from __future__ import annotations

import math
import shutil
import struct
import subprocess
import sys
import threading
import time
import wave
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Protocol


class AudioSource(Protocol):
    def open(self, sample_rate: int, channels: int) -> None: ...
    def stream(self) -> Iterator[bytes]: ...
    def close(self) -> None: ...


class RecorderError(RuntimeError):
    """Raised when audio capture cannot start or fails mid-recording."""


def _wav_writer(path: Path, sample_rate: int, channels: int) -> wave.Wave_write:
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = wave.open(str(path), "wb")
    writer.setnchannels(channels)
    writer.setsampwidth(2)
    writer.setframerate(sample_rate)
    return writer


def _partial_path(final_path: Path) -> Path:
    return final_path.with_suffix(final_path.suffix + ".partial")


def _has_sounddevice() -> bool:
    """Return True if the `sounddevice` Python module is importable.

    We import lazily so importing this module never fails on systems that
    don't have PortAudio installed.
    """
    try:
        import sounddevice  # type: ignore[import-untyped]  # noqa: F401

        return True
    except Exception:
        return False


def is_portaudio_available() -> bool:
    """True when the PortAudio-backed mic capture path is usable.

    Requires both the `sounddevice` Python module and (typically) the
    `libportaudio2` system library. Use this from the CLI to decide whether
    to use PortAudio directly or fall back to the PulseAudio/PipeWire
    `parec` path.
    """
    return _has_sounddevice()


def _has_parec() -> bool:
    return shutil.which("parec") is not None


class NullAudioSource:
    """Audio source that yields silence. Used in tests and on systems without capture devices."""

    def __init__(self) -> None:
        self._stop = threading.Event()
        self._sample_rate = 16000
        self._channels = 1

    def open(self, sample_rate: int, channels: int) -> None:
        self._sample_rate = sample_rate
        self._channels = channels

    def stream(self) -> Iterator[bytes]:
        frame = b"\x00\x00" * self._channels * int(self._sample_rate / 50)
        while not self._stop.is_set():
            yield frame
            time.sleep(0.02)

    def close(self) -> None:
        self._stop.set()


class PortAudioSource:
    """Capture audio from the system default input using PortAudio via `sounddevice`."""

    def __init__(self, device: str | int | None = None) -> None:
        self._device = device
        self._stream: Any | None = None
        self._queue: list[bytes] = []
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._error: Exception | None = None
        self._sample_rate = 16000
        self._channels = 1

    def open(self, sample_rate: int, channels: int) -> None:
        try:
            import sounddevice as sd  # type: ignore[import-untyped]
        except ImportError as exc:
            raise RecorderError(
                "sounddevice is not installed. Run `pip install sounddevice` and ensure libportaudio2 is available."
            ) from exc
        self._sample_rate = sample_rate
        self._channels = channels

        def callback(indata: Any, frames: int, time_info: Any, status: Any) -> None:
            if status:
                pass
            with self._lock:
                self._queue.append(bytes(indata))

        try:
            stream = sd.InputStream(  # type: ignore[reportUnknownMemberType]
                samplerate=sample_rate,
                channels=channels,
                dtype="int16",
                device=self._device,
                callback=callback,
                blocksize=int(sample_rate / 10),
            )
            stream.start()  # type: ignore[reportUnknownMemberType]
            self._stream = stream
        except Exception as exc:
            raise RecorderError(f"Failed to open PortAudio input: {exc}") from exc

    def stream(self) -> Iterator[bytes]:
        if self._stream is None:
            raise RecorderError("PortAudio source not opened")
        while not self._stop.is_set():
            chunk: bytes | None = None
            with self._lock:
                if self._queue:
                    chunk = b"".join(self._queue)
                    self._queue.clear()
            if chunk:
                yield chunk
            else:
                time.sleep(0.02)
        if self._error is not None:
            raise self._error

    def close(self) -> None:
        self._stop.set()
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None


class PulseSource:
    """Capture any PulseAudio/PipeWire source via `parec`.

    Pass `device` to target a specific source (mic input, sink monitor,
    or anything else exposed by `pactl list short sources`). When
    `device` is None, the default behaviour depends on the `kind`:
    `monitor` reads from `@DEFAULT_MONITOR@` (system audio), `source`
    reads from `@DEFAULT_SOURCE@` (the default mic input).
    """

    def __init__(
        self,
        device: str | int | None = None,
        *,
        kind: str = "monitor",
    ) -> None:
        self._device = device
        self._kind = kind
        self._process: subprocess.Popen[bytes] | None = None
        self._stop = threading.Event()
        self._sample_rate = 16000
        self._channels = 1
        self._fallback_device: str | None = None

    def open(self, sample_rate: int, channels: int) -> None:
        if not sys.platform.startswith("linux"):
            raise RecorderError("PulseAudio/PipeWire capture is only supported on Linux.")
        if not _has_parec():
            raise RecorderError(
                "parec was not found. Install pulseaudio-utils (or the PipeWire equivalent)."
            )
        self._sample_rate = sample_rate
        self._channels = channels
        if self._device:
            device_spec = str(self._device)
        elif self._kind == "monitor":
            device_spec = "@DEFAULT_MONITOR@"
        else:
            device_spec = "@DEFAULT_SOURCE@"
        cmd = [
            "parec",
            "--device",
            device_spec,
            "--format=s16le",
            f"--rate={sample_rate}",
            f"--channels={channels}",
        ]
        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except FileNotFoundError as exc:
            raise RecorderError("parec binary not found on PATH") from exc
        except Exception as exc:
            raise RecorderError(f"Failed to start parec: {exc}") from exc

        # Give parec a brief moment to either start streaming or fail. If it
        # dies immediately (e.g. the device name is wrong, or the PulseAudio
        # server is down), surface its stderr so the user knows why.
        time.sleep(0.1)
        if self._process.poll() is not None:
            stderr = ""
            if self._process.stderr is not None:
                try:
                    stderr = self._process.stderr.read().decode("utf-8", errors="ignore").strip()
                except Exception:
                    pass
            self._process = None
            detail = f": {stderr}" if stderr else ""
            raise RecorderError(f"parec exited immediately for device {device_spec!r}{detail}")

    def stream(self) -> Iterator[bytes]:
        if self._process is None or self._process.stdout is None:
            raise RecorderError("Pulse source not opened")
        chunk_size = int(self._sample_rate * self._channels * 2 / 10)
        try:
            while not self._stop.is_set():
                chunk = self._process.stdout.read(chunk_size)
                if not chunk:
                    break
                yield chunk
        finally:
            if self._process and self._process.poll() is not None:
                stderr = ""
                if self._process.stderr is not None:
                    try:
                        stderr = self._process.stderr.read().decode("utf-8", errors="ignore")
                    except Exception:
                        stderr = ""
                if stderr.strip():
                    raise RecorderError(f"parec exited unexpectedly: {stderr.strip()}")

    def close(self) -> None:
        self._stop.set()
        if self._process is not None:
            try:
                self._process.terminate()
                self._process.wait(timeout=2)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    pass
            self._process = None


# Backward-compatible alias for the previous class name.
PulseMonitorSource = PulseSource


def make_audio_source(
    source: str,
    device: str | int | None = None,
    *,
    prefer_null: bool = False,
) -> AudioSource:
    """Factory used by the CLI to select an audio source.

    Recognised source values:

    - `mic`     — PortAudio (sounddevice). Falls back to `parec` against
                  `@DEFAULT_SOURCE@` when PortAudio is not available.
    - `system`  — `parec` against `@DEFAULT_MONITOR@` (system audio output).
    - `parec`   — `parec` against a user-chosen device (mic or monitor).
                  The `--device` flag is mandatory; we fall back to
                  `@DEFAULT_SOURCE@` if not given.

    `prefer_null=True` returns `NullAudioSource` regardless of `source`,
    which is useful for tests and headless runs.
    """

    if prefer_null:
        return NullAudioSource()
    if source == "mic":
        if is_portaudio_available():
            return PortAudioSource(device=device)
        # Fallback: record from the default PulseAudio/PipeWire input
        # source (the actual mic). Works on systems without libportaudio2
        # installed (e.g. a vanilla PipeWire desktop).
        if not _has_parec():
            raise RecorderError(
                "No audio capture backend available. Install `sounddevice` "
                "(requires libportaudio2) OR install `pulseaudio-utils` for `parec`."
            )
        return PulseSource(device=device, kind="source")
    if source == "system":
        return PulseSource(device=device, kind="monitor")
    if source == "parec":
        return PulseSource(device=device or "@DEFAULT_SOURCE@", kind="source")
    raise RecorderError(f"Unknown audio source: {source!r}")


def list_input_devices() -> list[dict[str, str]]:
    devices: list[dict[str, str]] = []
    if not _has_sounddevice():
        return devices
    try:
        import sounddevice as sd  # type: ignore[import-untyped]

        host_apis = sd.query_hostapis()  # type: ignore[reportUnknownMemberType, reportUnknownVariableType]
        for index, info in enumerate(sd.query_devices()):  # type: ignore[reportUnknownMemberType, reportUnknownVariableType]
            if int(info.get("max_input_channels", 0)) <= 0:  # type: ignore[reportUnknownMemberType, reportUnknownArgumentType]
                continue
            host_name = ""
            host_index = info.get("hostapi")  # type: ignore[reportUnknownMemberType]
            if isinstance(host_index, int) and 0 <= host_index < len(host_apis):  # type: ignore[reportUnknownArgumentType]
                host_name = host_apis[host_index].get("name", "")  # type: ignore[reportUnknownMemberType]
            devices.append(
                {
                    "index": str(index),
                    "name": str(info.get("name", "")),  # type: ignore[reportUnknownMemberType]
                    "host": host_name,
                    "channels": str(info.get("max_input_channels", 0)),  # type: ignore[reportUnknownMemberType]
                    "default_samplerate": str(info.get("default_samplerate", "")),  # type: ignore[reportUnknownMemberType]
                }
            )
    except Exception:
        return devices
    return devices  # type: ignore[reportUnknownMemberType, reportUnknownVariableType, reportUnknownArgumentType]


def list_pulse_sources() -> list[dict[str, str]]:
    sources: list[dict[str, str]] = []
    pactl = shutil.which("pactl")
    if pactl is None:
        return sources
    try:
        result = subprocess.run(
            [pactl, "list", "short", "sources"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except Exception:
        return sources
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        name = parts[1]
        if not name:
            continue
        sources.append({"name": name, "description": parts[2] if len(parts) > 2 else ""})
    return sources


def _promote_partial(partial: Path, final: Path) -> bool:
    """Atomically rename the `.partial` capture to its final path.

    If anything goes wrong, swallow the error and return False. The caller
    decides what to do next (e.g. the CLI still tries to finalize the
    meeting so the WAV we DID capture stays linked to the row, just
    under `.wav.partial`).
    """
    try:
        partial.replace(final)
    except Exception:
        return False
    return True


def record_wav(
    output_path: Path,
    source: AudioSource,
    sample_rate: int,
    channels: int,
    duration_seconds: float | None = None,
) -> int:
    """Stream from `source` into a WAV file. Returns the size in bytes.

    If the stream raises partway through, the `.wav.partial` file is still
    promoted to its final `.wav` path so the audio we DID capture stays
    attached to the meeting. Any error then re-raises.
    """

    partial = _partial_path(output_path)
    writer = _wav_writer(partial, sample_rate, channels)
    started = time.monotonic()
    deadline = started + duration_seconds if duration_seconds else None
    stream_error: BaseException | None = None
    try:
        for chunk in source.stream():
            writer.writeframes(chunk)
            if deadline is not None and time.monotonic() >= deadline:
                break
    except BaseException as exc:  # noqa: BLE001 — intentional wide catch
        stream_error = exc
    finally:
        writer.close()
        try:
            source.close()
        except Exception:
            pass

    if stream_error is not None:
        # Promote whatever we captured so the meeting row's audio_path
        # actually exists on disk. The audio may be shorter than intended,
        # but a partial recording is still useful (and the size will
        # reflect what was actually written). The exception then
        # propagates so the caller can decide whether to keep or discard.
        _promote_partial(partial, output_path)
        raise stream_error

    if not _promote_partial(partial, output_path):
        raise RecorderError(f"Failed to finalize recording at {output_path} (partial: {partial})")
    return output_path.stat().st_size


# ----------------------------------------------------------------------------
# Audio gain helpers
# ----------------------------------------------------------------------------
#
# The recorded WAVs come out at whatever level the source provides. On
# PulseAudio/PipeWire systems where the source volume is dialed down or
# the mic has a low output, the result can be too quiet to play back
# comfortably. These helpers apply gain in-place (rewriting the WAV) so
# the rest of the pipeline (faster-whisper, player) gets a healthier
# signal. They're lossless: read samples, scale, clip, write back at
# the same bit depth.


def _read_wav_samples(path: Path) -> tuple[int, int, int, bytes]:
    """Return (sample_rate, channels, sample_width_bytes, raw_bytes) for a WAV.

    Supports 8/16/24/32-bit integer PCM. The 8-bit case is unsigned
    (centered at 128), the others are signed little-endian. Anything
    else raises.
    """
    with wave.open(str(path), "rb") as reader:
        n_channels = reader.getnchannels()
        sample_width = reader.getsampwidth()
        sample_rate = reader.getframerate()
        raw = reader.readframes(reader.getnframes())
    if sample_width not in (1, 2, 3, 4):
        raise ValueError(f"Unsupported sample width: {sample_width} bytes")
    return sample_rate, n_channels, sample_width, raw


def _write_wav_samples(
    path: Path, sample_rate: int, n_channels: int, sample_width: int, raw: bytes
) -> None:
    """Write a complete WAV file with the given parameters and raw bytes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as writer:
        writer.setnchannels(n_channels)
        writer.setsampwidth(sample_width)
        writer.setframerate(sample_rate)
        writer.writeframes(raw)


def _samples_as_int(raw: bytes, sample_width: int) -> list[int]:
    """Decode raw PCM bytes to a list of signed ints, one per sample per channel."""
    if sample_width == 1:
        # 8-bit WAV is unsigned, centered at 128.
        return [b - 128 for b in raw]
    if sample_width == 2:
        return list(struct.unpack(f"<{len(raw) // 2}h", raw))
    if sample_width == 3:
        # 24-bit little-endian signed.
        out: list[int] = []
        for i in range(0, len(raw), 3):
            b0, b1, b2 = raw[i], raw[i + 1], raw[i + 2]
            v = b0 | (b1 << 8) | (b2 << 16)
            if v & 0x800000:
                v -= 0x1000000
            out.append(v)
        return out
    # 32-bit signed.
    return list(struct.unpack(f"<{len(raw) // 4}i", raw))


def _samples_to_int_bytes(samples: list[int], sample_width: int) -> bytes:
    """Encode a list of signed ints back to PCM bytes at the given width."""
    if sample_width == 1:
        # 8-bit WAV is unsigned: 0 is silence.
        return bytes((max(-128, min(127, s)) + 128) & 0xFF for s in samples)
    if sample_width == 2:
        clipped = [max(-32768, min(32767, s)) for s in samples]
        return struct.pack(f"<{len(clipped)}h", *clipped)
    if sample_width == 3:
        out = bytearray()
        for s in samples:
            v = max(-0x800000, min(0x7FFFFF, s))
            if v < 0:
                v += 0x1000000
            out += bytes((v & 0xFF, (v >> 8) & 0xFF, (v >> 16) & 0xFF))
        return bytes(out)
    clipped = [max(-0x80000000, min(0x7FFFFFFF, s)) for s in samples]
    return struct.pack(f"<{len(clipped)}i", *clipped)


def _peak_amplitude(samples: list[int]) -> int:
    return max((abs(s) for s in samples), default=0)


def peak_dbfs(path: Path) -> float | None:
    """Return the peak amplitude of `path` in dBFS, or None if the file is empty.

    Useful for telling the user "this recording is at -38 dBFS, you might
    want to boost it". Accepts both `str` and `Path`.
    """
    path = Path(path)
    _sample_rate, _n, sw, raw = _read_wav_samples(path)
    samples = _samples_as_int(raw, sw)
    peak = _peak_amplitude(samples)
    if peak == 0:
        return None
    # dBFS for a given integer peak at the file's bit depth.
    max_int = (1 << (sw * 8 - 1)) - 1
    return 20.0 * math.log10(peak / max_int)


def boost_wav(path: Path, factor: float) -> float:
    """Apply `factor` (linear gain) to every sample in the WAV, clipping in place.

    Returns the new peak dBFS after the boost. The file is rewritten
    atomically (write to a temp file, then replace). Accepts both
    `str` and `Path`.
    """
    path = Path(path)
    if factor <= 0:
        raise ValueError(f"gain factor must be > 0 (got {factor})")
    sample_rate, n_channels, sw, raw = _read_wav_samples(path)
    samples = _samples_as_int(raw, sw)
    boosted = [int(s * factor) for s in samples]
    clipped = _samples_to_int_bytes(boosted, sw)
    max_int = (1 << (sw * 8 - 1)) - 1
    # We rewrote as clipped ints; compute the real peak from the byte stream.
    new_samples = _samples_as_int(clipped, sw)
    new_peak = _peak_amplitude(new_samples) or 0
    tmp = path.with_suffix(path.suffix + ".boost.tmp")
    _write_wav_samples(tmp, sample_rate, n_channels, sw, clipped)
    tmp.replace(path)
    if new_peak == 0:
        return float("-inf")
    return 20.0 * math.log10(new_peak / max_int)


def normalize_wav(path: Path, target_dbfs: float = -3.0) -> tuple[float, float]:
    """Auto-gain the WAV so its peak hits `target_dbfs` (default -3 dBFS).

    Returns `(peak_before_dbfs, peak_after_dbfs)`. If the file is already
    at or above the target, it's left alone and both values are the same.
    """
    path = Path(path)
    _sample_rate, _n_channels, sw, raw = _read_wav_samples(path)
    samples = _samples_as_int(raw, sw)
    peak = _peak_amplitude(samples)
    if peak == 0:
        return (float("-inf"), float("-inf"))  # type: ignore[return-value]
    max_int = (1 << (sw * 8 - 1)) - 1
    current_dbfs = 20.0 * math.log10(peak / max_int)
    if current_dbfs >= target_dbfs:
        return (current_dbfs, current_dbfs)
    # We need `target_dbfs` peak. Required linear gain:
    headroom_db = target_dbfs - current_dbfs
    factor = 10.0 ** (headroom_db / 20.0)
    new_peak_dbfs = boost_wav(path, factor)
    return (current_dbfs, new_peak_dbfs)
