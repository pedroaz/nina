"""Integration tests for Codex lifecycle callbacks."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import frontmatter
import pytest
from fastapi.testclient import TestClient
from nina_core.config import get_database_path
from nina_core.db.engine import make_engine, make_session
from nina_core.models.models import Event, Task
from nina_core.obsidian.service import ObsidianService
from nina_core.repositories.service import RepositoryService
from nina_core.tasks.service import TaskService

pytestmark = pytest.mark.integration


def _create_task(isolated_config: Path, *, title: str, task_type: str = "coding") -> dict[str, object]:
    engine = make_engine(str(get_database_path(isolated_config)))
    session_local = make_session(engine)
    db = session_local()
    try:
        repo_path = isolated_config / "events-repo"
        repo_path.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init", str(repo_path)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        repository_id = RepositoryService(db).create(repo_path).id
        service = TaskService(
            db,
            ObsidianService(isolated_config / "vault"),
            background_classify=False,
        )
        task = service.create(
            title,
            "Run through Codex.",
            task_type=task_type,
            repository_id=repository_id,
            auto_classify=False,
        )
        return {"id": task.id, "repository_id": repository_id}
    finally:
        db.close()


def _callback_payload(
    task_id: str,
    *,
    event: str,
    run_id: str = "run-1",
    task_type: str | None = "coding",
    set_status: str | None = None,
    set_task_type: str | None = None,
    create_next_task_type: str | None = None,
    last_assistant_message: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "version": 1,
        "event": event,
        "source": "codex-hook",
        "taskId": task_id,
        "runId": run_id,
        "sessionId": "session-1",
        "turnId": "turn-1",
        "cwd": "/tmp/repo",
        "taskType": task_type,
        "lastAssistantMessage": last_assistant_message,
        "sentAt": "2026-06-20T12:00:00Z",
    }
    if set_status is not None:
        payload["setStatus"] = set_status
    if set_task_type is not None:
        payload["setTaskType"] = set_task_type
    if create_next_task_type is not None:
        payload["createNextTaskType"] = create_next_task_type
    return payload


def _stored_callback_count(
    isolated_config: Path,
    *,
    event: str,
    task_id: str,
    run_id: str,
) -> int:
    engine = make_engine(str(get_database_path(isolated_config)))
    session_local = make_session(engine)
    db = session_local()
    try:
        rows = db.query(Event).filter(Event.event_type == f"codex.{event}").all()
        count = 0
        for row in rows:
            payload = json.loads(row.payload_json)
            if payload.get("taskId") == task_id and payload.get("runId") == run_id:
                count += 1
        return count
    finally:
        db.close()


def _tasks_by_type(isolated_config: Path, task_type: str) -> list[Task]:
    engine = make_engine(str(get_database_path(isolated_config)))
    session_local = make_session(engine)
    db = session_local()
    try:
        return list(db.query(Task).filter(Task.task_type == task_type).all())
    finally:
        db.close()


def _task_note(isolated_config: Path, task_id: str):
    return frontmatter.loads((isolated_config / "vault" / "Tasks" / f"{task_id}.md").read_text())


def test_codex_events_require_auth(
    api_client: TestClient,
    auth_headers: dict[str, str],
    isolated_config: Path,
) -> None:
    task = _create_task(isolated_config, title="Auth callback task")

    response = api_client.post(
        "/codex/events",
        json=_callback_payload(str(task["id"]), event="started"),
    )

    assert response.status_code == 401


def test_started_callback_requires_explicit_working_status(
    api_client: TestClient,
    auth_headers: dict[str, str],
    isolated_config: Path,
) -> None:
    task = _create_task(isolated_config, title="Strict started callback")
    task_id = str(task["id"])
    payload = _callback_payload(task_id, event="started", run_id="run-started-missing-status")

    response = api_client.post("/codex/events", headers=auth_headers, json=payload)

    assert response.status_code == 400
    assert "setStatus=working" in response.json()["detail"]
    assert _stored_callback_count(
        isolated_config,
        event="started",
        task_id=task_id,
        run_id="run-started-missing-status",
    ) == 0

    current = api_client.get(f"/tasks/{task_id}", headers=auth_headers)
    assert current.status_code == 200
    assert current.json()["status"] == "idle"


def test_started_callback_is_idempotent_and_marks_task_working(
    api_client: TestClient,
    auth_headers: dict[str, str],
    isolated_config: Path,
) -> None:
    task = _create_task(isolated_config, title="Started callback task")
    task_id = str(task["id"])
    payload = _callback_payload(task_id, event="started", run_id="run-started", set_status="working")

    first = api_client.post("/codex/events", headers=auth_headers, json=payload)
    assert first.status_code == 200
    assert first.json()["duplicate"] is False
    assert first.json()["task"]["status"] == "working"

    second = api_client.post("/codex/events", headers=auth_headers, json=payload)
    assert second.status_code == 200
    assert second.json()["duplicate"] is True

    current = api_client.get(f"/tasks/{task_id}", headers=auth_headers)
    assert current.status_code == 200
    assert current.json()["status"] == "working"
    assert _stored_callback_count(
        isolated_config,
        event="started",
        task_id=task_id,
        run_id="run-started",
    ) == 1

    note = _task_note(isolated_config, task_id)
    assert note.metadata["status"] == "working"


@pytest.mark.parametrize(
    ("set_type", "expected_type"),
    [
        ("done", "done"),
        ("blocked", "blocked"),
    ],
)
def test_done_callback_applies_explicit_task_updates(
    api_client: TestClient,
    auth_headers: dict[str, str],
    isolated_config: Path,
    set_type: str,
    expected_type: str,
) -> None:
    task = _create_task(isolated_config, title=f"Done callback {set_type}")
    task_id = str(task["id"])
    payload = _callback_payload(
        task_id,
        event="done",
        run_id=f"run-{set_type}",
        set_status="idle",
        set_task_type=set_type,
        last_assistant_message=f"Outcome: {set_type}\nSummary: Codex finished.",
    )

    response = api_client.post("/codex/events", headers=auth_headers, json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["duplicate"] is False
    assert body["task"]["status"] == "idle"
    assert body["task"]["task_type"] == expected_type
    assert _stored_callback_count(
        isolated_config,
        event="done",
        task_id=task_id,
        run_id=f"run-{set_type}",
    ) == 1

    current = api_client.get(f"/tasks/{task_id}", headers=auth_headers)
    assert current.status_code == 200
    assert current.json()["status"] == "idle"
    assert current.json()["task_type"] == expected_type

    note = _task_note(isolated_config, task_id)
    assert note.metadata["status"] == "idle"
    assert note.metadata["task_type"] == expected_type


def test_done_callback_requires_explicit_actions(
    api_client: TestClient,
    auth_headers: dict[str, str],
    isolated_config: Path,
) -> None:
    task = _create_task(isolated_config, title="Strict coding completion")
    task_id = str(task["id"])
    payload = _callback_payload(
        task_id,
        event="done",
        run_id="run-missing-done-actions",
        last_assistant_message="Outcome: completed\nSummary: Codex finished.",
    )

    response = api_client.post("/codex/events", headers=auth_headers, json=payload)

    assert response.status_code == 400
    assert "requires setStatus" in response.json()["detail"]
    assert _stored_callback_count(
        isolated_config,
        event="done",
        task_id=task_id,
        run_id="run-missing-done-actions",
    ) == 0

    current = api_client.get(f"/tasks/{task_id}", headers=auth_headers)
    assert current.status_code == 200
    assert current.json()["status"] == "idle"
    assert current.json()["task_type"] == "coding"
    assert len(_tasks_by_type(isolated_config, "reviewing")) == 0


def test_done_callback_can_create_reviewing_followup_once(
    api_client: TestClient,
    auth_headers: dict[str, str],
    isolated_config: Path,
) -> None:
    task = _create_task(isolated_config, title="Coding followup callback")
    task_id = str(task["id"])
    payload = _callback_payload(
        task_id,
        event="done",
        run_id="run-create-review",
        set_status="idle",
        set_task_type="done",
        create_next_task_type="reviewing",
        last_assistant_message="Outcome: completed\nSummary: Ready for review.",
    )

    first = api_client.post("/codex/events", headers=auth_headers, json=payload)
    second = api_client.post("/codex/events", headers=auth_headers, json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["duplicate"] is True
    reviews = _tasks_by_type(isolated_config, "reviewing")
    assert len(reviews) == 1
    assert reviews[0].repository_id == task["repository_id"]
    assert reviews[0].title.startswith("Review: Coding followup callback")


def test_reviewing_rejection_marks_review_task_blocked(
    api_client: TestClient,
    auth_headers: dict[str, str],
    isolated_config: Path,
) -> None:
    task = _create_task(isolated_config, title="Review rejection callback", task_type="reviewing")
    task_id = str(task["id"])
    payload = _callback_payload(
        task_id,
        event="done",
        run_id="run-review-reject",
        task_type="reviewing",
        set_status="idle",
        set_task_type="blocked",
        last_assistant_message="Outcome: completed\nDecision: rejected\nSummary: Needs changes.",
    )

    response = api_client.post("/codex/events", headers=auth_headers, json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["task"]["status"] == "idle"
    assert body["task"]["task_type"] == "blocked"

    current = api_client.get(f"/tasks/{task_id}", headers=auth_headers)
    assert current.status_code == 200
    assert current.json()["task_type"] == "blocked"
