"""Cross-platform audio recording for Nina meetings.

Public surface:

- `AudioSource` — protocol implemented by every backend and the mixer.
- `RecorderError` — raised by every backend and the factory.
- `NullAudioSource` — silence. Used in tests and CI.
- `record_wav` — stream from any `AudioSource` into a WAV file.
- `make_audio_source` — the only factory. Picks a backend based on
  `--source` and the host platform.
- `list_input_devices`, `list_loopback_devices` — device discovery.
- `peak_dbfs`, `boost_wav`, `normalize_wav`, `apply_ffmpeg_noise_reduction`
  — gain helpers applied after recording.

Backend selection (`make_audio_source`):

- `mic`    → `SoundcardBackend(kind="mic")` on all 3 OSes.
- `system` → `MacosProcessTapSource` on macOS 14.4+ (no BlackHole).
             Falls back to `SoundcardBackend(kind="loopback")` on older
             macOS / Linux / Windows.
- `mixed`  → `AlignedMixer` over the mic and system sources above.

Backends live in `nina_core.meetings.backends`. Importing them lazily
keeps this module loadable on systems where the optional PyObjC extra is
not installed.
"""

from __future__ import annotations

import math
import shutil
import struct
import sys
import threading
import time
import wave
from collections.abc import Iterator
from pathlib import Path

from ._protocols import AudioSource, RecorderError
from .aligned_mixer import AlignedMixer

if sys.platform == "darwin":
    from .backends.macos_process_tap import MacosProcessTapSource  # noqa: F401
from .backends.soundcard_backend import (  # noqa: F401
    SoundcardBackend,
    list_microphones,
)


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


def _wav_writer(path: Path, sample_rate: int, channels: int) -> wave.Wave_write:
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = wave.open(str(path), "wb")
    writer.setnchannels(channels)
    writer.setsampwidth(2)
    writer.setframerate(sample_rate)
    return writer


def _partial_path(final_path: Path) -> Path:
    return final_path.with_suffix(final_path.suffix + ".partial")


def _promote_partial(partial: Path, final_path: Path) -> bool:
    """Atomically rename the `.partial` capture to its final path."""
    try:
        partial.replace(final_path)
    except Exception:
        return False
    return True


def make_audio_source(
    source: str,
    device: str | int | None = None,
    *,
    prefer_null: bool = False,
    mic_device: str | int | None = None,
    system_device: str | int | None = None,
    sample_rate: int = 48000,
    channels: int = 1,
) -> AudioSource:
    """Build an `AudioSource` for `source`.

    Recognised source values:

    - `mic`    — microphone input via `SoundcardBackend` (Pulse / CoreAudio / WASAPI).
    - `system` — system audio. On macOS 14.4+ this is the Core Audio Process
                 Tap (no BlackHole). On Linux and Windows it's the
                 `soundcard` loopback capture (Pulse monitor / WASAPI
                 loopback). On older macOS, falls back to `soundcard` (and
                 the user will need BlackHole for true system audio).
    - `mixed`  — `AlignedMixer` over the mic and system sources, frame-aligned
                 at 50 ms with sample rate alignment via `soxr`.

    `prefer_null=True` returns `NullAudioSource` regardless, which is
    useful for tests and headless runs.
    """
    if prefer_null:
        return NullAudioSource()
    if source == "mixed":
        mic = make_audio_source(
            "mic",
            device=mic_device if mic_device is not None else device,
            prefer_null=False,
        )
        system = make_audio_source(
            "system",
            device=system_device if system_device is not None else device,
            prefer_null=False,
        )
        return AlignedMixer(mic, system, target_rate=sample_rate, target_channels=channels)
    if source == "mic":
        return SoundcardBackend(device=device, kind="mic")
    if source == "system":
        if sys.platform == "darwin":
            tap = _try_macos_process_tap()
            if tap is not None:
                return tap
        return SoundcardBackend(device=device, kind="loopback")
    raise RecorderError(f"Unknown audio source: {source!r}")


def _try_macos_process_tap() -> AudioSource | None:
    """Return a `MacosProcessTapSource` if it can be constructed on this Mac.

    Returns `None` on non-macOS, on macOS older than 14.4, or when
    `pyobjc-framework-CoreAudio` isn't installed. The factory logs a
    single warning when this happens so the user knows the macOS Process
    Tap path was unavailable.
    """
    if sys.platform != "darwin":
        return None
    try:
        from .backends.macos_process_tap import (  # type: ignore[no-redef]
            MACOS_PROCESS_TAP_MIN_VERSION,
            MacosProcessTapSource,
            _macos_meets_min_version,
        )
    except ImportError:
        _warn_process_tap_unavailable("pyobjc-framework-CoreAudio is not installed")
        return None
    if not _macos_meets_min_version(MACOS_PROCESS_TAP_MIN_VERSION):
        _warn_process_tap_unavailable(
            f"macOS <{MACOS_PROCESS_TAP_MIN_VERSION[0]}.{MACOS_PROCESS_TAP_MIN_VERSION[1]}"
        )
        return None
    return MacosProcessTapSource()


_warn_process_tap_unavailable_emitted = False


def _warn_process_tap_unavailable(reason: str) -> None:
    """Emit a one-time warning. Goes to stderr via `print` so it appears
    in daemon logs without depending on the logging config."""
    global _warn_process_tap_unavailable_emitted
    if not _warn_process_tap_unavailable_emitted:
        print(
            f"[nina] macOS Process Tap unavailable ({reason}). "
            "Falling back to soundcard for system audio. "
            "On older macOS, install BlackHole for system capture.",
            file=sys.stderr,
        )
        _warn_process_tap_unavailable_emitted = True


def list_input_devices() -> list[dict[str, str]]:
    """List microphone input devices."""
    return list_microphones()


def record_wav(
    output_path: Path,
    source: AudioSource,
    sample_rate: int,
    channels: int,
    duration_seconds: float | None = None,
    stop_event: threading.Event | None = None,
) -> int:
    """Stream from `source` into a WAV file. Returns the size in bytes."""
    partial = _partial_path(output_path)
    writer = _wav_writer(partial, sample_rate, channels)
    started = time.monotonic()
    deadline = started + duration_seconds if duration_seconds else None
    stream_error: BaseException | None = None
    try:
        for chunk in source.stream():
            writer.writeframes(chunk)
            if stop_event is not None and stop_event.is_set():
                break
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
        _promote_partial(partial, output_path)
        raise stream_error

    if not _promote_partial(partial, output_path):
        raise RecorderError(f"Failed to finalize recording at {output_path} (partial: {partial})")
    return output_path.stat().st_size


# ----------------------------------------------------------------------------
# Audio gain helpers
# ----------------------------------------------------------------------------


def _read_wav_samples(path: Path) -> tuple[int, int, int, bytes]:
    """Return (sample_rate, channels, sample_width_bytes, raw_bytes) for a WAV."""
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
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as writer:
        writer.setnchannels(n_channels)
        writer.setsampwidth(sample_width)
        writer.setframerate(sample_rate)
        writer.writeframes(raw)


def _samples_as_int(raw: bytes, sample_width: int) -> list[int]:
    if sample_width == 1:
        return [b - 128 for b in raw]
    if sample_width == 2:
        return list(struct.unpack(f"<{len(raw) // 2}h", raw))
    if sample_width == 3:
        out: list[int] = []
        for i in range(0, len(raw), 3):
            b0, b1, b2 = raw[i], raw[i + 1], raw[i + 2]
            v = b0 | (b1 << 8) | (b2 << 16)
            if v & 0x800000:
                v -= 0x1000000
            out.append(v)
        return out
    return list(struct.unpack(f"<{len(raw) // 4}i", raw))


def _samples_to_int_bytes(samples: list[int], sample_width: int) -> bytes:
    if sample_width == 1:
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
    """Return the peak amplitude of `path` in dBFS, or None if the file is empty."""
    path = Path(path)
    _sample_rate, _n, sw, raw = _read_wav_samples(path)
    samples = _samples_as_int(raw, sw)
    peak = _peak_amplitude(samples)
    if peak == 0:
        return None
    max_int = (1 << (sw * 8 - 1)) - 1
    return 20.0 * math.log10(peak / max_int)


def boost_wav(path: Path, factor: float) -> float:
    """Apply `factor` (linear gain) to every sample in the WAV, clipping in place."""
    path = Path(path)
    if factor <= 0:
        raise ValueError(f"gain factor must be > 0 (got {factor})")
    sample_rate, n_channels, sw, raw = _read_wav_samples(path)
    samples = _samples_as_int(raw, sw)
    boosted = [int(s * factor) for s in samples]
    clipped = _samples_to_int_bytes(boosted, sw)
    max_int = (1 << (sw * 8 - 1)) - 1
    new_samples = _samples_as_int(clipped, sw)
    new_peak = _peak_amplitude(new_samples) or 0
    tmp = path.with_suffix(path.suffix + ".boost.tmp")
    _write_wav_samples(tmp, sample_rate, n_channels, sw, clipped)
    tmp.replace(path)
    if new_peak == 0:
        return float("-inf")
    return 20.0 * math.log10(new_peak / max_int)


def normalize_wav(path: Path, target_dbfs: float = -3.0) -> tuple[float, float]:
    """Auto-gain the WAV so its peak hits `target_dbfs`."""
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
    headroom_db = target_dbfs - current_dbfs
    factor = 10.0 ** (headroom_db / 20.0)
    new_peak_dbfs = boost_wav(path, factor)
    return (current_dbfs, new_peak_dbfs)


def apply_ffmpeg_noise_reduction(path: Path) -> bool:
    """Apply a best-effort noise reduction pass using ffmpeg's `afftdn` filter."""
    path = Path(path)
    if shutil.which("ffmpeg") is None:
        return False
    sample_rate, channels, _sample_width, _raw = _read_wav_samples(path)
    tmp = path.with_suffix(path.suffix + ".denoise.tmp")
    try:
        result = __import__("subprocess").run(
            [
                shutil.which("ffmpeg") or "ffmpeg",
                "-y",
                "-i",
                str(path),
                "-af",
                "afftdn",
                "-ar",
                str(sample_rate),
                "-ac",
                str(channels),
                "-c:a",
                "pcm_s16le",
                str(tmp),
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=60 * 30,
        )
    except Exception:
        return False
    if result.returncode != 0 or not tmp.exists():
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass
        return False
    tmp.replace(path)
    return True
