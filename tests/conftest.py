from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from nina_core.config import (
    get_database_path,
    get_token_path,
    get_vault_path,
    initialize,
    read_token,
)
from nina_core.scheduler.service import SchedulerService


@pytest.fixture
def isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    config_dir = tmp_path / "nina-config"
    initialize(config_dir=config_dir, force=True)
    monkeypatch.setenv("NINA_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("NINA_TOKEN", read_token(get_token_path(config_dir)))
    monkeypatch.setenv("NINA_VAULT_PATH", str(get_vault_path(config_dir)))
    monkeypatch.setenv("NINA_DATABASE_PATH", str(get_database_path(config_dir)))
    return config_dir


@pytest.fixture
def auth_headers(isolated_config: Path) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {read_token(get_token_path(isolated_config))}",
        "Content-Type": "application/json",
    }


@pytest.fixture
def api_client(isolated_config: Path) -> Iterator[TestClient]:
    from nina_server.app import app

    scheduler = SchedulerService(str(get_database_path(isolated_config)))
    app.state.scheduler = scheduler
    with TestClient(app) as client:
        yield client
    scheduler.shutdown()
    if hasattr(app.state, "scheduler"):
        del app.state.scheduler
