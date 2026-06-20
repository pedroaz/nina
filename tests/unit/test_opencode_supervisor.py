"""Unit tests for the opencode process supervisor.

The supervisor spawns an external `opencode serve` child, so these tests
use a tiny stand-in binary written to a temp file. On success, the script
opens a port and serves `GET /global/health` so the supervisor can mark
the child healthy.
"""

from __future__ import annotations

import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from nina_core.config import NinaConfig
from nina_core.opencode import OpencodeSupervisor
from nina_core.opencode.models import STATE_NOT_INSTALLED, STATE_RUNNING, STATE_STOPPED
from nina_core.opencode.password import ensure_password_file


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - http.server API
        if self.path == "/global/health":
            payload = b'{"healthy": true, "version": "1.0.0-test"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *_args: object) -> None:  # silence test output
        return


def _start_fake_opencode_server() -> tuple[ThreadingHTTPServer, int]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _HealthHandler)
    port = server.server_address[1]
    import threading

    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, port


def _write_fake_opencode_binary(tmp_path: Path, port: int) -> Path:
    """Write a tiny Python script that emulates `opencode serve` for tests.

    The HTTP server that the supervisor health-polls is started by the
    `_start_fake_opencode_server` fixture (so it can be torn down cleanly).
    The "binary" itself is just a script that sleeps — the supervisor's
    health probe is the only thing it needs to keep alive.
    """

    script = tmp_path / "fake-opencode"
    script.write_text(
        "#!/usr/bin/env python3\n"
        "import signal\n"
        "import sys\n"
        "import time\n"
        "\n"
        "for i, arg in enumerate(sys.argv):\n"
        "    if arg == '--port' and i + 1 < len(sys.argv):\n"
        "        # Accept the flag so the supervisor's argv matches the\n"
        "        # real opencode CLI. We don't actually open a port here.\n"
        "        pass\n"
        "\n"
        "def _term(_signum, _frame):\n"
        "    sys.exit(0)\n"
        "\n"
        "signal.signal(signal.SIGTERM, _term)\n"
        "while True:\n"
        "    time.sleep(60)\n"
    )
    script.chmod(0o755)
    return script


@pytest.fixture
def fake_opencode(tmp_path: Path) -> tuple[Path, int]:
    server, port = _start_fake_opencode_server()
    binary = _write_fake_opencode_binary(tmp_path, port)
    yield binary, port
    server.shutdown()


def _make_config(tmp_path: Path, port: int) -> NinaConfig:
    ensure_password_file(tmp_path, "opencode_password", force=True)
    return NinaConfig(
        profile="default",
        vault_path=str(tmp_path / "vault"),
        database_path=str(tmp_path / "nina.db"),
        daemon_host="127.0.0.1",
        daemon_port=8765,
        opencode=NinaConfig.model_fields["opencode"].default_factory(),  # type: ignore[attr-defined]
    ).with_resolved_paths(tmp_path)


def test_supervisor_marks_running_when_health_responds(
    tmp_path: Path, fake_opencode: tuple[Path, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    binary, port = fake_opencode
    # Build a config with our port and binary path.
    from nina_core.config.settings import OpencodeConfig

    config = NinaConfig(
        profile="default",
        vault_path=str(tmp_path / "vault"),
        database_path=str(tmp_path / "nina.db"),
        daemon_host="127.0.0.1",
        daemon_port=8765,
        opencode=OpencodeConfig(
            enabled=True,
            binary_path=str(binary),
            host="127.0.0.1",
            port=port,
            username="nina",
            password_ref="opencode_password",
            startup_timeout_seconds=5.0,
            shutdown_timeout_seconds=2.0,
        ),
    )
    # vault directory needs to exist for any side effect, even though
    # supervisor doesn't touch it directly.
    (tmp_path / "vault").mkdir(parents=True, exist_ok=True)
    ensure_password_file(tmp_path, "opencode_password", force=True)
    log_path = tmp_path / "logs" / "opencode.log"
    supervisor = OpencodeSupervisor(tmp_path, config, log_path)
    try:
        supervisor.start()
        assert supervisor.state == STATE_RUNNING, (
            f"expected running, got {supervisor.state} ({supervisor._last_error})"
        )
        status = supervisor.status()
        assert status.state == STATE_RUNNING
        assert status.version == "1.0.0-test"
        assert status.host == "127.0.0.1"
        assert status.port == port
    finally:
        supervisor.stop()
    assert supervisor.state == STATE_STOPPED


def test_supervisor_warns_when_binary_missing(tmp_path: Path) -> None:
    from nina_core.config.settings import OpencodeConfig

    config = NinaConfig(
        profile="default",
        vault_path=str(tmp_path / "vault"),
        database_path=str(tmp_path / "nina.db"),
        daemon_host="127.0.0.1",
        daemon_port=8765,
        opencode=OpencodeConfig(
            enabled=True,
            binary_path=str(tmp_path / "does-not-exist"),
            host="127.0.0.1",
            port=4096,
            username="nina",
            password_ref="opencode_password",
            startup_timeout_seconds=1.0,
            shutdown_timeout_seconds=1.0,
        ),
    )
    (tmp_path / "vault").mkdir(parents=True, exist_ok=True)
    ensure_password_file(tmp_path, "opencode_password", force=True)
    log_path = tmp_path / "logs" / "opencode.log"
    supervisor = OpencodeSupervisor(tmp_path, config, log_path)
    supervisor.start()
    assert supervisor.state == STATE_NOT_INSTALLED
    assert supervisor._last_error  # type: ignore[attr-defined]
    supervisor.stop()


def test_supervisor_disabled_does_not_spawn(tmp_path: Path) -> None:
    from nina_core.config.settings import OpencodeConfig

    config = NinaConfig(
        profile="default",
        vault_path=str(tmp_path / "vault"),
        database_path=str(tmp_path / "nina.db"),
        daemon_host="127.0.0.1",
        daemon_port=8765,
        opencode=OpencodeConfig(
            enabled=False,
            binary_path="",
            host="127.0.0.1",
            port=4096,
            username="nina",
            password_ref="opencode_password",
            startup_timeout_seconds=1.0,
            shutdown_timeout_seconds=1.0,
        ),
    )
    (tmp_path / "vault").mkdir(parents=True, exist_ok=True)
    log_path = tmp_path / "logs" / "opencode.log"
    supervisor = OpencodeSupervisor(tmp_path, config, log_path)
    supervisor.start()
    from nina_core.opencode.models import STATE_DISABLED

    assert supervisor.state == STATE_DISABLED
    supervisor.stop()
