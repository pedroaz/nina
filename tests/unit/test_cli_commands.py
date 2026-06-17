from __future__ import annotations

import json
from typing import Any

import pytest
import yaml
from nina_cli import config_commands as config_module
from nina_cli import main as main_module
from nina_cli.api import api_base
from nina_cli.main import app
from nina_core.config import (
    get_token_path,
    initialize,
    load_effective_config,
    read_token,
)
from typer.testing import CliRunner


class FakeResponse:
    def __init__(self, payload: Any) -> None:
        self.payload = payload

    def json(self) -> Any:
        return self.payload


class FakeHealthResponse:
    def __init__(self, payload: Any) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> Any:
        return self.payload


runner = CliRunner()


def _patch_popen_capture(monkeypatch: pytest.MonkeyPatch, captured: dict[str, Any]) -> None:
    """Patch `subprocess.Popen` to capture the argv into `captured["cmd"]`
    and return a sentinel object that doesn't actually spawn a process.

    Used by the `nina config edit` tests so they don't launch a real
    editor or hang waiting for one to close.
    """

    class _Sentinel:
        pass

    def _fake_popen(cmd: list[str], *args: Any, **kwargs: Any) -> _Sentinel:
        captured["cmd"] = list(cmd)
        return _Sentinel()

    monkeypatch.setattr(config_module.subprocess, "Popen", _fake_popen)


def test_task_move_calls_kanban_move_endpoint(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    calls: list[tuple[str, str, dict[str, Any]]] = []

    def fake_request(method: str, path: str, **kwargs: Any) -> FakeResponse:
        calls.append((method, path, kwargs))
        return FakeResponse({"id": "task-1", "kanban_column": "Doing", "kanban_position": 2})

    monkeypatch.setattr("nina_cli.task_commands.request", fake_request)

    result = runner.invoke(app, ["task", "move", "task-1", "--column", "Doing", "--position", "2"])

    assert result.exit_code == 0
    assert calls == [
        (
            "POST",
            "/kanban/move",
            {"json": {"task_id": "task-1", "to_column": "Doing", "to_position": 2}},
        )
    ]
    assert "Moved task task-1 to Doing:2" in result.stdout


def test_job_create_and_run_call_expected_endpoints(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    calls: list[tuple[str, str, dict[str, Any]]] = []

    def fake_request(method: str, path: str, **kwargs: Any) -> FakeResponse:
        calls.append((method, path, kwargs))
        if path == "/jobs":
            return FakeResponse({"name": "daily", "enabled": True})
        return FakeResponse({"id": "run-1", "job_name": "daily", "status": "completed"})

    monkeypatch.setattr("nina_cli.job_commands.request", fake_request)

    create = runner.invoke(
        app,
        [
            "job",
            "create",
            "daily",
            "--schedule",
            "0 7 * * *",
            "--workflow",
            "summarize-last-day",
        ],
    )
    run = runner.invoke(app, ["job", "run", "daily"])

    assert create.exit_code == 0
    assert run.exit_code == 0
    assert calls == [
        (
            "POST",
            "/jobs",
            {
                "json": {
                    "name": "daily",
                    "workflow_name": "summarize-last-day",
                    "schedule": "0 7 * * *",
                    "enabled": True,
                }
            },
        ),
        ("POST", "/jobs/daily/run", {}),
    ]
    assert "Saved job daily" in create.stdout
    assert "Ran job daily -> completed (run-1)" in run.stdout


def test_ask_calls_ask_endpoint(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    calls: list[tuple[str, str, dict[str, Any]]] = []

    def fake_request(method: str, path: str, **kwargs: Any) -> FakeResponse:
        calls.append((method, path, kwargs))
        return FakeResponse(
            {
                "answer": "Use Codex OAuth through the CLI.",
                "sources": [{"path": "Research/codex.md"}],
            }
        )

    monkeypatch.setattr("nina_cli.main.request", fake_request)

    result = runner.invoke(app, ["ask", "How is Codex OAuth used?", "--limit", "3"])

    assert result.exit_code == 0
    assert calls == [
        (
            "POST",
            "/ask",
            {"json": {"question": "How is Codex OAuth used?", "limit": 3}},
        )
    ]
    assert "Use Codex OAuth through the CLI." in result.stdout
    assert "Research/codex.md" in result.stdout


def test_llm_test_calls_complete_endpoint(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    calls: list[tuple[str, str, dict[str, Any]]] = []

    def fake_request(method: str, path: str, **kwargs: Any) -> FakeResponse:
        calls.append((method, path, kwargs))
        return FakeResponse({"provider": "openai", "model": "gpt-5.4-mini", "response": "auth ok"})

    monkeypatch.setattr("nina_cli.llm_commands.request", fake_request)

    result = runner.invoke(app, ["llm", "test", "Reply with auth ok", "--model", "gpt-5.4-mini"])

    assert result.exit_code == 0
    assert calls == [
        (
            "POST",
            "/llm/complete",
            {
                "json": {
                    "purpose": "cli_test",
                    "prompt": "Reply with auth ok",
                    "model": "gpt-5.4-mini",
                }
            },
        )
    ]
    assert "Provider: openai" in result.stdout
    assert "Model: gpt-5.4-mini" in result.stdout
    assert "auth ok" in result.stdout


def test_chat_test_uses_session_create_and_message_flow(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    calls: list[tuple[str, str, dict[str, Any]]] = []

    def fake_request(method: str, path: str, **kwargs: Any) -> FakeResponse:
        calls.append((method, path, kwargs))
        if path == "/sessions?mode=chat":
            return FakeResponse([])
        if path == "/sessions":
            return FakeResponse(
                {"id": "session-1", "mode": "chat", "title": "Chat", "messages": []}
            )
        if path == "/sessions/session-1/messages":
            return FakeResponse(
                {
                    "session": {"id": "session-1", "mode": "chat", "title": "Chat", "messages": []},
                    "assistant": {"content": "chat ok"},
                    "sources": [{"title": "Note", "path": "Research/note.md"}],
                }
            )
        raise AssertionError(f"unexpected path: {path}")

    monkeypatch.setattr("nina_cli.chat_commands.request", fake_request)

    result = runner.invoke(app, ["chat", "test", "Reply with chat ok"])

    assert result.exit_code == 0
    assert calls == [
        ("GET", "/sessions?mode=chat", {}),
        ("POST", "/sessions", {"json": {"mode": "chat", "title": "Chat"}}),
        ("POST", "/sessions/session-1/messages", {"json": {"content": "Reply with chat ok"}}),
    ]
    assert "Session: session-1" in result.stdout
    assert "chat ok" in result.stdout
    assert "Sources:" in result.stdout
    assert "Research/note.md" in result.stdout


def test_status_reports_running_daemon_and_configuration_paths(
    monkeypatch, isolated_config
) -> None:  # type: ignore[no-untyped-def]
    (isolated_config / "daemon.pid").write_text("4321")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-api-key")
    monkeypatch.setattr(main_module, "_process_exists", lambda pid: True)
    monkeypatch.setattr(
        main_module.httpx,
        "get",
        lambda *args, **kwargs: FakeHealthResponse({"status": "ok"}),
    )
    monkeypatch.setattr(
        main_module,
        "codex_auth_status",
        lambda: type(
            "AuthStatus",
            (),
            {
                "connected": True,
                "account_id": "acc-123",
                "expires_at": 1893456000000,
                "detail": None,
            },
        )(),
    )
    monkeypatch.setattr(config_module, "_sync_daemon", lambda *args, **kwargs: False)

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    assert "Daemon running (pid 4321)" in result.stdout
    assert "Health: ok" in result.stdout
    assert "LLM auth: OpenAI API key configured" in result.stdout
    assert "LLM provider: openai" in result.stdout
    assert "Transcription:" in result.stdout
    assert "Meeting pipeline:" in result.stdout
    assert "Configuration paths:" in result.stdout
    assert "Config dir:" in result.stdout
    assert "Config file:" in result.stdout
    assert "Token:" in result.stdout
    assert "Database:" in result.stdout
    assert "Vault:" in result.stdout
    assert "Log:" in result.stdout
    assert "PID:" in result.stdout
    assert "LLM base URL:" in result.stdout


def test_logs_reads_daemon_log_file(isolated_config) -> None:  # type: ignore[no-untyped-def]
    log_path = isolated_config / "logs" / "daemon.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("first line\nsecond line\nthird line\n")

    result = runner.invoke(app, ["logs"])

    assert result.exit_code == 0
    assert f"Log file: {log_path}" in result.stdout
    assert "first line" in result.stdout
    assert "second line" in result.stdout
    assert "third line" in result.stdout


def test_setup_python_prints_sys_executable() -> None:
    result = runner.invoke(app, ["setup", "python"])
    assert result.exit_code == 0
    # The test runner uses the same Python as the pytest process.
    import sys as _sys

    assert _sys.executable in result.stdout


def test_setup_transcription_calls_uv_pip_install(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`nina setup transcription` shells out to `uv pip install` against the
    Python the nina shim is running on, and verifies the module is importable
    afterwards. Mock both the subprocess call and the import check.
    """
    from nina_cli import setup_commands as setup_module

    called: list[list[str]] = []

    def fake_call(cmd: list[str]) -> int:
        called.append(list(cmd))
        return 0

    monkeypatch.setattr(setup_module.shutil, "which", lambda name: "/usr/bin/uv")
    monkeypatch.setattr(setup_module.subprocess, "call", fake_call)
    # The success path imports faster_whisper; ensure it looks installed.
    monkeypatch.setitem(__import__("sys").modules, "faster_whisper", object())

    result = runner.invoke(app, ["setup", "transcription"])

    assert result.exit_code == 0, result.stdout
    assert called
    cmd = called[0]
    # The command must pin --python to the nina Python (sys.executable).
    assert "--python" in cmd
    assert cmd[cmd.index("--python") + 1] == __import__("sys").executable
    assert "faster-whisper" in cmd
    assert "ready" in result.stdout


def test_setup_transcription_surfaces_install_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from nina_cli import setup_commands as setup_module

    monkeypatch.setattr(setup_module.shutil, "which", lambda name: "/usr/bin/uv")
    # Simulate `uv pip install` returning a non-zero exit code.
    monkeypatch.setattr(setup_module.subprocess, "call", lambda cmd: 1)

    result = runner.invoke(app, ["setup", "transcription"])
    assert result.exit_code != 0
    assert "Install failed" in result.stdout
    assert "uv pip install" in result.stdout


def test_setup_default_runs_unified_installer(monkeypatch: pytest.MonkeyPatch) -> None:
    from nina_cli import setup_commands as setup_module

    called: dict[str, object] = {}

    monkeypatch.setattr(
        setup_module, "setup_runtime", lambda python=None: called.setdefault("ok", True)
    )

    result = runner.invoke(app, ["setup"])

    assert result.exit_code == 0, result.stdout
    assert called == {"ok": True}


def test_status_reports_offline_daemon_and_configuration_paths(
    monkeypatch, isolated_config
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(config_module, "_sync_daemon", lambda *args, **kwargs: False)
    monkeypatch.setattr(
        main_module.httpx,
        "get",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("health should not be called")
        ),
    )
    monkeypatch.setattr(
        main_module,
        "codex_auth_status",
        lambda: type(
            "AuthStatus",
            (),
            {
                "connected": False,
                "account_id": None,
                "expires_at": None,
                "detail": "Codex auth file not found",
            },
        )(),
    )

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    assert "Daemon not running" in result.stdout
    assert "Health: offline" in result.stdout
    assert "LLM auth: disconnected (OPENAI_API_KEY is not set in the environment)" in result.stdout
    assert "LLM provider: openai" in result.stdout
    assert "Warnings:" in result.stdout
    assert "Configuration paths:" in result.stdout
    assert "Config dir:" in result.stdout


def test_config_open_launches_vs_code(monkeypatch: pytest.MonkeyPatch, isolated_config) -> None:  # type: ignore[no-untyped-def]
    captured: dict[str, Any] = {}
    _patch_popen_capture(monkeypatch, captured)
    monkeypatch.setattr(
        config_module.shutil, "which", lambda name: "/usr/bin/code" if name == "code" else None
    )

    result = runner.invoke(app, ["config", "open"])

    assert result.exit_code == 0, result.stdout
    assert captured["cmd"] == ["code", str(isolated_config)]


def test_uninstall_removes_install_root_and_config(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:  # type: ignore[no-untyped-def]
    install_root = tmp_path / "nina-root"
    launcher_dir = tmp_path / "launcher"
    config_dir = install_root / "default"
    vault_dir = config_dir / "vault"
    (config_dir / "logs").mkdir(parents=True, exist_ok=True)
    vault_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.yaml").write_text("llm:\n  provider: openai\n")
    (config_dir / "token").write_text("token")
    (config_dir / "nina.db").write_text("db")
    (config_dir / "daemon.pid").write_text("4321")
    (launcher_dir).mkdir(parents=True, exist_ok=True)
    (launcher_dir / "nina").write_text("launcher")

    monkeypatch.setattr(main_module, "get_config_dir", lambda profile="default": config_dir)
    monkeypatch.setattr(main_module, "_default_launcher_dir", lambda: launcher_dir)
    monkeypatch.setenv("NINA_INSTALL_ROOT", str(install_root))
    monkeypatch.setenv("NINA_LAUNCHER_DIR", str(launcher_dir))
    monkeypatch.setattr(main_module, "_read_pid", lambda path: 4321)
    monkeypatch.setattr(main_module, "_process_exists", lambda pid: False)
    monkeypatch.setattr(main_module, "_terminate_process", lambda pid: None)

    result = runner.invoke(app, ["uninstall"])

    assert result.exit_code == 0, result.stdout
    assert not install_root.exists()
    assert not (launcher_dir / "nina").exists()


def test_api_base_prefers_runtime_state(monkeypatch, isolated_config) -> None:  # type: ignore[no-untyped-def]
    (isolated_config / "daemon.json").write_text(
        json.dumps(
            {
                "profile": "default",
                "config_dir": str(isolated_config),
                "daemon_host": "10.0.0.5",
                "daemon_port": 9123,
            }
        )
    )

    assert api_base() == "http://10.0.0.5:9123"


def test_config_vault_command_updates_config_and_vault_structure(
    monkeypatch, isolated_config
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(
        config_module.httpx, "patch", lambda *args, **kwargs: FakeHealthResponse({})
    )
    custom_vault = isolated_config.parent / "custom-vault"

    result = runner.invoke(app, ["config", "vault", str(custom_vault)])

    assert result.exit_code == 0
    config = load_effective_config(isolated_config)
    assert config.vault_path == str(custom_vault)
    assert (custom_vault / "Projects").exists()
    assert (custom_vault / "System" / "Deleted").exists()
    assert "Vault path:" in result.stdout


def test_config_database_command_updates_config_and_creates_storage(
    monkeypatch, isolated_config
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(
        config_module.httpx, "patch", lambda *args, **kwargs: FakeHealthResponse({})
    )
    custom_db = isolated_config.parent / "custom-nina.db"

    result = runner.invoke(app, ["config", "database", str(custom_db)])

    assert result.exit_code == 0
    config = load_effective_config(isolated_config)
    assert config.database_path == str(custom_db)
    assert custom_db.exists()
    assert "Database path:" in result.stdout


def test_config_show_json_lists_config_values(isolated_config) -> None:  # type: ignore[no-untyped-def]
    result = runner.invoke(app, ["config", "show", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["config_dir"] == str(isolated_config)
    assert payload["vault_path"] == str(isolated_config / "vault")
    assert payload["daemon_host"] == "127.0.0.1"
    # `default_gain` should be in the snapshot with the model default (1.0).
    assert payload["meetings"]["default_gain"] == 1.0


def test_config_show_includes_default_gain_in_table(isolated_config) -> None:  # type: ignore[no-untyped-def]
    result = runner.invoke(app, ["config", "show"])

    assert result.exit_code == 0
    # The default gain row should be present in the rich table output.
    assert "default gain" in result.stdout.lower()
    assert "1.0x" in result.stdout


def test_config_meetings_gain_round_trip(isolated_config) -> None:  # type: ignore[no-untyped-def]
    # Set gain via the CLI, then verify it shows up in `nina config show`.
    result = runner.invoke(app, ["config", "meetings-gain", "4.0"])
    assert result.exit_code == 0, result.stdout
    assert "+12.0 dB" in result.stdout

    # Now show should reflect the new value.
    show = runner.invoke(app, ["config", "show", "--json"])
    assert show.exit_code == 0
    payload = json.loads(show.stdout)
    assert payload["meetings"]["default_gain"] == 4.0

    # And the on-disk file should have it too.
    config_path = isolated_config / "config.yaml"
    on_disk = yaml.safe_load(config_path.read_text())
    assert on_disk["meetings"]["default_gain"] == 4.0


def test_config_edit_uses_explicit_editor(monkeypatch: pytest.MonkeyPatch, isolated_config) -> None:  # type: ignore[no-untyped-def]
    captured: dict[str, Any] = {}
    _patch_popen_capture(monkeypatch, captured)

    result = runner.invoke(app, ["config", "edit", "--editor", "nvim {path}"])

    assert result.exit_code == 0, result.stdout
    assert captured["cmd"] == ["nvim", str(isolated_config / "config.yaml")]


def test_config_edit_creates_file_if_missing(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    config_dir = tmp_path / "nina-config"
    initialize(config_dir=config_dir, force=True)
    monkeypatch.setenv("NINA_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("NINA_TOKEN", read_token(get_token_path(config_dir)))

    config_path = config_dir / "config.yaml"
    config_path.unlink(missing_ok=True)
    assert not config_path.exists()

    captured: dict[str, Any] = {}
    _patch_popen_capture(monkeypatch, captured)

    result = runner.invoke(app, ["config", "edit", "--editor", "code"])

    assert result.exit_code == 0, result.stdout
    # File was created with the effective config.
    assert config_path.exists()
    on_disk = yaml.safe_load(config_path.read_text())
    assert on_disk["profile"] == "default"
    # And the editor was launched with the path.
    assert captured["cmd"] == ["code", str(config_path)]


def test_config_edit_falls_back_to_code_binary(
    monkeypatch: pytest.MonkeyPatch, isolated_config
) -> None:  # type: ignore[no-untyped-def]
    # Make `code` discoverable.
    code_dir = isolated_config / "bin"
    code_dir.mkdir(exist_ok=True)
    fake_code = code_dir / "code"
    fake_code.write_text("#!/bin/sh\n")
    fake_code.chmod(0o755)
    monkeypatch.setenv("PATH", f"{code_dir}:{__import__('os').environ.get('PATH', '')}")
    monkeypatch.delenv("EDITOR", raising=False)

    captured: dict[str, Any] = {}
    _patch_popen_capture(monkeypatch, captured)

    result = runner.invoke(app, ["config", "edit", "--wait"])

    assert result.exit_code == 0, result.stdout
    assert captured["cmd"][0] == "code"
    assert "--wait" in captured["cmd"]
    assert captured["cmd"][-1] == str(isolated_config / "config.yaml")


def test_config_edit_exits_when_no_editor_available(
    monkeypatch: pytest.MonkeyPatch, isolated_config
) -> None:  # type: ignore[no-untyped-def]
    # Pretend nothing is on PATH and no $EDITOR is set.
    monkeypatch.setenv("PATH", "/nonexistent")
    monkeypatch.delenv("EDITOR", raising=False)
    # Also no xdg-open/open/start.
    import shutil as _shutil

    monkeypatch.setattr(_shutil, "which", lambda name: None)

    result = runner.invoke(app, ["config", "edit"])

    assert result.exit_code == 1
    assert "no editor found" in result.stdout.lower()


def test_tui_binary_resolution_prefers_env(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    tui_bin = tmp_path / "nina-tui"
    tui_bin.write_text("binary")
    monkeypatch.setenv("NINA_TUI_BIN", str(tui_bin))

    assert main_module._resolve_tui_binary() == tui_bin


def test_version_command_prints_nina_version() -> None:
    from nina_core import __version__

    for argv in (["version"], ["v"], ["-v"], ["--version"]):
        result = runner.invoke(app, argv)
        assert result.exit_code == 0, argv
        assert result.stdout.strip() == f"Nina {__version__}", argv


def test_tui_alias_invokes_the_tui_command(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    tui_bin = tmp_path / "nina-tui"
    tui_bin.write_text("binary")
    monkeypatch.setattr(main_module, "_resolve_tui_binary", lambda: tui_bin)
    captured: dict[str, Any] = {}

    def fake_execv(path: str, args: list[str]) -> None:
        captured["path"] = path
        captured["args"] = args
        raise SystemExit(0)

    monkeypatch.setattr(main_module.os, "execv", fake_execv)

    result = runner.invoke(app, ["t"])

    assert result.exit_code == 0
    assert captured == {"path": str(tui_bin), "args": [str(tui_bin)]}


def test_daemon_restart_alias_invokes_restart_command(monkeypatch, isolated_config) -> None:  # type: ignore[no-untyped-def]
    (isolated_config / "daemon.pid").write_text("1234")
    monkeypatch.setattr(main_module, "_process_exists", lambda pid: pid == 1234)
    monkeypatch.setattr(main_module, "_terminate_process", lambda pid: None)

    class FakeProcess:
        pid = 5678

    monkeypatch.setattr(main_module.subprocess, "Popen", lambda *args, **kwargs: FakeProcess())

    result = runner.invoke(app, ["d", "r"])

    assert result.exit_code == 0
    assert "Daemon stopped" in result.stdout
    assert "Daemon restarted (pid 5678)" in result.stdout


def test_server_command_prefers_installed_entrypoint(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(main_module.shutil, "which", lambda name: "/opt/nina/nina-server")

    assert main_module._server_command() == ["/opt/nina/nina-server"]


def test_ticket_create_calls_ticket_endpoint(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    calls: list[tuple[str, str, dict[str, Any]]] = []

    def fake_request(method: str, path: str, **kwargs: Any) -> FakeResponse:
        calls.append((method, path, kwargs))
        return FakeResponse({"id": "ticket-1"})

    monkeypatch.setattr("nina_cli.ticket_commands.request", fake_request)

    result = runner.invoke(
        app,
        ["ticket", "create", "Fix daemon stop", "--description", "Recursion bug"],
    )

    assert result.exit_code == 0
    assert calls == [
        (
            "POST",
            "/tickets",
            {"json": {"title": "Fix daemon stop", "description": "Recursion bug"}},
        )
    ]
    assert "Created ticket ticket-1" in result.stdout


def test_research_run_calls_research_endpoint(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    calls: list[tuple[str, str, dict[str, Any]]] = []

    def fake_request(method: str, path: str, **kwargs: Any) -> FakeResponse:
        calls.append((method, path, kwargs))
        return FakeResponse(
            {
                "note_path": "Research/2026-06-13-openai-web-search.md",
                "summary": "Summary",
                "sources": [{"title": "Example", "url": "https://example.com"}],
            }
        )

    monkeypatch.setattr("nina_cli.research_commands.request", fake_request)

    result = runner.invoke(app, ["research", "run", "OpenAI web search"])

    assert result.exit_code == 0
    assert calls == [("POST", "/research/run", {"json": {"topic": "OpenAI web search"}})]
    assert "Research note: Research/2026-06-13-openai-web-search.md" in result.stdout
    assert "Summary: Summary" in result.stdout
    assert "Example" in result.stdout


def test_note_show_uses_get_endpoint(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    calls: list[tuple[str, str, dict]] = []

    def fake_request(method, path, **kwargs):
        calls.append((method, path, kwargs))
        if path == "/notes/Research/note.md":
            return FakeResponse(
                {
                    "path": "Research/note.md",
                    "title": "Note",
                    "nina_type": "note",
                    "frontmatter": {"title": "Note"},
                    "body": "Hello world",
                }
            )
        raise AssertionError(f"Unexpected path: {path}")

    monkeypatch.setattr("nina_cli.notes_commands.request", fake_request)
    result = runner.invoke(app, ["note", "show", "Research/note.md"])
    assert result.exit_code == 0, result.output
    assert calls == [("GET", "/notes/Research/note.md", {})]
    assert "Note" in result.stdout
    assert "Hello world" in result.stdout


def test_note_create_posts_body(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    calls: list[tuple[str, str, dict]] = []

    def fake_request(method, path, **kwargs):
        calls.append((method, path, kwargs))
        return FakeResponse({"path": "Research/new.md"})

    monkeypatch.setattr("nina_cli.notes_commands.request", fake_request)
    result = runner.invoke(
        app,
        ["note", "create", "Research/new.md", "--body", "hello", "--type", "note"],
    )
    assert result.exit_code == 0, result.output
    assert calls == [
        (
            "POST",
            "/notes",
            {"json": {"path": "Research/new.md", "body": "hello", "nina_type": "note"}},
        )
    ]
    assert "Created" in result.stdout


def test_note_list_supports_filters(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    calls: list[tuple[str, str, dict]] = []

    def fake_request(method, path, **kwargs):
        calls.append((method, path, kwargs))
        return FakeResponse(
            {
                "notes": [
                    {
                        "path": "Research/a.md",
                        "title": "A",
                        "nina_type": "note",
                    }
                ]
            }
        )

    monkeypatch.setattr("nina_cli.notes_commands.request", fake_request)
    result = runner.invoke(
        app,
        ["note", "list", "--folder", "Research", "--type", "note", "--limit", "5", "--json"],
    )
    assert result.exit_code == 0, result.output
    assert calls == [("GET", "/notes?limit=5&folder=Research&nina_type=note", {})]
    assert "Research/a.md" in result.stdout


def test_note_append_patches(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    calls: list[tuple[str, str, dict]] = []

    def fake_request(method, path, **kwargs):
        calls.append((method, path, kwargs))
        return FakeResponse({"path": "Daily/today.md"})

    monkeypatch.setattr("nina_cli.notes_commands.request", fake_request)
    result = runner.invoke(
        app,
        ["note", "append", "Daily/today.md", "--body", "second"],
    )
    assert result.exit_code == 0, result.output
    assert calls == [("PATCH", "/notes/Daily/today.md", {"json": {"append": "second"}})]


def test_note_update_patches_body(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    calls: list[tuple[str, str, dict]] = []

    def fake_request(method, path, **kwargs):
        calls.append((method, path, kwargs))
        return FakeResponse({"path": "Research/x.md"})

    monkeypatch.setattr("nina_cli.notes_commands.request", fake_request)
    result = runner.invoke(
        app,
        ["note", "update", "Research/x.md", "--body", "new"],
    )
    assert result.exit_code == 0, result.output
    assert calls == [("PATCH", "/notes/Research/x.md", {"json": {"body": "new"}})]


# ----------------------------------------------------------------------------
# Meeting play path: recover from a stranded `.wav.partial`
# ----------------------------------------------------------------------------


def test_resolve_audio_path_returns_existing_wav(tmp_path) -> None:
    from nina_cli.meeting_commands import resolve_audio_path

    wav = tmp_path / "meeting.wav"
    wav.write_bytes(b"RIFF...WAVE")
    resolved = resolve_audio_path(str(wav))
    assert resolved == wav


def test_resolve_audio_path_promotes_partial(tmp_path) -> None:
    from nina_cli.meeting_commands import resolve_audio_path

    wav = tmp_path / "meeting.wav"
    partial = tmp_path / "meeting.wav.partial"
    partial.write_bytes(b"RIFF...WAVE")  # valid WAV header + some data
    resolved = resolve_audio_path(str(wav))
    assert resolved == wav
    assert wav.exists()
    assert not partial.exists()


def test_resolve_audio_path_raises_when_neither_exists(tmp_path) -> None:
    from nina_cli.meeting_commands import resolve_audio_path

    wav = tmp_path / "missing.wav"
    with pytest.raises(FileNotFoundError):
        resolve_audio_path(str(wav))


def test_resolve_audio_path_raises_when_partial_empty(tmp_path) -> None:
    """A zero-byte partial is not useful — don't promote it."""
    from nina_cli.meeting_commands import resolve_audio_path

    wav = tmp_path / "meeting.wav"
    partial = tmp_path / "meeting.wav.partial"
    partial.write_bytes(b"")
    with pytest.raises(FileNotFoundError):
        resolve_audio_path(str(wav))
    # We did NOT promote the empty partial.
    assert not wav.exists()
    assert partial.exists()


def test_resolve_audio_path_raises_for_empty_path() -> None:
    from nina_cli.meeting_commands import resolve_audio_path

    with pytest.raises(FileNotFoundError, match="no audio_path"):
        resolve_audio_path("")
