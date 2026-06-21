"""Integration tests for the codex-backed `/codex/*` endpoints."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from nina_core.config.settings import CodexConfig
from nina_core.codex.password import ensure_password_file
from nina_core.codex.supervisor import CodexSupervisor

pytestmark = pytest.mark.integration


def _write_fake_codex_binary(tmp_path: Path, version: str = "0.3.1") -> Path:
    script = tmp_path / "fake-codex"
    script.write_text(
        "#!/usr/bin/env python3\n"
        "import json\n"
        "import sys\n"
        "\n"
        f"VERSION = '{version}'\n"
        "\n"
        "if '--version' in sys.argv:\n"
        "    print(VERSION)\n"
        "    raise SystemExit(0)\n"
        "if len(sys.argv) >= 2 and sys.argv[1] == 'exec':\n"
        "    if '--json' in sys.argv:\n"
        "        print(json.dumps({\"status\": \"ok\", \"prompt\": ' '.join(sys.argv[2:])[:10]}))\n"
        "    else:\n"
        "        print('execution complete')\n"
        "    raise SystemExit(0)\n"
        "raise SystemExit(0)\n"
    )
    script.chmod(0o755)
    return script


def _register_repository(api_client: TestClient, auth_headers: dict[str, str], path: Path) -> str:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", str(path)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    response = api_client.post(
        "/repositories",
        headers=auth_headers,
        json={"path": str(path), "name": path.name},
    )
    assert response.status_code == 200
    return response.json()["id"]


def _install_supervisor(api_client: TestClient, isolated_config: Path, binary: Path) -> CodexSupervisor:
    from nina_core.config import load_effective_config
    from nina_server import apply_runtime_config

    config = load_effective_config(isolated_config)
    ensure_password_file(isolated_config, "codex_password", force=True)
    config.codex = CodexConfig(  # type: ignore[assignment]
        enabled=True,
        binary_path=str(binary),
        host="127.0.0.1",
        port=5555,
        username="nina",
        password_ref="codex_password",
        startup_timeout_seconds=5.0,
        shutdown_timeout_seconds=2.0,
    )
    apply_runtime_config(api_client.app, isolated_config, config)

    supervisor = CodexSupervisor(isolated_config, config, isolated_config / "logs" / "codex.log")
    supervisor.start()
    api_client.app.state.codex = supervisor
    if hasattr(api_client.app.state, "runtime"):
        api_client.app.state.runtime.codex = supervisor
    return supervisor


def test_codex_status_returns_running_with_version(
    api_client: TestClient,
    auth_headers: dict[str, str],
    isolated_config: Path,
) -> None:
    binary = _write_fake_codex_binary(isolated_config)
    supervisor = _install_supervisor(api_client, isolated_config, binary)
    try:
        response = api_client.get("/codex/status", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["state"] == "running"
        assert data["version"] == "0.3.1"
        assert data["host"] == "127.0.0.1"
        assert data["port"] == 5555
    finally:
        supervisor.stop()


def test_codex_projects_returns_empty_list(
    api_client: TestClient,
    auth_headers: dict[str, str],
    isolated_config: Path,
) -> None:
    binary = _write_fake_codex_binary(isolated_config)
    supervisor = _install_supervisor(api_client, isolated_config, binary)
    try:
        response = api_client.get("/codex/projects", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []
    finally:
        supervisor.stop()


def test_codex_current_project_reports_not_supported(
    api_client: TestClient,
    auth_headers: dict[str, str],
    isolated_config: Path,
) -> None:
    binary = _write_fake_codex_binary(isolated_config)
    supervisor = _install_supervisor(api_client, isolated_config, binary)
    try:
        response = api_client.get("/codex/projects/current", headers=auth_headers)
        assert response.status_code == 502
        assert response.json()["detail"]
    finally:
        supervisor.stop()


def test_codex_health_proxies_to_codex_version(
    api_client: TestClient,
    auth_headers: dict[str, str],
    isolated_config: Path,
) -> None:
    binary = _write_fake_codex_binary(isolated_config)
    supervisor = _install_supervisor(api_client, isolated_config, binary)
    try:
        response = api_client.get("/codex/health", headers=auth_headers)
        assert response.status_code == 200
        payload = response.json()
        assert payload["healthy"] is True
        assert payload["version"] == "0.3.1"
    finally:
        supervisor.stop()


def test_codex_exec_route_forwards_to_codex(
    api_client: TestClient,
    auth_headers: dict[str, str],
    isolated_config: Path,
) -> None:
    binary = _write_fake_codex_binary(isolated_config)
    supervisor = _install_supervisor(api_client, isolated_config, binary)
    try:
        response = api_client.post(
            "/codex/exec",
            headers=auth_headers,
            json={"prompt": "hello codex", "json": True},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["exit_code"] == 0
        assert isinstance(payload["json"], dict)
        assert payload["json"]["status"] == "ok"
    finally:
        supervisor.stop()



def _write_task_codex_binary(tmp_path: Path) -> Path:
    script = tmp_path / "fake-task-codex"
    script.write_text(
        "#!/usr/bin/env python3\n"
        "import json\n"
        "import os\n"
        "import pathlib\n"
        "import sys\n"
        "\n"
        "if '--version' in sys.argv:\n"
        "    print('codex task fake 1.0')\n"
        "    raise SystemExit(0)\n"
        "if len(sys.argv) >= 2 and sys.argv[1] == 'exec':\n"
        "    task_type = os.environ.get('NINA_TASK_TYPE', 'unknown')\n"
        "    cwd = pathlib.Path.cwd()\n"
        "    (cwd / f'task-{task_type}.txt').write_text(f'completed {task_type}\\n')\n"
        "    message = 'Outcome: completed\\n'\n"
        "    if task_type == 'reviewing':\n"
        "        message += 'Decision: approved\\n'\n"
        "    message += f'Summary: completed {task_type}.\\n'\n"
        "    if '--output-last-message' in sys.argv:\n"
        "        pathlib.Path(sys.argv[sys.argv.index('--output-last-message') + 1]).write_text(message)\n"
        "    if '--json' in sys.argv:\n"
        "        print(json.dumps({'task_type': task_type, 'status': 'ok'}))\n"
        "    raise SystemExit(0)\n"
        "raise SystemExit(0)\n"
    )
    script.chmod(0o755)
    return script


def test_task_run_launches_codex_task_happy_path(
    api_client: TestClient,
    auth_headers: dict[str, str],
    isolated_config: Path,
) -> None:
    binary = _write_task_codex_binary(isolated_config)
    worktree = isolated_config / "agent-test-folder"
    repository_id = _register_repository(api_client, auth_headers, worktree)
    supervisor = _install_supervisor(api_client, isolated_config, binary)
    try:
        created = api_client.post(
            "/tasks",
            headers=auth_headers,
            json={
                "title": "Codex task happy path",
                "description": "Create task marker file.",
                "task_type": "coding",
                "auto_classify": False,
                "repository_id": repository_id,
            },
        )
        assert created.status_code == 200
        task_id = created.json()["id"]

        response = api_client.post(f"/tasks/{task_id}/run", headers=auth_headers)

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "completed"
        assert payload["output"]["task_type"] == "coding"
        assert payload["output"]["would_route_to"] == "codex:coding"
        assert (worktree / "task-coding.txt").read_text() == "completed coding\n"

        current = api_client.get(f"/tasks/{task_id}", headers=auth_headers)
        assert current.status_code == 200
        task = current.json()
        assert task["task_type"] == "coding"
        assert task["status"] == "working"
        assert task["repository_id"] == repository_id
        assert task["repository_path"] == str(worktree)
    finally:
        supervisor.stop()


def test_task_create_background_auto_run_queues_codex_task_happy_path(
    api_client: TestClient,
    auth_headers: dict[str, str],
    isolated_config: Path,
) -> None:
    binary = _write_task_codex_binary(isolated_config)
    worktree = isolated_config / "background-agent-test-folder"
    repository_id = _register_repository(api_client, auth_headers, worktree)
    supervisor = _install_supervisor(api_client, isolated_config, binary)
    try:
        created = api_client.post(
            "/tasks",
            headers=auth_headers,
            json={
                "title": "Background auto run Codex happy path",
                "description": "Create task marker file from background task create.",
                "task_type": "coding",
                "auto_classify": False,
                "auto_run": True,
                "auto_run_background": True,
                "repository_id": repository_id,
            },
        )

        assert created.status_code == 200
        task_id = created.json()["id"]
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if (worktree / "task-coding.txt").exists():
                break
            time.sleep(0.1)

        assert (worktree / "task-coding.txt").read_text() == "completed coding\n"
        current = api_client.get(f"/tasks/{task_id}", headers=auth_headers)
        assert current.status_code == 200
        assert current.json()["status"] == "working"
    finally:
        supervisor.stop()


def test_task_create_auto_run_launches_codex_task_happy_path(
    api_client: TestClient,
    auth_headers: dict[str, str],
    isolated_config: Path,
) -> None:
    binary = _write_task_codex_binary(isolated_config)
    worktree = isolated_config / "auto-run-agent-test-folder"
    repository_id = _register_repository(api_client, auth_headers, worktree)
    supervisor = _install_supervisor(api_client, isolated_config, binary)
    try:
        created = api_client.post(
            "/tasks",
            headers=auth_headers,
            json={
                "title": "Auto run Codex happy path",
                "description": "Create task marker file from one task create call.",
                "task_type": "coding",
                "auto_classify": False,
                "auto_run": True,
                "repository_id": repository_id,
            },
        )

        assert created.status_code == 200
        task = created.json()
        assert task["task_type"] == "coding"
        assert task["status"] == "working"
        assert task["repository_id"] == repository_id
        assert task["repository_path"] == str(worktree)
        assert (worktree / "task-coding.txt").read_text() == "completed coding\n"
    finally:
        supervisor.stop()
