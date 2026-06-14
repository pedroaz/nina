from pathlib import Path
from typing import Any, Self

import yaml
from pydantic import BaseModel, Field


class LLMConfig(BaseModel):
    provider: str = "codex"
    model: str = "gpt-5"
    api_key: str | None = None


class SchedulerConfig(BaseModel):
    daily_summary_time: str = "07:00"


class NinaConfig(BaseModel):
    profile: str = "default"
    vault_path: str = Field(default="")
    database_path: str = Field(default="")
    daemon_host: str = "127.0.0.1"
    daemon_port: int = 8765
    llm: LLMConfig = Field(default_factory=LLMConfig)
    scheduler: SchedulerConfig = Field(default_factory=SchedulerConfig)
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
        if not self.vault_path:
            self.vault_path = str(config_dir / "vault")
        if not self.database_path:
            self.database_path = str(config_dir / "nina.db")
        return self
