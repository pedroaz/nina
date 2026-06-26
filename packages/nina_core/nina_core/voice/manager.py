from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from nina_core.config.paths import get_voice_recordings_path
from nina_core.config.settings import NinaConfig
from nina_core.meetings._protocols import RecorderError
from nina_core.meetings.recorder import (
    apply_ffmpeg_noise_reduction,
    boost_wav,
    make_audio_source,
    normalize_wav,
    record_wav,
)

from .service import VoiceCaptureService

VOICE_DEFAULT_SAMPLE_RATE = 16000
VOICE_DEFAULT_CHANNELS = 1
VOICE_DEFAULT_GAIN = 1.0
VOICE_DEFAULT_AUTO_NORMALIZE = False
VOICE_DEFAULT_NOISE_REDUCTION = "off"


@dataclass(slots=True)
class VoiceRecordingRequest:
    title: str = ""
    source: str | None = None
    device: str | int | None = None
    mic_device: str | int | None = None
    system_device: str | int | None = None
    sample_rate: int | None = None
    channels: int | None = None
    duration_seconds: int | None = None
    gain: float | None = None
    auto_normalize: bool | None = None
    normalize_target_dbfs: float | None = None
    noise_reduction: str | None = None


@dataclass(slots=True)
class VoiceRecordingSession:
    capture_id: str
    service: VoiceCaptureService
    audio_path: Path
    source: Any
    sample_rate: int
    channels: int
    duration_seconds: int | None
    gain: float
    auto_normalize: bool
    normalize_target_dbfs: float
    noise_reduction: str
    stop_event: threading.Event = field(default_factory=threading.Event)
    done_event: threading.Event = field(default_factory=threading.Event)
    thread: threading.Thread | None = None
    error: str | None = None
    size_bytes: int | None = None
    started_at: float = field(default_factory=time.monotonic)


class VoiceRecordingManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: dict[str, VoiceRecordingSession] = {}

    def active_capture_id(self) -> str | None:
        with self._lock:
            for capture_id, session in self._sessions.items():
                if not session.done_event.is_set():
                    return capture_id
        return None

    def start(
        self,
        *,
        config: NinaConfig,
        config_dir: Path,
        request: VoiceRecordingRequest,
    ) -> dict[str, Any]:
        source_name = (request.source or config.meetings.default_source or "mic").strip() or "mic"
        sample_rate = request.sample_rate or VOICE_DEFAULT_SAMPLE_RATE
        channels = request.channels or VOICE_DEFAULT_CHANNELS
        gain = request.gain if request.gain is not None else VOICE_DEFAULT_GAIN
        auto_normalize = (
            request.auto_normalize
            if request.auto_normalize is not None
            else VOICE_DEFAULT_AUTO_NORMALIZE
        )
        normalize_target_dbfs = (
            request.normalize_target_dbfs
            if request.normalize_target_dbfs is not None
            else config.meetings.normalize_target_dbfs
        )
        noise_reduction = (request.noise_reduction or VOICE_DEFAULT_NOISE_REDUCTION).strip().lower()
        device = request.device
        mic_device = request.mic_device
        system_device = request.system_device
        if device is None and mic_device is None and config.meetings.default_device:
            device = config.meetings.default_device
        device_name = self._describe_device(
            source_name, device=device, mic_device=mic_device, system_device=system_device
        )

        with self._lock:
            if any(not session.done_event.is_set() for session in self._sessions.values()):
                raise RecorderError("Another voice recording is already active.")

        try:
            vault_path = config.require_vault_path()
        except ValueError as exc:
            raise RecorderError(str(exc)) from exc
        service = VoiceCaptureService(
            config.database_path, get_voice_recordings_path(config_dir), vault_path
        )
        capture = service.start(
            title=request.title,
            source=source_name,
            device_name=device_name,
            sample_rate=sample_rate,
            channels=channels,
            audio_format="wav",
        )

        try:
            source = make_audio_source(
                source_name,
                device=device,
                mic_device=mic_device,
                system_device=system_device,
                sample_rate=sample_rate,
                channels=channels,
            )
            source.open(sample_rate, channels)
        except Exception as exc:
            service.update_status(capture["id"], status="failed", error=str(exc))
            raise RecorderError(str(exc)) from exc

        session = VoiceRecordingSession(
            capture_id=capture["id"],
            service=service,
            audio_path=Path(capture["audio_path"]),
            source=source,
            sample_rate=sample_rate,
            channels=channels,
            duration_seconds=request.duration_seconds,
            gain=gain,
            auto_normalize=auto_normalize,
            normalize_target_dbfs=normalize_target_dbfs,
            noise_reduction=noise_reduction,
        )
        thread = threading.Thread(target=self._run_session, args=(session,), daemon=True)
        session.thread = thread
        with self._lock:
            self._sessions[capture["id"]] = session
        thread.start()
        return capture

    def stop(self, capture_id: str, *, timeout_seconds: float = 30.0) -> dict[str, Any] | None:
        with self._lock:
            session = self._sessions.get(capture_id)
        if session is None:
            return None
        session.stop_event.set()
        try:
            session.source.close()
        except Exception:
            pass
        if not session.done_event.wait(timeout=timeout_seconds):
            raise RecorderError(f"Timed out stopping voice recording {capture_id}")
        return session.service.get(capture_id)

    def _run_session(self, session: VoiceRecordingSession) -> None:
        audio_path = session.audio_path
        error: str | None = None
        try:
            size_bytes = record_wav(
                audio_path,
                session.source,
                sample_rate=session.sample_rate,
                channels=session.channels,
                duration_seconds=float(session.duration_seconds)
                if session.duration_seconds
                else None,
                stop_event=session.stop_event,
            )
            session.size_bytes = size_bytes
            self._apply_quality_filters(audio_path, session)
            if audio_path.exists():
                session.size_bytes = audio_path.stat().st_size
        except BaseException as exc:  # noqa: BLE001 - recording failures must still finalize the row
            error = str(exc)
            if audio_path.exists():
                try:
                    session.size_bytes = audio_path.stat().st_size
                except Exception:
                    session.size_bytes = None
        finally:
            elapsed = max(0, int(time.monotonic() - session.started_at))
            try:
                session.service.stop(
                    session.capture_id,
                    duration_seconds=elapsed,
                    size_bytes=session.size_bytes,
                    error=error,
                )
            except Exception as stop_exc:
                session.error = error or str(stop_exc)
                try:
                    session.service.update_status(
                        session.capture_id, status="failed", error=session.error
                    )
                except Exception:
                    pass
            with self._lock:
                self._sessions.pop(session.capture_id, None)
            session.done_event.set()

    def _apply_quality_filters(self, audio_path: Path, session: VoiceRecordingSession) -> None:
        if session.noise_reduction == "ffmpeg":
            try:
                if apply_ffmpeg_noise_reduction(audio_path):
                    session.size_bytes = audio_path.stat().st_size
            except Exception:
                pass
        if session.auto_normalize:
            try:
                normalize_wav(audio_path, target_dbfs=session.normalize_target_dbfs)
                session.size_bytes = audio_path.stat().st_size
            except Exception:
                pass
        elif session.gain != 1.0:
            try:
                boost_wav(audio_path, session.gain)
                session.size_bytes = audio_path.stat().st_size
            except Exception:
                pass

    def _describe_device(
        self,
        source: str,
        *,
        device: str | int | None = None,
        mic_device: str | int | None = None,
        system_device: str | int | None = None,
    ) -> str | None:
        if source == "mixed":
            mic = self._device_label(mic_device if mic_device is not None else device)
            system = self._device_label(system_device if system_device is not None else device)
            return f"mic={mic}; system={system}"
        if source == "mic":
            return self._device_label(mic_device if mic_device is not None else device)
        if source == "system":
            return self._device_label(system_device if system_device is not None else device)
        if device is not None:
            return self._device_label(device)
        return None

    @staticmethod
    def _device_label(value: str | int | None) -> str:
        if value is None:
            return "default"
        return str(value)
