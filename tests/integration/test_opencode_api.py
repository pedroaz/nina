"""Integration tests for the opencode supervisor and `/opencode/*` endpoints.

The tests boot a tiny in-process "opencode" HTTP server on a free port,
point the supervisor at it, and exercise the FastAPI routes through the
existing `TestClient` harness.
"""

from __future__ import annotations

import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from nina_core.config.settings import OpencodeConfig
from nina_core.opencode.password import ensure_password_file
from nina_core.opencode.supervisor import OpencodeSupervisor

pytestmark = pytest.mark.integration


class _FakeOpencodeHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - http.server API
        if self.path == "/global/health":
            payload = b'{"healthy": true, "version": "0.0.0-test"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if self.path == "/project":
            payload = b'[{"id":"abc123","worktree":"/tmp/fake","vcs":"git","time":{"created":1,"updated":2},"sandboxes":[]}]'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if self.path == "/project/current":
            payload = b'{"id":"abc123","worktree":"/tmp/fake","vcs":"git","time":{"created":1,"updated":2},"sandboxes":[]}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, *_args: object) -> None:
        return


@pytest.fixture
def fake_opencode_server() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = ThreadingHTTPServer(("127.0.0.1", port), _FakeOpencodeHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield port
    finally:
        server.shutdown()


def _install_supervisor(
    api_client: TestClient, isolated_config: Path, port: int
) -> OpencodeSupervisor:
    from nina_core.config import load_effective_config
    from nina_server.app import app, apply_runtime_config

    config = load_effective_config(isolated_config)
    ensure_password_file(isolated_config, "opencode_password", force=True)
    # Build a settings object that overrides the opencode block for tests.
    config.opencode = OpencodeConfig(  # type: ignore[assignment]
        enabled=True,
        binary_path="",
        host="127.0.0.1",
        port=port,
        username="nina",
        password_ref="opencode_password",
        startup_timeout_seconds=5.0,
        shutdown_timeout_seconds=2.0,
    )
    apply_runtime_config(app, isolated_config, config)

    log_path = isolated_config / "logs" / "opencode.log"
    supervisor = OpencodeSupervisor(isolated_config, config, log_path)
    supervisor.start()
    app.state.opencode = supervisor
    return supervisor


def test_opencode_status_returns_running_with_version(
    api_client: TestClient,
    auth_headers: dict[str, str],
    isolated_config: Path,
    fake_opencode_server: int,
) -> None:
    supervisor = _install_supervisor(api_client, isolated_config, fake_opencode_server)
    try:
        # Give the supervisor's startup poll a moment to mark the child healthy.
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            response = api_client.get("/opencode/status", headers=auth_headers)
            assert response.status_code == 200
            data = response.json()
            if data["state"] == "running":
                break
            time.sleep(0.05)
        else:
            pytest.fail(f"supervisor never became running: {data}")
        assert data["state"] == "running"
        assert data["version"] == "0.0.0-test"
        assert data["host"] == "127.0.0.1"
        assert data["port"] == fake_opencode_server
    finally:
        supervisor.stop()


def test_opencode_projects_returns_server_payload(
    api_client: TestClient,
    auth_headers: dict[str, str],
    isolated_config: Path,
    fake_opencode_server: int,
) -> None:
    supervisor = _install_supervisor(api_client, isolated_config, fake_opencode_server)
    try:
        # Wait for the supervisor to be ready.
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            response = api_client.get("/opencode/status", headers=auth_headers)
            if response.json()["state"] == "running":
                break
            time.sleep(0.05)

        response = api_client.get("/opencode/projects", headers=auth_headers)
        assert response.status_code == 200
        projects = response.json()
        assert len(projects) == 1
        assert projects[0]["id"] == "abc123"
        assert projects[0]["worktree"] == "/tmp/fake"
        assert projects[0]["vcs"] == "git"
        assert projects[0]["time"]["created"] == 1

        current = api_client.get("/opencode/projects/current", headers=auth_headers)
        assert current.status_code == 200
        assert current.json()["id"] == "abc123"
    finally:
        supervisor.stop()


def test_opencode_health_proxies_global_health(
    api_client: TestClient,
    auth_headers: dict[str, str],
    isolated_config: Path,
    fake_opencode_server: int,
) -> None:
    supervisor = _install_supervisor(api_client, isolated_config, fake_opencode_server)
    try:
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            response = api_client.get("/opencode/status", headers=auth_headers)
            if response.json()["state"] == "running":
                break
            time.sleep(0.05)
        response = api_client.get("/opencode/health", headers=auth_headers)
        assert response.status_code == 200
        payload = response.json()
        assert payload["healthy"] is True
        assert payload["version"] == "0.0.0-test"
    finally:
        supervisor.stop()
