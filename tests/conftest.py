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
from nina_core.tasks.service import _drain_classification_threads


@pytest.fixture
def isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    config_dir = tmp_path / "nina-config"
    initialize(config_dir=config_dir, force=True)
    monkeypatch.setenv("NINA_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("NINA_TOKEN", read_token(get_token_path(config_dir)))
    # Disable background classification threads; tests use synchronous
    # classification so the daemon-driven flow is deterministic.
    monkeypatch.setenv("NINA_BACKGROUND_CLASSIFY", "0")
    return config_dir


@pytest.fixture
def auth_headers(isolated_config: Path) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {read_token(get_token_path(isolated_config))}",
        "Content-Type": "application/json",
    }


@pytest.fixture
def fake_llm(monkeypatch: pytest.MonkeyPatch) -> FakeProvider:
    """A shared `FakeProvider` that the daemon's LLMService will use.

    Tests that exercise workflows (which spawn background threads and create
    fresh `LLMService` instances) can `queue_text`/`queue_tool_calls` on this
    provider to drive the LLM path deterministically.
    """

    fake = FakeProvider()
    monkeypatch.setattr(LLMService, "_build_provider", lambda self: fake)
    return fake


@pytest.fixture
def api_client(
    isolated_config: Path,
    fake_llm: FakeProvider,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[TestClient]:
    from nina_server.app import app, apply_runtime_config

    # Apply the active config so endpoints read vault/db paths from
    # `NinaConfig` instead of hidden env vars. The CLI's `nina config` PATCH
    # endpoint also writes through this path.
    apply_runtime_config(app, isolated_config, load_effective_config(isolated_config))

    scheduler = SchedulerService(str(get_database_path(isolated_config)))
    app.state.scheduler = scheduler
    with TestClient(app) as client:
        yield client
    # Drain any classification threads spawned by the test before tearing
    # down the monkeypatched `LLMService._build_provider`. Without this
    # drain, late-completing threads would try to call the real provider
    # after the patch is reverted, which hits the real network.
    _drain_classification_threads(timeout=2.0)
    scheduler.shutdown()
    if hasattr(app.state, "scheduler"):
        del app.state.scheduler
    if hasattr(app.state, "meeting_recorder"):
        del app.state.meeting_recorder
    if hasattr(app.state, "config"):
        del app.state.config
