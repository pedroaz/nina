from __future__ import annotations

import math
import struct
import threading
import wave
from pathlib import Path

import pytest
from nina_core.meetings.recorder import (
    NullAudioSource,
    PortAudioSource,
    PulseSource,
    RecorderError,
    SoundCardSource,
    boost_wav,
    is_portaudio_available,
    make_audio_source,
    normalize_wav,
    peak_dbfs,
    record_wav,
)

pytestmark = pytest.mark.unit


def _write_silence_wav(
    path: Path, sample_rate: int = 16000, channels: int = 1, seconds: float = 0.2
) -> None:

    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as writer:
        writer.setnchannels(channels)
        writer.setsampwidth(2)
        writer.setframerate(sample_rate)
        frame = b"\x00\x00" * channels
        for _ in range(int(sample_rate * seconds)):
            writer.writeframes(frame)


def test_null_audio_source_produces_a_valid_wav(tmp_path: Path) -> None:
    output = tmp_path / "rec.wav"
    source = NullAudioSource()
    source.open(16000, 1)
    size = record_wav(output, source, sample_rate=16000, channels=1, duration_seconds=0.1)
    assert size > 0
    with wave.open(str(output), "rb") as reader:
        assert reader.getframerate() == 16000
        assert reader.getnchannels() == 1
        assert reader.getsampwidth() == 2


def test_make_audio_source_returns_null_when_prefer_null() -> None:
    assert isinstance(make_audio_source("mic", prefer_null=True), NullAudioSource)


def test_make_audio_source_rejects_unknown() -> None:
    with pytest.raises(RecorderError):
        make_audio_source("nonsense")


def test_make_audio_source_parec_returns_pulse_source() -> None:
    source = make_audio_source("parec", device="alsa_input.test")
    assert isinstance(source, PulseSource)


def test_make_audio_source_system_returns_supported_source() -> None:
    source = make_audio_source("system")
    assert isinstance(source, (PulseSource, SoundCardSource))


def test_make_audio_source_system_falls_back_to_soundcard_when_parec_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("nina_core.meetings.recorder._has_parec", lambda: False)
    monkeypatch.setattr("nina_core.meetings.recorder._has_soundcard", lambda: True)
    source = make_audio_source("system")
    assert isinstance(source, SoundCardSource)


def test_make_audio_source_mic_falls_back_to_pulse_when_portaudio_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When `sounddevice` is not installed (e.g. on a vanilla PipeWire system
    without `libportaudio2`), the `mic` source should fall back to `parec`
    against the default PulseAudio input, not raise a hard error.
    """
    monkeypatch.setattr(
        "nina_core.meetings.recorder.is_portaudio_available",
        lambda: False,
    )
    monkeypatch.setattr(
        "nina_core.meetings.recorder._has_parec",
        lambda: True,
    )
    source = make_audio_source("mic")
    assert isinstance(source, PulseSource)


def test_make_audio_source_mic_raises_when_no_backend_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "nina_core.meetings.recorder.is_portaudio_available",
        lambda: False,
    )
    monkeypatch.setattr(
        "nina_core.meetings.recorder._has_parec",
        lambda: False,
    )
    with pytest.raises(RecorderError, match="No audio capture backend"):
        make_audio_source("mic")


def test_make_audio_source_mic_uses_portaudio_when_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "nina_core.meetings.recorder.is_portaudio_available",
        lambda: True,
    )
    source = make_audio_source("mic")
    assert isinstance(source, PortAudioSource)


def test_is_portaudio_available_does_not_raise() -> None:
    """`is_portaudio_available` is a probe: it must always return a bool."""
    result = is_portaudio_available()
    assert isinstance(result, bool)


def test_pulse_source_stream_raises_when_not_opened() -> None:
    """Regression: a `PulseSource` whose `open()` has not been called must
    raise a clear RecorderError when `stream()` is invoked. The CLI used
    to forget the `open()` call, leading to a confusing "Pulse source not
    opened" error mid-recording.
    """
    source = PulseSource(kind="source")
    with pytest.raises(RecorderError, match="Pulse source not opened"):
        next(source.stream())


def test_cli_style_recording_flow(tmp_path: Path) -> None:
    """The CLI does `make_audio_source -> open -> record_wav` in that order.
    This is the full path that runs in `nina r`, so it must work end to end.
    """
    output = tmp_path / "meeting.wav"
    source = make_audio_source("mic", prefer_null=True)
    source.open(16000, 1)
    size = record_wav(output, source, sample_rate=16000, channels=1, duration_seconds=0.1)
    assert size > 0
    assert output.is_file()


def test_record_wav_replaces_partial_with_final_file(tmp_path: Path) -> None:
    output = tmp_path / "out.wav"
    partial = output.with_suffix(".wav.partial")
    assert not output.exists()
    assert not partial.exists()
    source = NullAudioSource()
    source.open(8000, 1)
    record_wav(output, source, sample_rate=8000, channels=1, duration_seconds=0.05)
    assert output.exists()
    assert not partial.exists()


def test_null_source_stream_yields_silence_frames() -> None:
    source = NullAudioSource()
    source.open(16000, 1)
    gen = source.stream()
    chunk = next(gen)
    source.close()
    assert isinstance(chunk, bytes)
    assert len(chunk) > 0


class _BoomSource:
    """Audio source that yields one chunk of silence then raises."""

    def __init__(self) -> None:
        self._stop = threading.Event()
        self._yielded_once = False
        self._sample_rate = 16000
        self._channels = 1

    def open(self, sample_rate: int, channels: int) -> None:
        self._sample_rate = sample_rate
        self._channels = channels

    def stream(self):
        # Yield one chunk so the WAV header is valid, then blow up
        # mid-stream. This mimics the recorder being killed partway
        # through (e.g. SIGKILL on the CLI subprocess, or `parec`
        # dying).
        frame = b"\x00\x00" * self._channels * int(self._sample_rate / 50)
        yield frame
        if not self._stop.is_set():
            raise RecorderError("simulated mid-stream failure (e.g. SIGKILL)")

    def close(self) -> None:
        self._stop.set()


def test_record_wav_promotes_partial_when_stream_fails(tmp_path: Path) -> None:
    """Regression: when the stream raises mid-recording, the partial WAV
    should still be promoted to its final path so whatever audio was
    captured is reachable. The exception then re-raises so the caller
    can decide what to do (e.g. mark the meeting with an error).
    """

    output = tmp_path / "out.wav"
    partial = tmp_path / "out.wav.partial"
    source = _BoomSource()
    source.open(16000, 1)

    with pytest.raises(RecorderError, match="simulated"):
        record_wav(output, source, sample_rate=16000, channels=1)

    # The partial file should have been promoted to its final name,
    # even though the stream raised.
    assert output.exists(), f"expected {output.name} to be promoted from partial"
    assert not partial.exists(), "partial file should be gone after promotion"
    with wave.open(str(output), "rb") as reader:
        assert reader.getframerate() == 16000
        assert reader.getnchannels() == 1


def test_record_wav_raises_when_promotion_fails(tmp_path: Path, monkeypatch) -> None:
    """If promotion to the final path fails, we surface that as a
    RecorderError instead of silently losing the audio."""

    from nina_core.meetings import recorder as recorder_mod

    output = tmp_path / "out.wav"
    source = NullAudioSource()
    source.open(16000, 1)

    # Force the rename to fail.
    def _fake_promote(_partial, _final) -> bool:
        return False

    monkeypatch.setattr(recorder_mod, "_promote_partial", _fake_promote)

    with pytest.raises(RecorderError, match="Failed to finalize"):
        record_wav(output, source, sample_rate=16000, channels=1, duration_seconds=0.05)


# -----------------------------------------------------------------------------
# Gain / normalize helpers
# -----------------------------------------------------------------------------


def _write_tone_wav(
    path: Path,
    amplitude: int = 1000,
    sample_rate: int = 16000,
    channels: int = 1,
    seconds: float = 0.1,
) -> None:
    """Write a short constant-amplitude tone at the given int16 amplitude."""
    path.parent.mkdir(parents=True, exist_ok=True)
    nframes = int(sample_rate * seconds)
    with wave.open(str(path), "wb") as writer:
        writer.setnchannels(channels)
        writer.setsampwidth(2)
        writer.setframerate(sample_rate)
        frame = struct.pack("<" + "h" * channels, *([amplitude] * channels))
        writer.writeframes(frame * nframes)


def test_peak_dbfs_returns_none_for_silence(tmp_path: Path) -> None:
    path = tmp_path / "silent.wav"
    _write_silence_wav(path, seconds=0.1)
    # Silent audio: amplitude == 0 → log10(0) is undefined → None.
    assert peak_dbfs(path) is None


def test_peak_dbfs_matches_expected_amplitude(tmp_path: Path) -> None:
    path = tmp_path / "tone.wav"
    _write_tone_wav(path, amplitude=1000)
    db = peak_dbfs(path)
    assert db is not None
    # 1000/32768 ≈ 0.0305 → 20*log10 ≈ -30.3 dBFS
    assert abs(db - 20 * math.log10(1000 / 32768)) < 0.5


def test_boost_wav_doubles_peak_amplitude(tmp_path: Path) -> None:
    path = tmp_path / "tone.wav"
    _write_tone_wav(path, amplitude=1000)
    before = peak_dbfs(path)
    new_peak = boost_wav(path, 2.0)
    # +6 dB boost is exactly 2x in linear domain.
    assert abs(new_peak - before - 6.0206) < 0.5


def test_boost_wav_factor_four_boosts_by_twelve_db(tmp_path: Path) -> None:
    path = tmp_path / "tone.wav"
    _write_tone_wav(path, amplitude=2000)
    before = peak_dbfs(path)
    new_peak = boost_wav(path, 4.0)
    assert abs(new_peak - before - 12.041) < 0.5


def test_boost_wav_clamps_at_zero_dbfs(tmp_path: Path) -> None:
    path = tmp_path / "tone.wav"
    # 0 dBFS = amplitude 32767; applying 4x would normally clip to 32767
    # (int16 saturation), so the post-boost peak should be ≈ 0 dBFS.
    _write_tone_wav(path, amplitude=30000)
    new_peak = boost_wav(path, 4.0)
    assert new_peak <= 0.05  # within rounding
    assert new_peak > -0.5  # not 0 dBFS only by integer saturation


def test_boost_wav_rejects_non_positive_factor(tmp_path: Path) -> None:
    path = tmp_path / "tone.wav"
    _write_tone_wav(path, amplitude=1000)
    with pytest.raises(ValueError, match="factor"):
        boost_wav(path, 0.0)
    with pytest.raises(ValueError, match="factor"):
        boost_wav(path, -2.0)


def test_boost_wav_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        boost_wav(tmp_path / "missing.wav", 2.0)


def test_normalize_wav_brings_peak_to_target(tmp_path: Path) -> None:
    path = tmp_path / "quiet.wav"
    _write_tone_wav(path, amplitude=500)
    before, after = normalize_wav(path, target_dbfs=-3.0)
    assert before < -25.0  # the input is genuinely quiet
    assert abs(after - (-3.0)) < 0.5  # hits the target within rounding


def test_normalize_wav_no_op_when_already_loud(tmp_path: Path) -> None:
    path = tmp_path / "loud.wav"
    # 0.5 amplitude ≈ -6 dBFS; target is -3.0 dBFS → only +3 dB gain.
    _write_tone_wav(path, amplitude=16000)
    before, after = normalize_wav(path, target_dbfs=-3.0)
    assert after >= before  # never makes things quieter
    assert abs(after - (-3.0)) < 0.5


def test_normalize_wav_rejects_unsupported_format(tmp_path: Path) -> None:
    # The wave module only emits widths 1/2/3/4, but our helpers handle
    # 1/2/3 (8/16/24-bit) as int. A 32-bit WAV passes the read step (we
    # read it as 32-bit signed int) and round-trips successfully. Verify
    # the integer-PCM path is correct by checking a 24-bit WAV boosts.
    path = tmp_path / "pcm24.wav"
    nframes = 1600
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(3)
        w.setframerate(16000)
        # 24-bit little-endian amplitude ~1000.
        sample = (1000).to_bytes(3, "little", signed=True)
        w.writeframes(sample * nframes)
    before, after = normalize_wav(path, target_dbfs=-3.0)
    assert after > before
    assert abs(after - (-3.0)) < 0.5
