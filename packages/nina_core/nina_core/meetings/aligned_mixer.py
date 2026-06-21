"""Frame-aligned mixer for two `AudioSource` instances.

Wraps a mic source and a system source. Each source runs on its own
background thread that:
  1. Reads raw PCM16 chunks from `source.stream()`.
  2. Converts them to mono float32.
  3. Resamples to the common target rate (default 48 kHz) using `soxr`.
  4. Cuts the resampled stream into fixed-size 50 ms frames and pushes
     PCM16 bytes to a per-side output queue.

The consumer thread (the one calling `stream()`) pulls one 50 ms frame from
each side, mixes with `audioop.add` + halving, and yields. This is the
Python analog of Meetily's `AudioPipelineManager` 50 ms windowing.
"""

from __future__ import annotations

import audioop
import threading
import time
from collections.abc import Iterator
from queue import Empty, Queue

import numpy as np
import soxr  # pyright: ignore[reportMissingTypeStubs]

from ._protocols import AudioSource, RecorderError

FRAME_MS = 50


class AlignedMixer:
    """Mix two `AudioSource` instances, frame-aligned at 50 ms."""

    def __init__(
        self,
        left: AudioSource,
        right: AudioSource,
        *,
        target_rate: int = 48000,
        target_channels: int = 1,
    ) -> None:
        self._left = left
        self._right = right
        self._target_rate = target_rate
        self._target_channels = target_channels
        self._frame_samples = max(1, target_rate * FRAME_MS // 1000)
        self._frame_bytes = self._frame_samples * target_channels * 2

        self._left_queue: Queue[bytes | None] = Queue()
        self._right_queue: Queue[bytes | None] = Queue()
        self._left_worker: _ResampleWorker | None = None
        self._right_worker: _ResampleWorker | None = None
        self._errors: list[Exception] = []
        self._stop = threading.Event()
        self._opened = False

    def open(self, sample_rate: int, channels: int) -> None:
        if sample_rate != self._target_rate or channels != self._target_channels:
            raise RecorderError(
                f"AlignedMixer.open expects sample_rate={self._target_rate} "
                f"channels={self._target_channels}, got {sample_rate}x{channels}. "
                "The factory should pass the target rate; this is a bug."
            )
        self._left.open(sample_rate, channels)
        try:
            self._right.open(sample_rate, channels)
        except Exception:
            try:
                self._left.close()
            except Exception:
                pass
            raise

        self._left_worker = _ResampleWorker(
            self._left,
            self._target_rate,
            self._target_channels,
            self._frame_bytes,
            self._left_queue,
            self._errors,
            self._stop,
        )
        self._right_worker = _ResampleWorker(
            self._right,
            self._target_rate,
            self._target_channels,
            self._frame_bytes,
            self._right_queue,
            self._errors,
            self._stop,
        )
        self._left_worker.start()
        self._right_worker.start()
        self._opened = True

    def stream(self) -> Iterator[bytes]:
        if not self._opened:
            raise RecorderError("Aligned mixer not opened")
        left_done = False
        right_done = False
        silence = b"\x00" * self._frame_bytes
        while not self._stop.is_set():
            if self._errors:
                raise RecorderError(f"Mixed audio source failed: {self._errors[0]}")
            left_frame: bytes | None = silence if left_done else None
            right_frame: bytes | None = silence if right_done else None
            if not left_done:
                item = self._drain_queue(self._left_queue)
                if item is _SENTINEL_DONE:
                    left_done = True
                elif item is not None:
                    left_frame = item  # pyright: ignore[reportAssignmentType]
            if not right_done:
                item = self._drain_queue(self._right_queue)
                if item is _SENTINEL_DONE:
                    right_done = True
                elif item is not None:
                    right_frame = item  # pyright: ignore[reportAssignmentType]
            if self._errors:
                raise RecorderError(f"Mixed audio source failed: {self._errors[0]}")
            if left_frame and right_frame:
                yield _mix_pcm16(left_frame, right_frame)
                if left_done and right_done:
                    break
                continue
            time.sleep(0.005)
        if self._errors:
            raise RecorderError(f"Mixed audio source failed: {self._errors[0]}")

    def _drain_queue(self, q: Queue[bytes | None]) -> bytes | _SentinelDone | None:
        try:
            item = q.get(timeout=0.05)
        except Empty:
            return None
        if item is None:
            return _SENTINEL_DONE
        return item

    def close(self) -> None:
        self._stop.set()
        try:
            self._left.close()
        except Exception:
            pass
        try:
            self._right.close()
        except Exception:
            pass
        for worker in (self._left_worker, self._right_worker):
            if worker is not None:
                worker.join(timeout=2)
        self._opened = False


class _SentinelDone:
    pass


_SENTINEL_DONE = _SentinelDone()


def _mix_pcm16(left: bytes, right: bytes) -> bytes:
    if not left:
        return right
    if not right:
        return left
    if len(left) != len(right):
        target_len = max(len(left), len(right))
        if len(left) < target_len:
            left = left + b"\x00" * (target_len - len(left))
        if len(right) < target_len:
            right = right + b"\x00" * (target_len - len(right))
    mixed = audioop.add(left, right, 2)
    return audioop.mul(mixed, 2, 0.5)


class _ResampleWorker(threading.Thread):
    """Background thread that pulls PCM16 from a source, resamples to the
    target rate, and cuts into fixed-size 50 ms frames.

    Each frame is exactly `frame_bytes` long (zero-padded at EOF so the
    mixer always gets a full 50 ms slot). When the source ends, `None` is
    pushed to the queue as a sentinel.
    """

    def __init__(
        self,
        source: AudioSource,
        target_rate: int,
        target_channels: int,
        frame_bytes: int,
        out_queue: Queue[bytes | None],
        errors: list[Exception],
        stop_evt: threading.Event,
    ) -> None:
        super().__init__(daemon=True)
        self._source = source
        self._target_rate = target_rate
        self._target_channels = target_channels
        self._frame_bytes = frame_bytes
        self._out_queue = out_queue
        self._errors = errors
        self._stop_evt = stop_evt
        self._native_rate = getattr(source, "native_rate", None) or target_rate
        self._native_channels = getattr(source, "native_channels", None) or target_channels

    def run(self) -> None:
        try:
            self._pump()
        except Exception as exc:
            self._errors.append(exc)
        finally:
            self._out_queue.put(None)

    def _pump(self) -> None:
        resampler = _StreamResampler(
            self._native_rate,
            self._native_channels,
            self._target_rate,
            self._target_channels,
        )
        for raw_pcm in self._source.stream():
            if self._stop_evt.is_set():
                break
            for frame in resampler.feed(raw_pcm):
                if self._stop_evt.is_set():
                    break
                self._out_queue.put(frame)
        for frame in resampler.flush():
            self._out_queue.put(frame)


class _StreamResampler:
    """Stateful float32 → soxr → fixed-size PCM16 frames.

    Each source may emit PCM16 at a different rate / channel count. We
    buffer the resampled float32 stream and cut it into `frame_bytes`
    PCM16 chunks. The last partial frame is zero-padded.
    """

    def __init__(self, in_rate: int, in_channels: int, out_rate: int, out_channels: int) -> None:
        self._out_rate = out_rate
        self._out_channels = out_channels
        self._out_channels_resample = in_channels
        self._resampler = soxr.ResampleStream(
            in_rate, out_rate, in_channels, dtype="float32", quality="QQ"
        )
        self._frame_samples = max(1, out_rate * FRAME_MS // 1000)
        self._frame_bytes = self._frame_samples * out_channels * 2
        self._float_buffer = np.empty(0, dtype=np.float32)

    def feed(self, raw_pcm: bytes) -> list[bytes]:
        if not raw_pcm:
            return []
        array = np.frombuffer(raw_pcm, dtype=np.int16).astype(np.float32) / 32767.0
        if self._out_channels_resample != 1 and array.ndim == 1:
            array = array.reshape(-1, self._out_channels_resample)
        resampled = self._resampler.resample_chunk(array, last=False)
        if resampled.ndim == 2:
            resampled = resampled.mean(axis=1)
        self._float_buffer = np.concatenate([self._float_buffer, resampled.astype(np.float32)])
        return self._drain_frames()

    def flush(self) -> list[bytes]:
        try:
            tail = self._resampler.resample_chunk(
                np.empty((0, self._out_channels_resample), dtype=np.float32), last=True
            )
        except Exception:
            tail = np.empty(0, dtype=np.float32)
        if tail.ndim == 2:
            tail = tail.mean(axis=1)
        if tail.size:
            self._float_buffer = np.concatenate([self._float_buffer, tail.astype(np.float32)])
        frames = self._drain_frames()
        if self._float_buffer.size:
            frames.append(self._pad_frame(self._float_buffer))
            self._float_buffer = np.empty(0, dtype=np.float32)
        return frames

    def _drain_frames(self) -> list[bytes]:
        frames: list[bytes] = []
        needed = self._frame_samples
        while self._float_buffer.size >= needed:
            chunk = self._float_buffer[:needed]
            self._float_buffer = self._float_buffer[needed:]
            frames.append(self._encode(chunk))
        return frames

    def _pad_frame(self, partial: np.ndarray) -> bytes:
        if partial.size >= self._frame_samples:
            return self._encode(partial[: self._frame_samples])
        padded = np.zeros(self._frame_samples, dtype=np.float32)
        padded[: partial.size] = partial
        return self._encode(padded)

    def _encode(self, frame: np.ndarray) -> bytes:
        clipped = np.clip(frame, -1.0, 1.0)
        pcm = (clipped * 32767.0).astype(np.int16)
        return pcm.tobytes()
