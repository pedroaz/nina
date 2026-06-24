"""Cross-platform audio capture via the `soundcard` library.

`soundcard` is a single Python library that wraps the OS-native audio stack
on every desktop OS:

- Linux: PulseAudio / PipeWire (via `libpulse`)
- macOS: CoreAudio
- Windows: WASAPI

It exposes a uniform `Microphone`/`Speaker` API and supports loopback
captures (reading a speaker's output) on Linux and Windows. On macOS,
system audio is captured by `MacosProcessTapSource` instead — the
`soundcard` library does not implement the macOS Process Tap.
"""

from __future__ import annotations

import sys
import threading
import time
from collections.abc import Iterator
from typing import Any, Literal

import numpy as np

from .._protocols import RecorderError

Kind = Literal["mic", "speaker", "loopback"]


def _pcm16_bytes_from_ndarray(data: Any) -> bytes:
    """Convert a soundcard float ndarray into mono PCM16 little-endian bytes."""
    array = np.asarray(data)
    if array.ndim == 2:
        array = array.mean(axis=1)
    array = np.clip(array, -1.0, 1.0)
    pcm = (array * 32767.0).astype(np.int16)
    return pcm.tobytes()


class SoundcardBackend:
    """Capture audio with the cross-platform `soundcard` backend.

    `kind` selects which kind of device to open:

    - `"mic"`     — default microphone input (all 3 OSes)
    - `"loopback"` — speaker output captured as input. On Linux this resolves
                     to a PulseAudio `.monitor` source; on Windows it opens
                     a WASAPI render endpoint in loopback mode. On macOS this
                     is not a real "process tap" path — use
                     `MacosProcessTapSource` for that. The factory falls
                     back to this only when the Process Tap isn't available.
    - `"speaker"`  — like `"loopback"` but selects a specific output device.

    `device` is an optional name (substring match) or device id used to
    disambiguate when the user has more than one of the chosen kind.
    """

    def __init__(self, device: str | int | None = None, *, kind: Kind = "mic") -> None:
        self._device = device
        self._kind: Kind = kind
        self._card: Any | None = None
        self._recorder: Any | None = None
        self._recorder_cm: Any | None = None
        self._stream_gen: Any | None = None
        self._stop = threading.Event()
        self._stream_finished = threading.Event()
        self._reader_thread: threading.Thread | None = None
        self._closed = False
        self._sample_rate = 16000
        self._channels = 1
        self._chunk_frames = 0
        self._mode = ""

    def open(self, sample_rate: int, channels: int) -> None:
        try:
            import soundcard as sc  # type: ignore[import-untyped]
        except ImportError as exc:
            raise RecorderError(
                "soundcard is not installed. Run `pip install soundcard` to use the cross-platform backend."
            ) from exc

        self._sample_rate = sample_rate
        self._channels = channels
        self._chunk_frames = max(256, int(sample_rate / 10))

        try:
            self._card = self._resolve_card(sc)
        except Exception as exc:
            raise RecorderError(f"Failed to resolve soundcard {self._kind}: {exc}") from exc
        if self._card is None:
            raise RecorderError(f"No soundcard {self._kind} available")
        # Touch the PulseAudio lib to surface any system issues early. The
        # `soundcard` library has a bug at import time when `sys.argv` has
        # fewer than 2 entries (it does `sys.argv[1][:30]` while computing
        # the PulseAudio client name). Nina patches `sys.argv` in
        # `_verify_imports` for `python -c` invocations; for normal CLI
        # usage `sys.argv` always has at least the program name + command.
        # We touch `_pulse` here to make sure the import succeeded.
        getattr(sc, "_pulse", None)

        recorder_factory = getattr(self._card, "recorder", None)
        if not callable(recorder_factory):
            raise RecorderError("Soundcard backend does not expose a record API")
        try:
            self._recorder_cm = recorder_factory(
                samplerate=sample_rate, blocksize=self._chunk_frames
            )
            if hasattr(self._recorder_cm, "__enter__"):
                self._recorder = self._recorder_cm.__enter__()
            else:
                self._recorder = self._recorder_cm
            self._mode = "recorder"
        except Exception as exc:
            raise RecorderError(f"Failed to open soundcard recorder: {exc}") from exc

    def stream(self) -> Iterator[bytes]:
        if self._recorder is None:
            raise RecorderError("Soundcard source not opened")
        # Reset the finished event so a re-iteration of `stream()` (e.g. after
        # a transient error) can be coordinated with `close()` again.
        self._stream_finished.clear()
        self._closed = False
        self._reader_thread = threading.current_thread()

        def _generator() -> Iterator[bytes]:
            consecutive_empty = 0
            try:
                while not self._stop.is_set():
                    try:
                        data = self._recorder.record(numframes=self._chunk_frames)  # type: ignore[union-attr]
                    except TypeError as exc:
                        # Older versions of `soundcard` raise TypeError
                        # ("object of type 'NoneType' has no len()") when PulseAudio
                        # reports a hole. The patched library returns an empty array
                        # instead, but we keep this guard for unpatched installs:
                        # treat the empty read as silence and continue.
                        if "NoneType" in str(exc) and "len" in str(exc):
                            consecutive_empty += 1
                            if consecutive_empty > 50:
                                raise RecorderError(
                                    "Soundcard capture stuck on empty reads"
                                ) from exc
                            time.sleep(0.01)
                            continue
                        raise RecorderError(f"Soundcard capture failed: {exc}") from exc
                    except Exception as exc:
                        raise RecorderError(f"Soundcard capture failed: {exc}") from exc
                    if data is None:
                        break
                    if getattr(data, "size", 0) == 0:
                        consecutive_empty += 1
                        if consecutive_empty > 50:
                            break
                        time.sleep(0.005)
                        continue
                    consecutive_empty = 0
                    chunk = _pcm16_bytes_from_ndarray(data)
                    if chunk:
                        yield chunk
            finally:
                # Tear down the PulseAudio stream on this thread (the
                # reader thread). This avoids the `soundcard` close race
                # where `__exit__` is called from another thread while
                # `_recorder.record()` is still in flight.
                self._teardown_recorder()

        gen = _generator()
        self._stream_gen = gen
        return gen

    def close(self) -> None:
        # The `soundcard` library's `recorder` context manager is NOT
        # thread-safe: calling `__exit__` while the reader thread is in
        # `_recorder.record()` can crash the PulseAudio native code
        # (`pa_stream_get_state` assertion or glibc heap corruption).
        #
        # To avoid the race, `close()` is split across two threads:
        #
        # - The first caller (typically the API handler thread that stops
        #   the recording) just sets the stop event. It does NOT touch the
        #   PulseAudio stream.
        # - The reader thread (the one iterating `stream()`) sees the stop
        #   event, exits its `try` block, and runs the `finally` clause
        #   that calls `__exit__` on the context manager. This happens on
        #   the same thread that was doing the reading, which is safe.
        #
        # If `close()` is called from the reader thread itself (e.g. via
        # `record_wav`'s `finally`), it runs the teardown directly.
        if self._recorder_cm is None:
            self._stop.set()
            return
        if self._closed:
            return
        self._closed = True
        if threading.current_thread() is self._reader_thread:
            self._stop.set()
            self._teardown_recorder()
            return
        # Called from another thread (API handler). Signal the reader to
        # stop; the reader's `finally` block will tear down the recorder.
        self._stop.set()
        # Best-effort: wait for the reader to finish so the caller knows
        # the PulseAudio stream has been released. Bounded so we don't
        # hang if the reader is stuck.
        block_seconds = self._chunk_frames / max(self._sample_rate, 1)
        self._stream_finished.wait(timeout=min(1.0, max(0.35, block_seconds * 2 + 0.15)))

    def _teardown_recorder(self) -> None:
        """Tear down the PulseAudio stream. Must be called on the reader
        thread (the one that was iterating `stream()`) to avoid the
        `soundcard` close race."""
        if self._recorder_cm is not None:
            try:
                if hasattr(self._recorder_cm, "__exit__"):
                    self._recorder_cm.__exit__(None, None, None)
            except Exception:
                pass
            self._recorder_cm = None
        self._recorder = None
        self._stream_gen = None
        self._stream_finished.set()

    def _resolve_card(self, sc: Any) -> Any:
        # `soundcard` 0.4.6 takes no args on `default_microphone`; 0.4.7+
        # accepts `include_loopback` / `exclude_monitors`. Probe the signature
        # once at import time so we don't pay the introspection cost per call.
        default_mic = sc.default_microphone
        try:
            import inspect

            default_mic_supports_loopback = (
                "include_loopback" in inspect.signature(default_mic).parameters
            )
        except Exception:
            default_mic_supports_loopback = False
        if self._kind == "mic":
            if self._device is not None:
                return sc.get_microphone(
                    self._device, include_loopback=False, exclude_monitors=True
                )
            if default_mic_supports_loopback:
                return default_microphone_with_loopback(  # type: ignore[name-defined]
                    default_mic, include_loopback=False, exclude_monitors=True
                )
            return default_mic()
        if self._kind in ("loopback", "speaker"):
            if self._device is not None:
                try:
                    return sc.get_microphone(
                        self._device, include_loopback=True, exclude_monitors=False
                    )
                except Exception:
                    return sc.get_speaker(self._device)
            if self._kind == "loopback":
                if default_mic_supports_loopback:
                    default_loop = default_microphone_with_loopback(  # type: ignore[name-defined]
                        default_mic, include_loopback=True, exclude_monitors=False
                    )
                    if default_loop is not None:
                        return default_loop
                # `default_microphone` doesn't support the loopback kwargs in
                # this version, and `default_speaker()` returns a `Speaker`
                # which has no `record`/`recorder` API. Fall back to scanning
                # all microphones for the first loopback monitor.
                try:
                    for mic in sc.all_microphones(include_loopback=True, exclude_monitors=False):
                        if getattr(mic, "isloopback", False):
                            return mic
                except Exception:
                    pass
            if self._kind == "speaker":
                return sc.default_speaker()
                raise RecorderError(
                    "No soundcard loopback device found. On Linux, ensure a PulseAudio "
                    "monitor source is available (e.g. `pactl list sources short` should "
                    "list at least one `.monitor` source)."
                )
        raise RecorderError(f"Unknown soundcard kind: {self._kind!r}")


def default_microphone_with_loopback(fn: Any, **kwargs: Any) -> Any:
    """Call a `soundcard.default_microphone` that supports the loopback kwargs."""
    return fn(**kwargs)


def list_loopback_devices() -> list[dict[str, str]]:
    """List monitors / loopback devices visible to the `soundcard` library."""
    try:
        import soundcard as sc  # type: ignore[import-untyped]
    except Exception:
        return []
    out: list[dict[str, str]] = []
    try:
        for mic in sc.all_microphones(include_loopback=True, exclude_monitors=False):
            if getattr(mic, "isloopback", False):
                out.append({"name": getattr(mic, "name", str(mic))})
    except Exception:
        pass
    if not out and sys.platform.startswith("linux"):
        try:
            for speaker in sc.all_speakers():
                out.append({"name": getattr(speaker, "name", str(speaker)) + " (monitor)"})
        except Exception:
            pass
    return out


def list_microphones() -> list[dict[str, str]]:
    """List microphone input devices visible to the `soundcard` library."""
    try:
        import soundcard as sc  # type: ignore[import-untyped]
    except Exception:
        return []
    out: list[dict[str, str]] = []
    try:
        for mic in sc.all_microphones(include_loopback=False, exclude_monitors=True):
            out.append({"name": getattr(mic, "name", str(mic))})
    except Exception:
        pass
    return out
