from __future__ import annotations

import json
from typing import Any

from nina_cli import config_commands as config_module
from nina_cli import main as main_module
from nina_cli.api import api_base
from nina_cli.main import app
from nina_core.config import load_effective_config
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
            {"json": {"purpose": "cli_test", "prompt": "Reply with auth ok", "model": "gpt-5.4-mini"}},
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
            return FakeResponse({"id": "session-1", "mode": "chat", "title": "Chat", "messages": []})
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

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    assert "Daemon running (pid 4321)" in result.stdout
    assert "Health: ok" in result.stdout
    assert "LLM auth: Codex OAuth connected, account acc-123" in result.stdout
    assert "Configuration paths:" in result.stdout
    assert "Config dir:" in result.stdout
    assert "Config file:" in result.stdout
    assert "Token:" in result.stdout
    assert "Database:" in result.stdout
    assert "Vault:" in result.stdout
    assert "Log:" in result.stdout
    assert "PID:" in result.stdout


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


def test_status_reports_offline_daemon_and_configuration_paths(
    monkeypatch, isolated_config
) -> None:  # type: ignore[no-untyped-def]
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
    assert "LLM auth: disconnected (Codex auth file not found)" in result.stdout
    assert "Configuration paths:" in result.stdout
    assert "Config dir:" in result.stdout


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


def test_tui_binary_resolution_prefers_env(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    tui_bin = tmp_path / "nina-tui"
    tui_bin.write_text("binary")
    monkeypatch.setenv("NINA_TUI_BIN", str(tui_bin))

    assert main_module._resolve_tui_binary() == tui_bin


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
