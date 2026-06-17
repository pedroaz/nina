from __future__ import annotations

import os
import re
import shutil
import subprocess
import uuid
import warnings
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from nina_core.config.settings import TranscriptionConfig
from nina_core.models.models import LLMInteraction


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def _suppress_hf_unauth_warning() -> Any:
    """Suppress `huggingface_hub`'s "unauthenticated requests" `UserWarning`
    when no `HF_TOKEN` is set in the environment.

    Nina downloads public models (Whisper, BGE) so an auth token is not
    required. The warning is noisy and confusing for users who haven't
    signed up for a Hugging Face account. If the user has set `HF_TOKEN`,
    the library uses it automatically and we don't suppress anything.
    """
    if os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN"):
        yield
        return
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=".*unauthenticated requests to the HF Hub.*",
            category=UserWarning,
        )
        yield


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str


@dataclass
class TranscriptResult:
    text: str
    segments: list[TranscriptSegment]
    language: str | None
    model: str
    duration_seconds: float | None = None


class TranscriptionProvider:
    """Abstract transcription provider."""

    def transcribe(self, audio_path: Path, *, language: str | None = None) -> TranscriptResult:
        raise NotImplementedError


class NullTranscriptionProvider(TranscriptionProvider):
    """Returns a fixed transcript. Used in tests and CI."""

    def __init__(self, text: str = "Hello from the NullTranscriptionProvider.") -> None:
        self.text = text
        self.call_count = 0

    def transcribe(self, audio_path: Path, *, language: str | None = None) -> TranscriptResult:
        self.call_count += 1
        return TranscriptResult(
            text=self.text,
            segments=[TranscriptSegment(start=0.0, end=1.0, text=self.text)],
            language=language or "en",
            model="null",
        )


class FasterWhisperProvider(TranscriptionProvider):
    """Transcribes audio locally using `faster-whisper`."""

    def __init__(
        self,
        model: str = "small",
        device: str = "cpu",
        compute_type: str = "int8",
        language: str | None = None,
    ) -> None:
        self.model = model
        self.device = device
        self.compute_type = compute_type
        self.language = language

    def transcribe(self, audio_path: Path, *, language: str | None = None) -> TranscriptResult:
        try:
            from faster_whisper import WhisperModel  # type: ignore[import-untyped]
        except ImportError as exc:
            raise RuntimeError(
                "faster-whisper is not installed. Install with `pip install nina-core[transcription]`."
            ) from exc
        lang = language or self.language
        with _suppress_hf_unauth_warning():
            whisper = WhisperModel(self.model, device=self.device, compute_type=self.compute_type)
        segments_iter, info = whisper.transcribe(
            str(audio_path),
            language=lang,
            vad_filter=True,
            word_timestamps=False,
        )
        segments: list[TranscriptSegment] = []
        text_parts: list[str] = []
        duration: float | None = None
        for seg in segments_iter:
            text_parts.append(seg.text.strip())
            segments.append(
                TranscriptSegment(start=float(seg.start), end=float(seg.end), text=seg.text.strip())
            )
            if duration is None or float(seg.end) > duration:
                duration = float(seg.end)
        text = " ".join(part for part in text_parts if part).strip()
        return TranscriptResult(
            text=text,
            segments=segments,
            language=getattr(info, "language", lang),
            model=self.model,
            duration_seconds=duration,
        )


class WhisperCliProvider(TranscriptionProvider):
    """Falls back to the `whisper` CLI binary if installed and faster-whisper is not available."""

    def __init__(self, model: str = "small", language: str | None = None) -> None:
        self.model = model
        self.language = language

    def transcribe(self, audio_path: Path, *, language: str | None = None) -> TranscriptResult:
        binary = shutil.which("whisper")
        if binary is None:
            raise RuntimeError(
                "whisper CLI not found on PATH. Install faster-whisper or openai-whisper."
            )
        effective_language = language or self.language
        with tempfile_dir() as tmp:
            cmd = [
                binary,
                str(audio_path),
                "--model",
                self.model,
                "--output_format",
                "txt",
                "--output_dir",
                str(tmp),
            ]
            if effective_language:
                cmd.extend(["--language", effective_language])
            result = subprocess.run(
                cmd, capture_output=True, text=True, check=False, timeout=60 * 60
            )
            if result.returncode != 0:
                raise RuntimeError(
                    f"whisper CLI failed (code {result.returncode}): {result.stderr.strip()}"
                )
            stem = audio_path.stem
            text_file = tmp / f"{stem}.txt"
            text = text_file.read_text() if text_file.exists() else ""
        return TranscriptResult(
            text=text.strip(),
            segments=[],
            language=effective_language,
            model=self.model,
        )


def tempfile_dir() -> _TempDir:
    import tempfile

    path = Path(tempfile.mkdtemp(prefix="nina-whisper-"))
    return _TempDir(path)


class _TempDir:
    def __init__(self, path: Path) -> None:
        self.path = path

    def __enter__(self) -> Path:
        return self.path

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        shutil.rmtree(self.path, ignore_errors=True)


def build_transcription_provider(
    config: TranscriptionConfig | None = None,
) -> TranscriptionProvider:
    """Build a transcription provider from Nina config.

    All values come from `config.transcription.*`. The provider is selected
    by `config.backend` and the model/device/compute_type/language are
    applied to whichever concrete provider is built.
    """
    cfg = config or TranscriptionConfig()
    name = cfg.backend.lower()
    if name in {"null", "fake"}:
        return NullTranscriptionProvider()
    if name in {"local_whisper", "faster_whisper"}:
        try:
            import faster_whisper  # type: ignore[import-untyped]  # noqa: F401

            return FasterWhisperProvider(
                model=cfg.model,
                device=cfg.device,
                compute_type=cfg.compute_type,
                language=cfg.language,
            )
        except ImportError:
            return WhisperCliProvider(model=cfg.model, language=cfg.language)
    if name in {"whisper_cli", "whisper"}:
        return WhisperCliProvider(model=cfg.model, language=cfg.language)
    raise RuntimeError(f"Unsupported transcription backend: {cfg.backend}")


@dataclass
class TranscriptionStatus:
    """Snapshot of the configured transcription backend's health.

    Used by `nina status` so the user can see whether the audio pipeline is
    actually ready (faster-whisper installed, whisper CLI on PATH, etc.) before
    triggering a long transcription run.
    """

    backend: str
    model: str
    device: str
    compute_type: str
    available: bool
    detail: str | None = None
    provider_class: str | None = None


def check_transcription_status(
    config: TranscriptionConfig | None = None,
) -> TranscriptionStatus:
    """Probe the configured transcription backend without running a model.

    Cheap: just imports / PATH checks. Never raises.
    """
    cfg = config or TranscriptionConfig()
    backend = (cfg.backend or "").lower()
    if backend in {"null", "fake"}:
        return TranscriptionStatus(
            backend=backend,
            model=cfg.model,
            device=cfg.device,
            compute_type=cfg.compute_type,
            available=True,
            detail="null backend returns a fixed transcript (tests/CI)",
            provider_class=NullTranscriptionProvider.__name__,
        )
    if backend in {"local_whisper", "faster_whisper"}:
        try:
            import faster_whisper  # type: ignore[import-untyped]  # noqa: F401

            return TranscriptionStatus(
                backend=backend,
                model=cfg.model,
                device=cfg.device,
                compute_type=cfg.compute_type,
                available=True,
                detail=(
                    f"faster-whisper will pull {cfg.model!r} on first run "
                    f"({cfg.device}/{cfg.compute_type})"
                ),
                provider_class=FasterWhisperProvider.__name__,
            )
        except ImportError:
            binary = shutil.which("whisper")
            if binary is not None:
                return TranscriptionStatus(
                    backend=backend,
                    model=cfg.model,
                    device=cfg.device,
                    compute_type=cfg.compute_type,
                    available=True,
                    detail=(
                        "faster-whisper is not installed; falling back to the "
                        f"`whisper` CLI at {binary}"
                    ),
                    provider_class=WhisperCliProvider.__name__,
                )
            return TranscriptionStatus(
                backend=backend,
                model=cfg.model,
                device=cfg.device,
                compute_type=cfg.compute_type,
                available=False,
                detail=(
                    "faster-whisper is not installed and the `whisper` CLI is "
                    "not on PATH. Run `nina setup transcription` or "
                    "`uv pip install --python <nina-python> faster-whisper`."
                ),
                provider_class=None,
            )
    if backend in {"whisper_cli", "whisper"}:
        binary = shutil.which("whisper")
        if binary is not None:
            return TranscriptionStatus(
                backend=backend,
                model=cfg.model,
                device=cfg.device,
                compute_type=cfg.compute_type,
                available=True,
                detail=f"`whisper` CLI found at {binary}",
                provider_class=WhisperCliProvider.__name__,
            )
        return TranscriptionStatus(
            backend=backend,
            model=cfg.model,
            device=cfg.device,
            compute_type=cfg.compute_type,
            available=False,
            detail=(
                "`whisper` CLI not found on PATH. Install openai-whisper, "
                "run `nina setup transcription`, or switch the backend to "
                "`local_whisper`."
            ),
            provider_class=None,
        )
    return TranscriptionStatus(
        backend=backend,
        model=cfg.model,
        device=cfg.device,
        compute_type=cfg.compute_type,
        available=False,
        detail=f"Unknown transcription backend: {cfg.backend!r}",
        provider_class=None,
    )


def _interaction_id() -> str:
    return "li_" + uuid.uuid4().hex[:24]


def _slugify_segment(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return slug[:60] or "segment"


def write_transcript_files(
    result: TranscriptResult,
    output_text_path: Path,
    output_segments_path: Path | None = None,
) -> None:
    output_text_path.parent.mkdir(parents=True, exist_ok=True)
    output_text_path.write_text(result.text + "\n")
    if output_segments_path is not None:
        payload = {
            "language": result.language,
            "model": result.model,
            "duration_seconds": result.duration_seconds,
            "segments": [{"start": s.start, "end": s.end, "text": s.text} for s in result.segments],
        }
        output_segments_path.write_text(_json_dumps(payload))


def _json_dumps(data: dict[str, Any]) -> str:
    import json

    return json.dumps(data, ensure_ascii=False, indent=2)


def log_transcription_interaction(
    db_path: str,
    *,
    provider_name: str,
    model: str,
    audio_path: str,
    result: TranscriptResult,
    workflow_run_id: str | None,
    status: str = "completed",
    error: str | None = None,
) -> None:
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    try:
        prompt = (
            f"Transcribe audio file at {audio_path} with model {model} "
            f"(language={result.language or 'auto'})."
        )
        interaction = LLMInteraction(
            id=_interaction_id(),
            provider=provider_name,
            model=model,
            purpose="meeting_transcription",
            prompt=prompt,
            response=result.text[:4000],
            status=status,
            error=error,
            workflow_run_id=workflow_run_id,
            created_at=_now(),
            completed_at=_now() if status != "pending" else None,
        )
        db.add(interaction)
        db.commit()
    finally:
        db.close()
