from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from nina_core.config import (
    get_database_path,
    get_token_path,
    initialize,
    load_effective_config,
    read_token,
)
from nina_core.llm.provider import FakeProvider, LLMService
from nina_core.scheduler.service import SchedulerService


@pytest.fixture
def isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    config_dir = tmp_path / "nina-config"
    initialize(config_dir=config_dir, force=True)
    monkeypatch.setenv("NINA_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("NINA_TOKEN", read_token(get_token_path(config_dir)))
    return config_dir


@pytest.fixture
def auth_headers(isolated_config: Path) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {read_token(get_token_path(isolated_config))}",
        "Content-Type": "application/json",
    }


@pytest.fixture
def api_client(isolated_config: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    from nina_server.app import app, apply_runtime_config

    # Apply the active config so endpoints read vault/db paths from
    # `NinaConfig` instead of hidden env vars. The CLI's `nina config` PATCH
    # endpoint also writes through this path.
    apply_runtime_config(app, isolated_config, load_effective_config(isolated_config))

    # Force the FakeProvider for tests; the real Codex/OpenAI providers
    # would require real credentials.
    fake = FakeProvider()
    monkeypatch.setattr(LLMService, "_build_provider", lambda self: fake)

    scheduler = SchedulerService(str(get_database_path(isolated_config)))
    app.state.scheduler = scheduler
    with TestClient(app) as client:
        yield client
    scheduler.shutdown()
    if hasattr(app.state, "scheduler"):
        del app.state.scheduler
    if hasattr(app.state, "meeting_recorder"):
        del app.state.meeting_recorder
    if hasattr(app.state, "config"):
        del app.state.config
