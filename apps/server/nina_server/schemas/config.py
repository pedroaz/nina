from __future__ import annotations

from pydantic import BaseModel


class LLMConfigResponse(BaseModel):
    provider: str
    model: str
    base_url: str | None = None


class ResearchConfigResponse(BaseModel):
    provider: str
    model: str
    search_mode: str
    timeout_seconds: float


class SchedulerConfigResponse(BaseModel):
    daily_summary_time: str


class TranscriptionConfigResponse(BaseModel):
    backend: str
    model: str
    device: str
    compute_type: str
    language: str | None = None


class MeetingsConfigResponse(BaseModel):
    default_source: str
    auto_summarize: bool
    sample_rate: int
    channels: int
    open_command: str
    play_command: str
    default_gain: float
    auto_normalize: bool
    normalize_target_dbfs: float
    noise_reduction: str


class VoiceConfigResponse(BaseModel):
    global_hotkey_enabled: bool
    global_hotkey: str
    insert_mode: str
    preserve_clipboard: bool


class CodexConfigResponse(BaseModel):
    enabled: bool
    binary_path: str
    host: str
    port: int
    username: str
    password_ref: str
    startup_timeout_seconds: float
    shutdown_timeout_seconds: float


class ConfigResponse(BaseModel):
    profile: str
    config_dir: str
    config_path: str
    vault_path: str
    database_path: str
    daemon_host: str
    daemon_port: int
    llm: LLMConfigResponse
    research: ResearchConfigResponse
    scheduler: SchedulerConfigResponse
    transcription: TranscriptionConfigResponse
    meetings: MeetingsConfigResponse
    voice: VoiceConfigResponse
    codex: CodexConfigResponse
    log_level: str


class LLMConfigUpdate(BaseModel):
    provider: str | None = None
    model: str | None = None
    base_url: str | None = None


class ResearchConfigUpdate(BaseModel):
    provider: str | None = None
    model: str | None = None
    search_mode: str | None = None
    timeout_seconds: float | None = None


class SchedulerConfigUpdate(BaseModel):
    daily_summary_time: str | None = None


class TranscriptionConfigUpdate(BaseModel):
    backend: str | None = None
    model: str | None = None
    device: str | None = None
    compute_type: str | None = None
    language: str | None = None


class MeetingsConfigUpdate(BaseModel):
    default_source: str | None = None
    auto_summarize: bool | None = None
    sample_rate: int | None = None
    channels: int | None = None
    open_command: str | None = None
    play_command: str | None = None
    default_gain: float | None = None
    auto_normalize: bool | None = None
    normalize_target_dbfs: float | None = None
    noise_reduction: str | None = None


class VoiceConfigUpdate(BaseModel):
    global_hotkey_enabled: bool | None = None
    global_hotkey: str | None = None
    insert_mode: str | None = None
    preserve_clipboard: bool | None = None


class CodexConfigUpdate(BaseModel):
    enabled: bool | None = None
    binary_path: str | None = None
    host: str | None = None
    port: int | None = None
    username: str | None = None
    password_ref: str | None = None
    startup_timeout_seconds: float | None = None
    shutdown_timeout_seconds: float | None = None


class ConfigUpdate(BaseModel):
    vault_path: str | None = None
    database_path: str | None = None
    daemon_host: str | None = None
    daemon_port: int | None = None
    log_level: str | None = None
    llm: LLMConfigUpdate | None = None
    research: ResearchConfigUpdate | None = None
    scheduler: SchedulerConfigUpdate | None = None
    transcription: TranscriptionConfigUpdate | None = None
    meetings: MeetingsConfigUpdate | None = None
    voice: VoiceConfigUpdate | None = None
    codex: CodexConfigUpdate | None = None
