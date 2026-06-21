"""Unit tests for the Codex CLI supervisor."""

from __future__ import annotations

from pathlib import Path

from nina_core.config import NinaConfig
from nina_core.config.settings import CodexConfig
from nina_core.codex import CodexSupervisor
from nina_core.codex.models import STATE_DISABLED, STATE_NOT_INSTALLED, STATE_RUNNING, STATE_STOPPED
from nina_core.codex.password import ensure_password_file


def _write_fake_codex_binary(tmp_path: Path, version: str = "1.2.3") -> Path:
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
        "if 'exec' in sys.argv:\n"
        "    # Simulate codex exec mode.\n"
        "    print('ok')\n"
        "    if '--json' in sys.argv:\n"
        "        print(json.dumps({'result': 'done'}))\n"
        "    raise SystemExit(0)\n"
        "raise SystemExit(0)\n"
    )
    script.chmod(0o755)
    return script


def _build_config(tmp_path: Path, *, binary_path: str, enabled: bool = True) -> NinaConfig:
    (tmp_path / "vault").mkdir(parents=True, exist_ok=True)
    ensure_password_file(tmp_path, "codex_password", force=True)
    return NinaConfig(
        profile="default",
        vault_path=str(tmp_path / "vault"),
        database_path=str(tmp_path / "nina.db"),
        daemon_host="127.0.0.1",
        daemon_port=8765,
        codex=CodexConfig(
            enabled=enabled,
            binary_path=binary_path,
            host="127.0.0.1",
            port=5555,
            username="nina",
            password_ref="codex_password",
            startup_timeout_seconds=1.0,
            shutdown_timeout_seconds=1.0,
        ),
    )


def test_supervisor_marks_running_when_codex_is_callable(tmp_path: Path) -> None:
    binary = _write_fake_codex_binary(tmp_path)
    config = _build_config(tmp_path, binary_path=str(binary))
    supervisor = CodexSupervisor(tmp_path, config, tmp_path / "logs" / "codex.log")

    supervisor.start()

    assert supervisor.state == STATE_RUNNING
    status = supervisor.status()
    assert status.state == STATE_RUNNING
    assert status.version == "1.2.3"
    assert status.host == "127.0.0.1"
    assert status.port == 5555

    supervisor.stop()
    assert supervisor.state == STATE_STOPPED


def test_supervisor_warns_when_binary_missing(tmp_path: Path) -> None:
    config = _build_config(tmp_path, binary_path=str(tmp_path / "does-not-exist"))
    supervisor = CodexSupervisor(tmp_path, config, tmp_path / "logs" / "codex.log")

    supervisor.start()

    assert supervisor.state == STATE_NOT_INSTALLED
    assert supervisor._last_error  # type: ignore[attr-defined]


def test_supervisor_disabled_does_not_run(tmp_path: Path) -> None:
    config = _build_config(tmp_path, binary_path="", enabled=False)
    supervisor = CodexSupervisor(tmp_path, config, tmp_path / "logs" / "codex.log")

    supervisor.start()

    assert supervisor.state == STATE_DISABLED
    assert supervisor._state == STATE_DISABLED
    supervisor.stop()
    assert supervisor.state == STATE_STOPPED
