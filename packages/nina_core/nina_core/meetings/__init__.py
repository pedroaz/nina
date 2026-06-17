from ._protocols import AudioSource, RecorderError
from .aligned_mixer import AlignedMixer
from .backends.macos_process_tap import MacosProcessTapSource
from .backends.soundcard_backend import (
    SoundcardBackend,
    list_loopback_devices,
    list_microphones,
)
from .manager import MeetingRecordingManager, RecordingRequest, RecordingSession
from .recorder import (
    NullAudioSource,
    apply_ffmpeg_noise_reduction,
    boost_wav,
    list_input_devices,
    make_audio_source,
    normalize_wav,
    peak_dbfs,
    record_wav,
)
from .service import MeetingService

__all__ = [
    "AlignedMixer",
    "AudioSource",
    "MacosProcessTapSource",
    "MeetingRecordingManager",
    "MeetingService",
    "NullAudioSource",
    "RecorderError",
    "RecordingRequest",
    "RecordingSession",
    "SoundcardBackend",
    "apply_ffmpeg_noise_reduction",
    "boost_wav",
    "list_input_devices",
    "list_loopback_devices",
    "list_microphones",
    "make_audio_source",
    "normalize_wav",
    "peak_dbfs",
    "record_wav",
]
