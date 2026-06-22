from __future__ import annotations

import os
import subprocess
from pathlib import Path

import frontmatter
import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


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


def test_task_creation_and_classification_patches_task_and_note(
    api_client: TestClient,
    auth_headers: dict[str, str],
    isolated_config: Path,
    fake_llm,
) -> None:
    fake_llm.queue_text('{"task_type": "coding", "reason": "refactor is a coding task"}')
    repository_id = _register_repository(api_client, auth_headers, isolated_config / "daemon-repo")

    first = api_client.post(
        "/tasks",
        headers=auth_headers,
        json={
            "title": "Refactor the auth module",
            "description": "Split it into smaller files.",
            "repository_id": repository_id,
        },
    )
    assert first.status_code == 200
    first_id = first.json()["id"]
    assert first.json()["task_type"] == "unclassified"
    assert first.json()["status"] == "idle"

    # The background classifier runs in a thread; give it enough time under full-suite load.
    _wait_for_classification(api_client, auth_headers, first_id, expected="coding")

    fake_llm.queue_text('{"task_type": "reminder", "reason": "messaging a colleague"}')
    second = api_client.post(
        "/tasks",
        headers=auth_headers,
        json={"title": "Email Sarah about Q3 numbers", "description": ""},
    )
    assert second.status_code == 200
    second_id = second.json()["id"]
    assert second.json()["task_type"] == "unclassified"
    _wait_for_classification(api_client, auth_headers, second_id, expected="reminder")

    first_now = api_client.get(f"/tasks/{first_id}", headers=auth_headers).json()
    assert first_now["task_type"] == "coding"
    assert first_now["classified_at"]
    assert first_now["classification_model"]
    assert first_now["classification_reason"]

    note_path = isolated_config / "vault" / "Tasks" / f"{first_id}.md"
    note = frontmatter.loads(note_path.read_text())
    assert note.metadata["task_type"] == "coding"
    assert note.metadata["classified_at"] == first_now["classified_at"]


def _wait_for_classification(
    api_client: TestClient,
    auth_headers: dict[str, str],
    task_id: str,
    *,
    expected: str,
    timeout: float = 15.0,
) -> dict[str, object]:
    """Poll the task until the background classifier finishes."""

    import time

    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = api_client.get(f"/tasks/{task_id}", headers=auth_headers)
        assert resp.status_code == 200
        payload = resp.json()
        if payload["task_type"] == expected:
            return payload
        time.sleep(0.05)
    raise AssertionError(f"Task {task_id} did not classify as {expected!r} within {timeout}s")


def test_ask_answers_from_obsidian_notes(
    api_client: TestClient,
    auth_headers: dict[str, str],
    isolated_config: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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


def test_ticket_alias_creates_and_classifies_via_ticket_routes(
    api_client: TestClient,
    auth_headers: dict[str, str],
    isolated_config: Path,
    fake_llm,
) -> None:
    fake_llm.queue_text('{"task_type": "coding", "reason": "default to coding for now"}')
    repository_id = _register_repository(api_client, auth_headers, isolated_config / "ticket-repo")

    created = api_client.post(
        "/tickets",
        headers=auth_headers,
        json={
            "title": "Alias ticket",
            "description": "Created through the ticket route.",
            "repository_id": repository_id,
        },
    )
    assert created.status_code == 200
    ticket_id = created.json()["id"]
    assert created.json()["task_type"] == "unclassified"

    _wait_for_classification(api_client, auth_headers, ticket_id, expected="coding")

    listed = api_client.get("/tickets", headers=auth_headers)
    assert listed.status_code == 200
    assert any(ticket["id"] == ticket_id for ticket in listed.json())

    show = api_client.get(f"/tickets/{ticket_id}", headers=auth_headers)
    assert show.status_code == 200
    assert show.json()["task_type"] == "coding"

    note_path = isolated_config / "vault" / "Tasks" / f"{ticket_id}.md"
    note = frontmatter.loads(note_path.read_text())
    assert note.metadata["nina_type"] == "task"
    assert note.metadata["task_type"] == "coding"


def test_chat_sessions_use_obsidian_context(
    api_client: TestClient,
    auth_headers: dict[str, str],
    isolated_config: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
    from nina_core.research import service as research_service_module

    monkeypatch.setattr(
        research_service_module,
        "FakeResearchProvider",
        research_service_module.FakeResearchProvider,
    )
    # Pin the research provider to "fake" via config so the daemon picks
    # the deterministic provider rather than hitting the real OpenAI API.
    config_path = isolated_config / "config.yaml"
    import yaml

    cfg = yaml.safe_load(config_path.read_text()) or {}
    cfg.setdefault("research", {})
    cfg["research"]["provider"] = "fake"
    cfg["research"]["model"] = "fake"
    cfg["research"]["search_mode"] = "live"
    config_path.write_text(yaml.safe_dump(cfg, sort_keys=False))
    # Re-apply the config on the running app.
    from nina_core.config import load_effective_config
    from nina_server import apply_runtime_config

    apply_runtime_config(api_client.app, isolated_config, load_effective_config(isolated_config))

    researched = api_client.post(
        "/research/run",
        headers=auth_headers,
        json={"topic": "OpenAI web search", "search_mode": "cached"},
    )
    assert researched.status_code == 200
    payload = researched.json()
    assert payload["status"] == "completed"
    assert payload["workflow_run_id"]
    assert payload["note_path"].startswith("Research/")
    assert payload["search_mode"] == "cached"

    note_path = isolated_config / "vault" / payload["note_path"]
    note = frontmatter.loads(note_path.read_text())
    assert note.metadata["nina_type"] == "research_report"
    assert note.metadata["topic"] == "OpenAI web search"
    assert note.metadata["workflow_run_id"] == payload["workflow_run_id"]
    assert note.metadata["search_mode"] == "cached"
    assert note.metadata["provider"] == "fake"
    assert note.metadata["sources"][0]["url"].startswith("https://example.com/")
    assert "Fake research summary" in note.content

    listed = api_client.get(
        "/notes?folder=Research&nina_type=research_report",
        headers=auth_headers,
    )
    assert listed.status_code == 200
    assert any(item["path"] == payload["note_path"] for item in listed.json()["notes"])

    fetched_path = payload["note_path"]
    fetched = api_client.get(f"/notes/{fetched_path}", headers=auth_headers)
    assert fetched.status_code == 200
    assert fetched.json()["nina_type"] == "research_report"


def test_research_run_failure_returns_detail(
    api_client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    response = api_client.post(
        "/research/run",
        headers=auth_headers,
        json={"topic": "OpenAI web search", "search_mode": "bogus"},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["status"] == "failed"
    assert "research search_mode" in payload["detail"]


def test_search_reindex_backfills_note_metadata(
    api_client: TestClient,
    auth_headers: dict[str, str],
    isolated_config: Path,
) -> None:
    note_path = isolated_config / "vault" / "Research" / "raw.md"
    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text(
        "---\ntitle: Raw Research\nnina_type: research_report\n---\n\nRaw body."
    )

    missing = api_client.get("/notes/Research/raw.md", headers=auth_headers)
    assert missing.status_code == 404

    reindexed = api_client.post("/search/reindex", headers=auth_headers, json={})
    assert reindexed.status_code == 200
    assert reindexed.json() == {"reindexed": True}

    fetched = api_client.get("/notes/Research/raw.md", headers=auth_headers)
    assert fetched.status_code == 200
    assert fetched.json()["nina_type"] == "research_report"


def test_search_open_uses_configured_open_command(
    api_client: TestClient,
    auth_headers: dict[str, str],
    isolated_config: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    note_path = isolated_config / "vault" / "Research" / "open file.md"
    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text("# Open me\n")

    updated = api_client.patch(
        "/config",
        headers=auth_headers,
        json={"meetings": {"open_command": "obsidian-open {path}"}},
    )
    assert updated.status_code == 200

    calls: list[tuple[list[str], dict[str, object]]] = []

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("nina_server.routers.search.subprocess.run", fake_run)

    opened = api_client.post(
        "/search/open",
        headers=auth_headers,
        json={"path": "Research/open file.md"},
    )

    assert opened.status_code == 200
    assert opened.json() == {"opened": True}
    assert calls == [
        (
            ["obsidian-open", str(note_path)],
            {"capture_output": True, "text": True, "timeout": 10},
        )
    ]


def test_search_open_reports_open_command_failure(
    api_client: TestClient,
    auth_headers: dict[str, str],
    isolated_config: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    note_path = isolated_config / "vault" / "Research" / "open.md"
    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text("# Open me\n")

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 1, stdout="", stderr="no obsidian handler")

    monkeypatch.setattr("nina_server.routers.search.subprocess.run", fake_run)

    opened = api_client.post(
        "/search/open",
        headers=auth_headers,
        json={"path": "Research/open.md"},
    )

    assert opened.status_code == 500
    assert opened.json()["detail"] == "no obsidian handler"


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
        json={"path": "System/Deleted/x.md", "body": "x", "nina_type": "note"},
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
    assert (custom_vault / "Tasks").exists()
    assert (custom_vault / "System" / "Archived").exists()

    health = api_client.get("/health", headers=auth_headers)
    assert health.status_code == 200
    assert health.json()["vault_path"] == str(custom_vault)


def test_daemon_logs_endpoint_tails_and_filters_task_lines(
    api_client: TestClient,
    auth_headers: dict[str, str],
    isolated_config: Path,
) -> None:
    log_path = isolated_config / "logs" / "daemon.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        "2026 info nina.task task=task-1 event=queued\n"
        "2026 info unrelated line\n"
        "2026 info nina.task task=task-2 event=done\n"
    )

    response = api_client.get(
        "/logs/daemon?tail=10&task_id=task-1",
        headers=auth_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["path"] == str(log_path)
    assert payload["lines"] == ["2026 info nina.task task=task-1 event=queued"]



def test_task_codex_logs_endpoint_tails_latest_run(
    api_client: TestClient,
    auth_headers: dict[str, str],
    isolated_config: Path,
) -> None:
    created = api_client.post(
        "/tasks",
        headers=auth_headers,
        json={
            "title": "Logged task",
            "description": "Has Codex logs",
            "task_type": "unclassified",
            "auto_classify": False,
        },
    )
    assert created.status_code == 200
    task_id = created.json()["id"]

    task_dir = isolated_config / "logs" / "codex" / "tasks" / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    old_log = task_dir / "run-old.log"
    new_log = task_dir / "run-new.log"
    old_log.write_text("old one\nold two\n")
    new_log.write_text("new one\nnew two\n")
    os.utime(old_log, (1, 1))
    os.utime(new_log, (2, 2))

    latest = api_client.get(f"/tasks/{task_id}/codex-logs?tail=1", headers=auth_headers)

    assert latest.status_code == 200
    payload = latest.json()
    assert payload["task_id"] == task_id
    assert payload["run_id"] == "run-new"
    assert payload["path"] == str(new_log)
    assert payload["lines"] == ["new two"]
    assert [run["run_id"] for run in payload["runs"]] == ["run-new", "run-old"]

    explicit = api_client.get(
        f"/tasks/{task_id}/codex-logs?run_id=run-old&tail=-1",
        headers=auth_headers,
    )

    assert explicit.status_code == 200
    explicit_payload = explicit.json()
    assert explicit_payload["run_id"] == "run-old"
    assert explicit_payload["lines"] == ["old one", "old two"]

    missing = api_client.get("/tasks/not-a-task/codex-logs", headers=auth_headers)
    assert missing.status_code == 404


def test_status_and_capabilities_endpoints(
    api_client: TestClient,
    auth_headers: dict[str, str],
    isolated_config: Path,
) -> None:
    status = api_client.get("/status", headers=auth_headers)
    assert status.status_code == 200
    payload = status.json()
    assert payload["profile"] == "default"
    assert payload["config_dir"] == str(isolated_config)
    assert payload["database_path"].endswith("nina.db")
    assert payload["scheduler_running"] is False
    assert "codex" in payload

    capabilities = api_client.get("/capabilities", headers=auth_headers)
    assert capabilities.status_code == 200
    assert "/tasks" in capabilities.json()["routes"]
    assert "/codex" in capabilities.json()["routes"]
