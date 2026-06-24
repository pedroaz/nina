from __future__ import annotations

from pydantic import BaseModel


class VoiceRecord(BaseModel):
    title: str = ""
    source: str | None = None
    device: str | None = None
    mic_device: str | None = None
    system_device: str | None = None
    sample_rate: int | None = None
    channels: int | None = None
    duration_seconds: int | None = None
    gain: float | None = None
    auto_normalize: bool | None = None
    normalize_target_dbfs: float | None = None
    noise_reduction: str | None = None


class VoiceStop(BaseModel):
    duration_seconds: int | None = None
    size_bytes: int | None = None
    error: str | None = None


class VoiceTranscribe(BaseModel):
    save_note: bool = False
