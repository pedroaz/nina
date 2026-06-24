from pathlib import Path
from typing import Any, Mapping, Self, cast

import yaml
from pydantic import BaseModel, Field, field_validator


class LLMConfig(BaseModel):
    provider: str = "codex"
    model: str = "codex-cli"
    # Used only by local OpenAI-compatible runtimes such as Ollama, llama.cpp,
    # vLLM, or LM Studio. Codex CLI is the default AI integration.
    base_url: str | None = None

    @field_validator("provider")
    @classmethod
    def normalize_provider(cls, value: str) -> str:
        provider = (value or "codex").lower()
        return "codex" if provider in {"openai", "openai_web", "web"} else provider


class ResearchConfig(BaseModel):
    provider: str = "codex"
    model: str = "codex-cli"
    search_mode: str = "live"
    timeout_seconds: float = 600.0

    @field_validator("provider")
    @classmethod
    def normalize_provider(cls, value: str) -> str:
        provider = (value or "codex").lower()
        return "codex" if provider in {"openai", "openai_web", "web"} else provider

    @field_validator("search_mode")
    @classmethod
    def normalize_search_mode(cls, value: str) -> str:
        mode = (value or "live").lower()
        if mode not in {"live", "cached", "disabled"}:
            raise ValueError("research.search_mode must be one of: live, cached, disabled")
        return mode

    @field_validator("timeout_seconds")
    @classmethod
    def validate_timeout_seconds(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("research.timeout_seconds must be greater than zero")
        return value


class SchedulerConfig(BaseModel):
    daily_summary_time: str = "07:00"
    reindex_cron: str = "*/15 * * * *"


class SearchConfig(BaseModel):
    live_indexing: bool = True
    embedding_provider: str = "fastembed"
    embedding_model: str = "BAAI/bge-small-en-v1.5"


class TranscriptionConfig(BaseModel):
    backend: str = "local_whisper"
    model: str = "small"
    device: str = "cpu"
    compute_type: str = "int8"
    language: str | None = None


class MeetingsConfig(BaseModel):
    default_source: str = "mic"
    default_device: str | None = None
    auto_summarize: bool = False
    open_command: str = "auto"
    play_command: str = "xdg-open {path}"
    sample_rate: int = 48000
    channels: int = 1
    # Linear gain applied to every recording by default (e.g. 2.0 = +6 dB,
    # 4.0 = +12 dB). Useful when the system source volume is low
    # (PipeWire/PulseAudio sometimes defaults to a low capture volume).
    # Per-call `--gain` on `nina r` / `nina meeting record` still overrides.
    default_gain: float = 1.0
    auto_normalize: bool = True
    normalize_target_dbfs: float = -3.0
    noise_reduction: str = "off"


class VoiceConfig(BaseModel):
    global_hotkey_enabled: bool = False
    global_hotkey: str = "Ctrl+Alt+Space"
    insert_mode: str = "clipboard_paste"
    preserve_clipboard: bool = True


class CodexConfig(BaseModel):
    enabled: bool = True
    # Empty string means "use shutil.which('codex')". A user-set path
    # overrides the search.
    binary_path: str = ""
    host: str = "127.0.0.1"
    port: int = 5555
    username: str = "nina"
    # Filename (relative to $NINA_CONFIG_DIR) of the password file. The
    # actual password is read from disk at boot so the secret never ends
    # up in config.yaml.
    password_ref: str = "codex_password"
    startup_timeout_seconds: float = 10.0
    shutdown_timeout_seconds: float = 5.0


class NinaConfig(BaseModel):
    profile: str = "default"
    vault_path: str = Field(default="")
    database_path: str = Field(default="")
    daemon_host: str = "127.0.0.1"
    daemon_port: int = 8765
    llm: LLMConfig = Field(default_factory=LLMConfig)
    research: ResearchConfig = Field(default_factory=ResearchConfig)
    scheduler: SchedulerConfig = Field(default_factory=SchedulerConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)
    transcription: TranscriptionConfig = Field(default_factory=TranscriptionConfig)
    meetings: MeetingsConfig = Field(default_factory=MeetingsConfig)
    voice: VoiceConfig = Field(default_factory=VoiceConfig)
    codex: CodexConfig = Field(default_factory=CodexConfig)
    log_level: str = "INFO"

    @classmethod
    def load(cls, path: Path) -> Self:
        if path.exists():
            data: dict[str, Any] = yaml.safe_load(path.read_text()) or {}
            return cls(**data)
        return cls()

    def save(self, path: Path) -> None:
        path.write_text(
            yaml.safe_dump(self.model_dump(), default_flow_style=False, sort_keys=False)
        )

    def with_resolved_paths(self, config_dir: Path) -> Self:
        self.vault_path = _normalize_path(self.vault_path, config_dir / "vault", config_dir)
        self.database_path = _normalize_path(
            self.database_path,
            config_dir / "nina.db",
            config_dir,
        )
        return self


def _normalize_path(value: str, default: Path, config_dir: Path) -> str:
    path = Path(value).expanduser() if value else default
    if not path.is_absolute():
        path = config_dir / path
    return str(path)


def _deep_update(target: dict[str, Any], patch: Mapping[str, Any]) -> None:
    for key, value in patch.items():
        if isinstance(value, Mapping) and isinstance(target.get(key), dict):
            _deep_update(target[key], cast(Mapping[str, Any], value))
        else:
            target[key] = value


def merge_config(config: NinaConfig, patch: Mapping[str, Any], config_dir: Path) -> NinaConfig:
    data: dict[str, Any] = config.model_dump()
    _deep_update(data, patch)
    return NinaConfig(**data).with_resolved_paths(config_dir)
