from __future__ import annotations

from typing import Any

from nina_cli import main as main_module
from nina_cli.main import app
from typer.testing import CliRunner


class FakeResponse:
    def __init__(self, payload: Any) -> None:
        self.payload = payload

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


def test_tui_binary_resolution_prefers_env(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    tui_bin = tmp_path / "nina-tui"
    tui_bin.write_text("binary")
    monkeypatch.setenv("NINA_TUI_BIN", str(tui_bin))

    assert main_module._resolve_tui_binary() == tui_bin


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
