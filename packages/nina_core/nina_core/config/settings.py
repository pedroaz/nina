from pathlib import Path
from typing import Any, Mapping, Self

import yaml
from pydantic import BaseModel, Field


class LLMConfig(BaseModel):
    provider: str = "codex"
    model: str = "gpt-5"
    api_key: str | None = None


class SchedulerConfig(BaseModel):
    daily_summary_time: str = "07:00"
    reindex_cron: str = "*/15 * * * *"


class SearchConfig(BaseModel):
    live_indexing: bool = True
    embedding_provider: str = "fastembed"
    embedding_model: str = "BAAI/bge-small-en-v1.5"


class NinaConfig(BaseModel):
    profile: str = "default"
    vault_path: str = Field(default="")
    database_path: str = Field(default="")
    daemon_host: str = "127.0.0.1"
    daemon_port: int = 8765
    llm: LLMConfig = Field(default_factory=LLMConfig)
    scheduler: SchedulerConfig = Field(default_factory=SchedulerConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)
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
            _deep_update(target[key], value)
        else:
            target[key] = value


def merge_config(config: NinaConfig, patch: Mapping[str, Any], config_dir: Path) -> NinaConfig:
    data = config.model_dump()
    _deep_update(data, patch)
    return NinaConfig(**data).with_resolved_paths(config_dir)
