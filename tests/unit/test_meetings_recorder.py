from __future__ import annotations

import math
import struct
import threading
import wave
from pathlib import Path

import pytest
from nina_core.meetings.aligned_mixer import AlignedMixer
from nina_core.meetings.backends import (
    MacosProcessTapSource,
    SoundcardBackend,
    list_loopback_devices,
)
from nina_core.meetings.recorder import (
    NullAudioSource,
    RecorderError,
    boost_wav,
    list_input_devices,
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


# -----------------------------------------------------------------------------
# AudioSource + record_wav
# -----------------------------------------------------------------------------


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


def test_make_audio_source_mic_returns_soundcard_backend() -> None:
    """The mic path always goes through the cross-platform `soundcard` library."""
    source = make_audio_source("mic")
    assert isinstance(source, SoundcardBackend)
    assert source._kind == "mic"


def test_make_audio_source_system_on_linux_returns_soundcard_loopback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """On Linux, system audio is captured via the soundcard loopback (PulseAudio monitor)."""
    monkeypatch.setattr("nina_core.meetings.recorder.sys.platform", "linux")
    monkeypatch.setattr("nina_core.meetings.recorder._try_macos_process_tap", lambda: None)
    source = make_audio_source("system")
    assert isinstance(source, SoundcardBackend)
    assert source._kind == "loopback"


def test_make_audio_source_system_on_windows_returns_soundcard_loopback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """On Windows, system audio is captured via soundcard loopback (WASAPI)."""
    monkeypatch.setattr("nina_core.meetings.recorder.sys.platform", "win32")
    monkeypatch.setattr("nina_core.meetings.recorder._try_macos_process_tap", lambda: None)
    source = make_audio_source("system")
    assert isinstance(source, SoundcardBackend)
    assert source._kind == "loopback"


def test_make_audio_source_system_on_macos_uses_process_tap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """On macOS, the factory prefers the Core Audio Process Tap (no BlackHole)."""
    monkeypatch.setattr("nina_core.meetings.recorder.sys.platform", "darwin")

    fake_tap = MacosProcessTapSource()
    monkeypatch.setattr("nina_core.meetings.recorder._try_macos_process_tap", lambda: fake_tap)

    source = make_audio_source("system")
    assert source is fake_tap


def test_make_audio_source_system_falls_back_to_soundcard_on_old_macos(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the Process Tap isn't available (older macOS / missing PyObjC), fall back to soundcard."""
    monkeypatch.setattr("nina_core.meetings.recorder.sys.platform", "darwin")
    monkeypatch.setattr("nina_core.meetings.recorder._try_macos_process_tap", lambda: None)
    source = make_audio_source("system")
    assert isinstance(source, SoundcardBackend)
    assert source._kind == "loopback"


def test_make_audio_source_mixed_uses_aligned_mixer(monkeypatch: pytest.MonkeyPatch) -> None:
    """`mixed` wraps the mic and system sources in `AlignedMixer` with a 48 kHz target."""
    import nina_core.meetings.recorder as rec_mod

    fake_mic = NullAudioSource()
    fake_system = NullAudioSource()

    class _StubBackend:
        def __init__(self, device=None, *, kind="mic"):
            self.device = device
            self.kind = kind
            self._calls = (kind,)

    def _fake_soundcard(device=None, *, kind="mic"):
        if kind == "mic":
            return fake_mic
        return fake_system

    monkeypatch.setattr(rec_mod, "SoundcardBackend", _fake_soundcard)

    source = rec_mod.make_audio_source("mixed")
    assert isinstance(source, AlignedMixer)
    assert source._target_rate == 48000
    assert source._target_channels == 1
    assert source._left is fake_mic
    assert source._right is fake_system


def test_make_audio_source_parec_raises() -> None:
    """`parec` is no longer a public source — users use `--device` to target a specific soundcard."""
    with pytest.raises(RecorderError, match="Unknown audio source"):
        make_audio_source("parec")


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
        self._sample_rate = 16000
        self._channels = 1

    def open(self, sample_rate: int, channels: int) -> None:
        self._sample_rate = sample_rate
        self._channels = channels

    def stream(self):
        frame = b"\x00\x00" * self._channels * int(self._sample_rate / 50)
        yield frame
        if not self._stop.is_set():
            raise RecorderError("simulated mid-stream failure (e.g. SIGKILL)")

    def close(self) -> None:
        self._stop.set()


def test_record_wav_promotes_partial_when_stream_fails(tmp_path: Path) -> None:
    output = tmp_path / "out.wav"
    partial = tmp_path / "out.wav.partial"
    source = _BoomSource()
    source.open(16000, 1)

    with pytest.raises(RecorderError, match="simulated"):
        record_wav(output, source, sample_rate=16000, channels=1)

    assert output.exists(), f"expected {output.name} to be promoted from partial"
    assert not partial.exists(), "partial file should be gone after promotion"
    with wave.open(str(output), "rb") as reader:
        assert reader.getframerate() == 16000
        assert reader.getnchannels() == 1


def test_record_wav_raises_when_promotion_fails(tmp_path: Path, monkeypatch) -> None:
    from nina_core.meetings import recorder as recorder_mod

    output = tmp_path / "out.wav"
    source = NullAudioSource()
    source.open(16000, 1)

    monkeypatch.setattr(recorder_mod, "_promote_partial", lambda _p, _f: False)

    with pytest.raises(RecorderError, match="Failed to finalize"):
        record_wav(output, source, sample_rate=16000, channels=1, duration_seconds=0.05)


# -----------------------------------------------------------------------------
# Device listing
# -----------------------------------------------------------------------------


def test_list_input_devices_returns_a_list() -> None:
    devices = list_input_devices()
    assert isinstance(devices, list)


def test_list_loopback_devices_returns_a_list() -> None:
    devices = list_loopback_devices()
    assert isinstance(devices, list)


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
    assert peak_dbfs(path) is None


def test_peak_dbfs_matches_expected_amplitude(tmp_path: Path) -> None:
    path = tmp_path / "tone.wav"
    _write_tone_wav(path, amplitude=1000)
    db = peak_dbfs(path)
    assert db is not None
    assert abs(db - 20 * math.log10(1000 / 32768)) < 0.5


def test_boost_wav_doubles_peak_amplitude(tmp_path: Path) -> None:
    path = tmp_path / "tone.wav"
    _write_tone_wav(path, amplitude=1000)
    before = peak_dbfs(path)
    new_peak = boost_wav(path, 2.0)
    assert abs(new_peak - before - 6.0206) < 0.5


def test_boost_wav_factor_four_boosts_by_twelve_db(tmp_path: Path) -> None:
    path = tmp_path / "tone.wav"
    _write_tone_wav(path, amplitude=2000)
    before = peak_dbfs(path)
    new_peak = boost_wav(path, 4.0)
    assert abs(new_peak - before - 12.041) < 0.5


def test_boost_wav_clamps_at_zero_dbfs(tmp_path: Path) -> None:
    path = tmp_path / "tone.wav"
    _write_tone_wav(path, amplitude=30000)
    new_peak = boost_wav(path, 4.0)
    assert new_peak <= 0.05
    assert new_peak > -0.5


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
    assert before < -25.0
    assert abs(after - (-3.0)) < 0.5


def test_normalize_wav_no_op_when_already_loud(tmp_path: Path) -> None:
    path = tmp_path / "loud.wav"
    _write_tone_wav(path, amplitude=16000)
    before, after = normalize_wav(path, target_dbfs=-3.0)
    assert after >= before
    assert abs(after - (-3.0)) < 0.5


def test_normalize_wav_handles_24bit(tmp_path: Path) -> None:
    path = tmp_path / "pcm24.wav"
    nframes = 1600
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setnchannels(1)
        w.setsampwidth(3)
        w.setframerate(16000)
        sample = (1000).to_bytes(3, "little", signed=True)
        w.writeframes(sample * nframes)
    before, after = normalize_wav(path, target_dbfs=-3.0)
    assert after > before
    assert abs(after - (-3.0)) < 0.5
