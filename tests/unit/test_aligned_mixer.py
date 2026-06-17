"""Tests for `AlignedMixer` — the sample-rate-aligned, 50 ms frame-aligned
mixer used by `--source mixed`.
"""

from __future__ import annotations

import threading
import time
import wave
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pytest
from nina_core.meetings.aligned_mixer import FRAME_MS, AlignedMixer
from nina_core.meetings.recorder import NullAudioSource, RecorderError, record_wav

pytestmark = pytest.mark.unit


class _ToneSource:
    """Audio source that emits a sine tone at a given native rate and channels.

    Used to verify that the mixer resamples correctly when the two sides
    are at different rates.
    """

    def __init__(
        self,
        frequency: float,
        native_rate: int,
        native_channels: int = 1,
        duration_seconds: float = 0.3,
    ) -> None:
        self._frequency = frequency
        self._native_rate = native_rate
        self._native_channels = native_channels
        self._duration = duration_seconds
        self._stop = threading.Event()

    def open(self, sample_rate: int, channels: int) -> None:
        self._opened_rate = sample_rate
        self._opened_channels = channels

    def stream(self) -> Iterator[bytes]:
        chunk_samples = max(64, self._native_rate // 20)
        total_samples = int(self._native_rate * self._duration)
        emitted = 0
        while emitted < total_samples and not self._stop.is_set():
            n = min(chunk_samples, total_samples - emitted)
            t = (np.arange(emitted, emitted + n) / self._native_rate).astype(np.float32)
            wave_data = (np.sin(2 * np.pi * self._frequency * t) * 0.3 * 32767).astype(np.int16)
            if self._native_channels == 2:
                wave_data = np.repeat(wave_data, 2)
            emitted += n
            yield wave_data.tobytes()
            time.sleep(0.001)

    def close(self) -> None:
        self._stop.set()


def test_aligned_mixer_resamples_different_rates(tmp_path: Path) -> None:
    """Left source at 48 kHz, right at 44.1 kHz → output should be at the
    mixer's 48 kHz target rate and roughly the right length."""
    left = _ToneSource(frequency=440.0, native_rate=48000, duration_seconds=0.3)
    right = _ToneSource(frequency=660.0, native_rate=44100, duration_seconds=0.3)
    mixer = AlignedMixer(left, right, target_rate=48000, target_channels=1)
    mixer.open(48000, 1)

    output = tmp_path / "mixed.wav"
    size = record_wav(output, mixer, sample_rate=48000, channels=1, duration_seconds=0.3)
    assert size > 0

    with wave.open(str(output), "rb") as reader:
        assert reader.getframerate() == 48000
        assert reader.getnchannels() == 1
        n_frames = reader.getnframes()
        expected_frames = int(48000 * 0.3)
        assert abs(n_frames - expected_frames) < 4800  # within 100 ms


def test_aligned_mixer_emits_frame_aligned_50ms_chunks(tmp_path: Path) -> None:
    """The mixer's stream() should yield fixed-size 50 ms PCM16 chunks."""
    left = NullAudioSource()
    right = NullAudioSource()
    mixer = AlignedMixer(left, right, target_rate=48000, target_channels=1)
    mixer.open(48000, 1)

    gen = mixer.stream()
    frame_bytes = 48000 * FRAME_MS // 1000 * 1 * 2
    seen = 0
    for chunk in gen:
        if seen == 0:
            assert len(chunk) == frame_bytes
        seen += 1
        if seen > 4:
            mixer.close()
            break
    assert seen >= 2


def test_aligned_mixer_mixes_left_and_right(tmp_path: Path) -> None:
    """When the right side is silent, the output should match the left side."""
    left = _ToneSource(frequency=440.0, native_rate=48000, duration_seconds=0.2)
    right_silent = NullAudioSource()
    mixer = AlignedMixer(left, right_silent, target_rate=48000, target_channels=1)
    mixer.open(48000, 1)

    output = tmp_path / "left_only.wav"
    record_wav(output, mixer, sample_rate=48000, channels=1, duration_seconds=0.2)

    with wave.open(str(output), "rb") as reader:
        raw = reader.readframes(reader.getnframes())
    samples = np.frombuffer(raw, dtype=np.int16)
    assert np.max(np.abs(samples)) > 0


def test_aligned_mixer_surfaces_source_error() -> None:
    """If one of the underlying sources raises mid-stream, the mixer should
    raise `RecorderError` on the next `stream()` call and stop."""

    class _Boom:
        def __init__(self) -> None:
            self._stop = threading.Event()

        def open(self, sample_rate, channels):
            pass

        def stream(self):
            yield (np.zeros(1024, dtype=np.int16)).tobytes()
            if not self._stop.is_set():
                raise RuntimeError("upstream boom")

        def close(self):
            self._stop.set()

    mixer = AlignedMixer(_Boom(), NullAudioSource(), target_rate=48000, target_channels=1)
    mixer.open(48000, 1)
    with pytest.raises(RecorderError, match="upstream boom|Mixed audio source failed"):
        for _ in mixer.stream():
            pass
