from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from nina_core.config import load_effective_config
from nina_server import apply_runtime_config, create_app
from nina_server.runtime import DaemonRuntime


def test_create_app_returns_fresh_instances_and_registers_core_routes() -> None:
    first = create_app()
    second = create_app()

    assert first is not second

    paths = {route.path for route in first.routes if getattr(route, "path", None)}
    assert {"/health", "/config", "/tasks", "/meetings", "/voice", "/jobs"}.issubset(paths)


def test_daemon_route_inventory_is_stable() -> None:
    app = create_app()

    actual = {
        (method, route.path)
        for route in app.routes
        if getattr(route, "path", "").startswith("/")
        for method in getattr(route, "methods", set()) - {"HEAD", "OPTIONS"}
        if route.path not in {"/docs", "/docs/oauth2-redirect", "/openapi.json", "/redoc"}
    }

    expected = {
        ("DELETE", "/integrations/{name}/credentials"),
        ("DELETE", "/meetings/{meeting_id}"),
        ("DELETE", "/repositories/{repository_id}"),
        ("DELETE", "/tasks/{task_id}"),
        ("DELETE", "/tickets/{ticket_id}"),
        ("GET", "/capabilities"),
        ("GET", "/config"),
        ("GET", "/health"),
        ("GET", "/integrations"),
        ("GET", "/integrations/{name}"),
        ("GET", "/integrations/{name}/credentials"),
        ("GET", "/integrations/{name}/tests"),
        ("GET", "/job-runs"),
        ("GET", "/jobs"),
        ("GET", "/llm/interactions"),
        ("GET", "/logs/daemon"),
        ("GET", "/meetings"),
        ("GET", "/meetings-devices"),
        ("GET", "/meetings/devices"),
        ("GET", "/meetings/{meeting_id}"),
        ("GET", "/meetings/{meeting_id}/transcript"),
        ("GET", "/notes"),
        ("GET", "/notes/{path:path}"),
        ("GET", "/repositories"),
        ("GET", "/repositories/{repository_id}"),
        ("GET", "/repositories/{repository_id}/worktrees"),
        ("GET", "/codex/health"),
        ("GET", "/codex/projects"),
        ("GET", "/codex/projects/current"),
        ("POST", "/codex/exec"),
        ("GET", "/codex/status"),
        ("GET", "/sessions"),
        ("GET", "/sessions/{session_id}"),
        ("GET", "/status"),
        ("GET", "/tasks"),
        ("GET", "/tasks/grouped-by-type"),
        ("GET", "/tasks/{task_id}"),
        ("GET", "/tasks/{task_id}/codex-logs"),
        ("GET", "/tickets"),
        ("GET", "/tickets/{ticket_id}"),
        ("GET", "/voice"),
        ("GET", "/voice/active"),
        ("GET", "/voice/transcriptions"),
        ("DELETE", "/voice/transcriptions"),
        ("GET", "/voice/{capture_id}"),
        ("GET", "/workflow-runs"),
        ("GET", "/workflow-runs/{run_id}"),
        ("GET", "/workflows"),
        ("PATCH", "/config"),
        ("PATCH", "/jobs/{job_name}"),
        ("PATCH", "/notes/{path:path}"),
        ("PATCH", "/tasks/{task_id}"),
        ("PATCH", "/tickets/{ticket_id}"),
        ("POST", "/ask"),
        ("POST", "/codex/events"),
        ("POST", "/integrations/{name}/test"),
        ("POST", "/jobs"),
        ("POST", "/jobs/{job_name}/run"),
        ("POST", "/llm/complete"),
        ("POST", "/meetings"),
        ("POST", "/meetings/record"),
        ("POST", "/meetings/{meeting_id}/pipeline"),
        ("POST", "/meetings/{meeting_id}/stop"),
        ("POST", "/notes"),
        ("POST", "/repositories"),
        ("POST", "/research/run"),
        ("POST", "/search"),
        ("POST", "/search/open"),
        ("POST", "/search/reindex"),
        ("POST", "/sessions"),
        ("POST", "/sessions/{session_id}/cancel"),
        ("POST", "/sessions/{session_id}/clear-cancel"),
        ("POST", "/sessions/{session_id}/messages"),
        ("POST", "/tasks"),
        ("POST", "/tasks/{task_id}/archive"),
        ("POST", "/tasks/{task_id}/classify"),
        ("POST", "/tasks/{task_id}/run"),
        ("POST", "/tasks/{task_id}/unarchive"),
        ("POST", "/tickets"),
        ("POST", "/tickets/{ticket_id}/classify"),
        ("POST", "/tickets/{ticket_id}/run"),
        ("POST", "/voice/record"),
        ("POST", "/voice/{capture_id}/stop"),
        ("POST", "/voice/{capture_id}/transcribe"),
        ("POST", "/workflows/{workflow_name}/run"),
        ("PUT", "/integrations/{name}/credentials"),
    }

    assert actual == expected


def test_health_is_public_and_other_routes_require_auth(isolated_config: Path) -> None:
    app = create_app()
    apply_runtime_config(app, isolated_config, load_effective_config(isolated_config))

    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/config").status_code == 401
        assert client.get("/status").status_code == 401


def test_apply_runtime_config_attaches_runtime_state(isolated_config: Path) -> None:
    app = create_app()
    config = load_effective_config(isolated_config)

    resolved = apply_runtime_config(app, isolated_config, config)

    assert app.state.config == resolved
    assert isinstance(app.state.runtime, DaemonRuntime)
    assert app.state.config_dir == isolated_config
    assert app.state.database.db_path == resolved.database_path
    assert app.state.token


def test_runtime_reconfigure_rebinds_database_and_vault(isolated_config: Path) -> None:
    app = create_app()
    config = load_effective_config(isolated_config)
    resolved = apply_runtime_config(app, isolated_config, config)
    runtime = app.state.runtime

    updated = resolved.model_copy(deep=True)
    updated.database_path = str(isolated_config.parent / "reconfigured.db")
    updated.vault_path = str(isolated_config.parent / "reconfigured-vault")

    runtime.reconfigure(isolated_config, updated)

    assert app.state.config.database_path == updated.database_path
    assert app.state.database.db_path == updated.database_path
    assert (Path(updated.vault_path) / "Tasks").exists()
    assert (Path(updated.vault_path) / "System" / "Archived").exists()
