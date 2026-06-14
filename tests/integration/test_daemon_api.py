from __future__ import annotations

from pathlib import Path

import frontmatter
import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def test_task_creation_and_kanban_move_update_status_and_note(
    api_client: TestClient,
    auth_headers: dict[str, str],
    isolated_config: Path,
) -> None:
    first = api_client.post(
        "/tasks",
        headers=auth_headers,
        json={"title": "First task", "description": ""},
    )
    assert first.status_code == 200
    assert first.json()["kanban_column"] == "Todo"
    assert first.json()["kanban_position"] == 0

    second = api_client.post(
        "/tasks",
        headers=auth_headers,
        json={"title": "Second task", "description": ""},
    )
    assert second.status_code == 200
    task_id = second.json()["id"]
    assert second.json()["kanban_position"] == 1

    moved = api_client.post(
        "/kanban/move",
        headers=auth_headers,
        json={"task_id": task_id, "to_column": "Doing", "to_position": 0},
    )
    assert moved.status_code == 200
    assert moved.json()["kanban_column"] == "Doing"
    assert moved.json()["kanban_position"] == 0
    assert moved.json()["status"] == "doing"

    board = api_client.get("/kanban", headers=auth_headers)
    assert board.status_code == 200
    assert [task["title"] for task in board.json()["Todo"]] == ["First task"]
    assert [task["title"] for task in board.json()["Doing"]] == ["Second task"]

    note_path = isolated_config / "vault" / moved.json()["note_path"]
    note = frontmatter.loads(note_path.read_text())
    assert note.metadata["status"] == "doing"
    assert note.metadata["kanban_column"] == "Doing"


def test_ask_answers_from_obsidian_notes(
    api_client: TestClient,
    auth_headers: dict[str, str],
    isolated_config: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NINA_LLM_PROVIDER", "fake")
    note_dir = isolated_config / "vault" / "Research"
    note_dir.mkdir(parents=True, exist_ok=True)
    (note_dir / "codex.md").write_text(
        "---\ntitle: Codex Auth Notes\nnina_type: note\n---\n\nCodex OAuth is used through the local Codex CLI session.\n"
    )

    asked = api_client.post(
        "/ask",
        headers=auth_headers,
        json={"question": "How is Codex OAuth used?", "limit": 3},
    )

    assert asked.status_code == 200
    payload = asked.json()
    assert payload["provider"] == "fake"
    assert payload["sources"][0]["path"] == "Research/codex.md"
    assert "Fake response" in payload["answer"]


def test_jobs_can_be_created_toggled_run_and_observed(
    api_client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    seeded = api_client.get("/jobs", headers=auth_headers)
    assert seeded.status_code == 200
    assert any(job["name"] == "daily-summary" for job in seeded.json())

    created = api_client.post(
        "/jobs",
        headers=auth_headers,
        json={
            "name": "test-summary",
            "workflow_name": "summarize-last-day",
            "schedule": "*/15 * * * *",
            "enabled": True,
        },
    )
    assert created.status_code == 200
    assert created.json()["name"] == "test-summary"
    assert created.json()["enabled"] is True

    disabled = api_client.patch(
        "/jobs/test-summary",
        headers=auth_headers,
        json={"enabled": False},
    )
    assert disabled.status_code == 200
    assert disabled.json()["enabled"] is False

    enabled = api_client.patch(
        "/jobs/test-summary",
        headers=auth_headers,
        json={"enabled": True},
    )
    assert enabled.status_code == 200
    assert enabled.json()["enabled"] is True

    run = api_client.post("/jobs/test-summary/run", headers=auth_headers)
    assert run.status_code == 200
    assert run.json()["job_name"] == "test-summary"
    assert run.json()["status"] == "completed"
    assert run.json()["workflow_run_id"]

    runs = api_client.get("/job-runs?job_name=test-summary", headers=auth_headers)
    assert runs.status_code == 200
    assert [job_run["status"] for job_run in runs.json()] == ["completed"]


def test_ticket_alias_creates_moves_and_reads_same_note(
    api_client: TestClient,
    auth_headers: dict[str, str],
    isolated_config: Path,
) -> None:
    created = api_client.post(
        "/tickets",
        headers=auth_headers,
        json={"title": "Alias ticket", "description": "Created through the ticket route."},
    )
    assert created.status_code == 200
    ticket_id = created.json()["id"]

    moved = api_client.post(
        "/kanban/move",
        headers=auth_headers,
        json={"task_id": ticket_id, "to_column": "Doing", "to_position": 0},
    )
    assert moved.status_code == 200
    assert moved.json()["kanban_column"] == "Doing"

    listed = api_client.get("/tickets", headers=auth_headers)
    assert listed.status_code == 200
    assert any(ticket["id"] == ticket_id for ticket in listed.json())

    show = api_client.get(f"/tickets/{ticket_id}", headers=auth_headers)
    assert show.status_code == 200
    assert show.json()["kanban_column"] == "Doing"

    note_path = isolated_config / "vault" / show.json()["note_path"]
    note = frontmatter.loads(note_path.read_text())
    assert note.metadata["nina_type"] == "task"
    assert note.metadata["status"] == "doing"
    assert note.metadata["kanban_column"] == "Doing"


def test_chat_sessions_use_obsidian_context(
    api_client: TestClient,
    auth_headers: dict[str, str],
    isolated_config: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NINA_LLM_PROVIDER", "fake")
    note_dir = isolated_config / "vault" / "Research"
    note_dir.mkdir(parents=True, exist_ok=True)
    (note_dir / "codex.md").write_text(
        "---\ntitle: Codex Auth Notes\nnina_type: note\n---\n\nCodex OAuth is used through the local Codex CLI session.\n"
    )

    created = api_client.post(
        "/sessions",
        headers=auth_headers,
        json={"mode": "chat", "title": "Chat"},
    )
    assert created.status_code == 200
    session_id = created.json()["id"]

    asked = api_client.post(
        f"/sessions/{session_id}/messages",
        headers=auth_headers,
        json={"content": "How is Codex OAuth used?"},
    )
    assert asked.status_code == 200
    payload = asked.json()
    assert payload["assistant"]["role"] == "assistant"
    assert payload["sources"][0]["path"] == "Research/codex.md"

    fetched = api_client.get(f"/sessions/{session_id}", headers=auth_headers)
    assert fetched.status_code == 200
    assert [message["role"] for message in fetched.json()["messages"]] == ["user", "assistant"]


def test_research_run_writes_summary_and_sources_note(
    api_client: TestClient,
    auth_headers: dict[str, str],
    isolated_config: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NINA_RESEARCH_PROVIDER", "fake")

    researched = api_client.post(
        "/research/run",
        headers=auth_headers,
        json={"topic": "OpenAI web search"},
    )
    assert researched.status_code == 200
    payload = researched.json()
    assert payload["status"] == "completed"
    assert payload["workflow_run_id"]
    assert payload["note_path"].startswith("Research/")

    note_path = isolated_config / "vault" / payload["note_path"]
    note = frontmatter.loads(note_path.read_text())
    assert note.metadata["nina_type"] == "research_report"
    assert note.metadata["topic"] == "OpenAI web search"
    assert note.metadata["workflow_run_id"] == payload["workflow_run_id"]
    assert note.metadata["sources"][0]["url"].startswith("https://example.com/")
    assert "Fake research summary" in note.content


def test_notes_endpoints_round_trip(
    api_client: TestClient,
    auth_headers: dict[str, str],
    isolated_config: Path,
) -> None:
    body = "---\ntitle: Hello Note\nnina_type: note\n---\n\n# Hello\n\nbody"
    created = api_client.post(
        "/notes",
        headers=auth_headers,
        json={"path": "Research/hello.md", "body": body, "nina_type": "note"},
    )
    assert created.status_code == 200
    assert created.json()["path"] == "Research/hello.md"

    fetched = api_client.get("/notes/Research/hello.md", headers=auth_headers)
    assert fetched.status_code == 200
    payload = fetched.json()
    assert "body" in payload and "Hello" in payload["body"]
    assert payload["frontmatter"].get("title") == "Hello Note"

    # Append
    patched = api_client.patch(
        "/notes/Research/hello.md",
        headers=auth_headers,
        json={"append": "more"},
    )
    assert patched.status_code == 200
    fetched2 = api_client.get("/notes/Research/hello.md", headers=auth_headers)
    assert "more" in fetched2.json()["body"]

    # List
    listed = api_client.get("/notes?nina_type=note", headers=auth_headers)
    assert listed.status_code == 200
    paths = {n["path"] for n in listed.json()["notes"]}
    assert "Research/hello.md" in paths


def test_notes_endpoint_rejects_unsafe_path(
    api_client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    bad = api_client.post(
        "/notes",
        headers=auth_headers,
        json={"path": "../escape.md", "body": "x", "nina_type": "note"},
    )
    assert bad.status_code == 400

    bad2 = api_client.post(
        "/notes",
        headers=auth_headers,
        json={"path": "System/Indexes/x.md", "body": "x", "nina_type": "note"},
    )
    assert bad2.status_code == 400


def test_session_cancel_endpoint(
    api_client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    created = api_client.post(
        "/sessions",
        headers=auth_headers,
        json={"mode": "chat", "title": "Chat"},
    )
    session_id = created.json()["id"]

    cancel = api_client.post(f"/sessions/{session_id}/cancel", headers=auth_headers)
    assert cancel.status_code == 200
    fetched = api_client.get(f"/sessions/{session_id}", headers=auth_headers)
    assert fetched.json()["cancel_requested"] is True

    clear = api_client.post(f"/sessions/{session_id}/clear-cancel", headers=auth_headers)
    assert clear.status_code == 200
    fetched = api_client.get(f"/sessions/{session_id}", headers=auth_headers)
    assert fetched.json()["cancel_requested"] is False


def test_config_endpoint_updates_runtime_and_reports_restart_requirement(
    api_client: TestClient,
    auth_headers: dict[str, str],
    isolated_config: Path,
) -> None:
    custom_vault = isolated_config.parent / "daemon-config-vault"
    response = api_client.patch(
        "/config",
        headers=auth_headers,
        json={
            "vault_path": str(custom_vault),
            "daemon_port": 9123,
            "llm": {"provider": "fake"},
            "scheduler": {"daily_summary_time": "08:30"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["changed_fields"] == [
        "vault_path",
        "daemon_port",
        "llm.provider",
        "scheduler.daily_summary_time",
    ]
    assert payload["restart_required"] is True
    assert payload["config"]["vault_path"] == str(custom_vault)
    assert payload["config"]["daemon_port"] == 9123
    assert payload["config"]["llm"]["provider"] == "fake"
    assert payload["config"]["scheduler"]["daily_summary_time"] == "08:30"
    assert (custom_vault / "Projects").exists()

    health = api_client.get("/health", headers=auth_headers)
    assert health.status_code == 200
    assert health.json()["vault_path"] == str(custom_vault)
