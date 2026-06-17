"""Audio capture backends for the meetings recorder.

Each backend implements the `AudioSource` protocol from
`nina_core.meetings.recorder`. Backends are platform-specific; the factory
in `nina_core.meetings.recorder.make_audio_source` picks the right one.
"""

from .macos_process_tap import MACOS_PROCESS_TAP_MIN_VERSION, MacosProcessTapSource
from .soundcard_backend import (
    SoundcardBackend,
    list_loopback_devices,
    list_microphones,
)

__all__ = [
    "MACOS_PROCESS_TAP_MIN_VERSION",
    "MacosProcessTapSource",
    "SoundcardBackend",
    "list_loopback_devices",
    "list_microphones",
]
