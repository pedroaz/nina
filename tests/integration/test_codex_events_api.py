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


def _create_task(
    isolated_config: Path, *, title: str, task_type: str = "coding"
) -> dict[str, object]:
    engine = make_engine(str(get_database_path(isolated_config)))
    session_local = make_session(engine)
    db = session_local()
    try:
        repo_path = isolated_config / "events-repo"
        repo_path.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "init", str(repo_path)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
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
    pipeline_stage: str | None = None,
    set_status: str | None = None,
    set_task_type: str | None = None,
    set_pipeline_stage: str | None = None,
    set_pipeline_error: str | None = None,
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
    if pipeline_stage is not None:
        payload["pipelineStage"] = pipeline_stage
    if set_status is not None:
        payload["setStatus"] = set_status
    if set_task_type is not None:
        payload["setTaskType"] = set_task_type
    if set_pipeline_stage is not None:
        payload["setPipelineStage"] = set_pipeline_stage
    if set_pipeline_error is not None:
        payload["setPipelineError"] = set_pipeline_error
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
    assert (
        _stored_callback_count(
            isolated_config,
            event="started",
            task_id=task_id,
            run_id="run-started-missing-status",
        )
        == 0
    )

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
    payload = _callback_payload(
        task_id,
        event="started",
        run_id="run-started",
        set_status="working",
        set_pipeline_stage="created",
    )

    first = api_client.post("/codex/events", headers=auth_headers, json=payload)
    assert first.status_code == 200
    assert first.json()["duplicate"] is False
    assert first.json()["task"]["status"] == "working"
    assert first.json()["task"]["pipeline_stage"] == "created"

    second = api_client.post("/codex/events", headers=auth_headers, json=payload)
    assert second.status_code == 200
    assert second.json()["duplicate"] is True

    current = api_client.get(f"/tasks/{task_id}", headers=auth_headers)
    assert current.status_code == 200
    assert current.json()["status"] == "working"
    assert current.json()["pipeline_stage"] == "created"
    assert (
        _stored_callback_count(
            isolated_config,
            event="started",
            task_id=task_id,
            run_id="run-started",
        )
        == 1
    )

    note = _task_note(isolated_config, task_id)
    assert note.metadata["status"] == "working"
    assert note.metadata["pipeline_stage"] == "created"


@pytest.mark.parametrize(
    ("set_type", "expected_type", "expected_stage"),
    [
        ("done", "done", "done"),
        ("blocked", "blocked", "blocked"),
    ],
)
def test_done_callback_applies_explicit_task_and_stage_updates(
    api_client: TestClient,
    auth_headers: dict[str, str],
    isolated_config: Path,
    set_type: str,
    expected_type: str,
    expected_stage: str,
) -> None:
    task = _create_task(isolated_config, title=f"Done callback {set_type}")
    task_id = str(task["id"])
    payload = _callback_payload(
        task_id,
        event="done",
        run_id=f"run-{set_type}",
        set_status="idle",
        set_task_type=set_type,
        set_pipeline_stage=expected_stage,
        last_assistant_message=f"Outcome: {set_type}\nSummary: Codex finished.",
    )

    response = api_client.post("/codex/events", headers=auth_headers, json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["duplicate"] is False
    assert body["task"]["status"] == "idle"
    assert body["task"]["task_type"] == expected_type
    assert body["task"]["pipeline_stage"] == expected_stage
    assert (
        _stored_callback_count(
            isolated_config,
            event="done",
            task_id=task_id,
            run_id=f"run-{set_type}",
        )
        == 1
    )

    current = api_client.get(f"/tasks/{task_id}", headers=auth_headers)
    assert current.status_code == 200
    assert current.json()["status"] == "idle"
    assert current.json()["task_type"] == expected_type
    assert current.json()["pipeline_stage"] == expected_stage

    note = _task_note(isolated_config, task_id)
    assert note.metadata["status"] == "idle"
    assert note.metadata["task_type"] == expected_type
    assert note.metadata["pipeline_stage"] == expected_stage
    assert "## Prompt" in note.content
    assert "No prompt captured yet." in note.content
    assert "## Summary" in note.content
    assert f"Outcome: {set_type}" in note.content


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
    assert (
        _stored_callback_count(
            isolated_config,
            event="done",
            task_id=task_id,
            run_id="run-missing-done-actions",
        )
        == 0
    )

    current = api_client.get(f"/tasks/{task_id}", headers=auth_headers)
    assert current.status_code == 200
    assert current.json()["status"] == "idle"
    assert current.json()["task_type"] == "coding"
    assert current.json()["pipeline_stage"] == "created"
    assert len(_tasks_by_type(isolated_config, "reviewing")) == 0


def test_done_callback_tracks_pipeline_and_rework_count(
    api_client: TestClient,
    auth_headers: dict[str, str],
    isolated_config: Path,
) -> None:
    task = _create_task(isolated_config, title="Pipeline tracking callback")
    task_id = str(task["id"])

    coding_payload = _callback_payload(
        task_id,
        event="done",
        run_id="run-created-to-coding",
        set_status="idle",
        set_pipeline_stage="coding",
        last_assistant_message="Outcome: completed\nSummary: Initial implementation plan.",
    )
    coding_response = api_client.post("/codex/events", headers=auth_headers, json=coding_payload)
    assert coding_response.status_code == 200
    assert coding_response.json()["task"]["pipeline_stage"] == "coding"

    testing_payload = _callback_payload(
        task_id,
        event="done",
        run_id="run-coding-to-testing",
        set_status="idle",
        set_pipeline_stage="testing",
        last_assistant_message="Outcome: completed\nSummary: Code implemented.",
    )
    testing_response = api_client.post("/codex/events", headers=auth_headers, json=testing_payload)
    assert testing_response.status_code == 200
    assert testing_response.json()["task"]["pipeline_stage"] == "testing"

    blocked_payload = _callback_payload(
        task_id,
        event="done",
        run_id="run-testing-to-blocked",
        set_status="idle",
        set_pipeline_stage="blocked",
        set_pipeline_error="Tests are failing",
        last_assistant_message="Outcome: blocked\nBlockers: Tests are failing",
    )
    blocked_response = api_client.post("/codex/events", headers=auth_headers, json=blocked_payload)
    assert blocked_response.status_code == 200
    blocked_task = blocked_response.json()["task"]
    assert blocked_task["pipeline_stage"] == "blocked"
    assert blocked_task["pipeline_rework_count"] == 1
    assert blocked_task["pipeline_error"] == "Tests are failing"

    current = api_client.get(f"/tasks/{task_id}", headers=auth_headers)
    assert current.status_code == 200
    assert current.json()["pipeline_stage"] == "blocked"
    assert current.json()["pipeline_rework_count"] == 1
    assert current.json()["pipeline_error"] == "Tests are failing"
    note = _task_note(isolated_config, task_id)
    assert note.metadata["pipeline_stage"] == "blocked"
    assert "Outcome: blocked" in note.content

    done_payload = _callback_payload(
        task_id,
        event="done",
        run_id="run-blocked-to-done",
        set_status="idle",
        set_task_type="done",
        set_pipeline_stage="done",
        last_assistant_message="Outcome: completed\nSummary: Finished after unblock.",
    )
    done_response = api_client.post("/codex/events", headers=auth_headers, json=done_payload)
    assert done_response.status_code == 200
    done_task = done_response.json()["task"]
    assert done_task["pipeline_stage"] == "done"
    assert done_task["pipeline_error"] is None

    current = api_client.get(f"/tasks/{task_id}", headers=auth_headers)
    assert current.status_code == 200
    assert current.json()["pipeline_error"] is None
    note = _task_note(isolated_config, task_id)
    assert note.metadata["pipeline_stage"] == "done"
    assert note.metadata["pipeline_error"] is None


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
        set_pipeline_stage="done",
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
        set_pipeline_stage="blocked",
        set_pipeline_error="Missing validation",
        last_assistant_message=(
            "Outcome: completed\n"
            "Decision: rejected\n"
            "Blockers: Missing validation\n"
            "Summary: Needs changes."
        ),
    )

    response = api_client.post("/codex/events", headers=auth_headers, json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["task"]["status"] == "idle"
    assert body["task"]["task_type"] == "blocked"
    assert body["task"]["pipeline_stage"] == "blocked"
    assert body["task"]["pipeline_error"] == "Missing validation"

    current = api_client.get(f"/tasks/{task_id}", headers=auth_headers)
    assert current.status_code == 200
    assert current.json()["task_type"] == "blocked"
    assert current.json()["pipeline_stage"] == "blocked"
    assert current.json()["pipeline_error"] == "Missing validation"
