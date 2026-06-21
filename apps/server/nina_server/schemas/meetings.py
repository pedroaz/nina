from __future__ import annotations

from pydantic import BaseModel


class MeetingCreate(BaseModel):
    title: str
    source: str = "mic"
    device_name: str | None = None
    sample_rate: int = 16000
    channels: int = 1
    audio_format: str = "wav"


class MeetingRecord(BaseModel):
    title: str
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


class MeetingStop(BaseModel):
    duration_seconds: int | None = None
    size_bytes: int | None = None
    error: str | None = None
