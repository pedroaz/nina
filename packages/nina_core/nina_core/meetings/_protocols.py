"""Audio source protocol and shared exceptions.

Defined in their own module to avoid a circular import between
`recorder.py` and `aligned_mixer.py` (the mixer needs the protocol, and
the recorder needs the mixer for the `--source mixed` factory branch).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol


class AudioSource(Protocol):
    """Anything that can be opened, streamed, and closed."""

    def open(self, sample_rate: int, channels: int) -> None: ...
    def stream(self) -> Iterator[bytes]: ...
    def close(self) -> None: ...


class RecorderError(RuntimeError):
    """Raised when audio capture cannot start or fails mid-recording."""
