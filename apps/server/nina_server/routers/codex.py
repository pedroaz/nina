from __future__ import annotations

import json
import uuid
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from nina_core.codex import CodexError, CodexExecResult, Project
from nina_core.models.models import TASK_AGENT_STATUSES, TASK_TYPES, Event

from nina_core.tasks.service import TaskService

from ..dependencies import get_db_session, get_obsidian


router = APIRouter()


class CodexExecRequest(BaseModel):
    prompt: str
    json_mode: bool = Field(False, alias="json")


class CodexEventRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    version: int
    event: Literal["started", "done"]
    source: str | None = None
    task_id: str = Field(alias="taskId")
    run_id: str = Field(alias="runId")
    session_id: str | None = Field(default=None, alias="sessionId")
    turn_id: str | None = Field(default=None, alias="turnId")
    cwd: str | None = None
    task_type: str | None = Field(default=None, alias="taskType")
    set_task_type: str | None = Field(default=None, alias="setTaskType")
    set_status: str | None = Field(default=None, alias="setStatus")
    create_next_task_type: str | None = Field(default=None, alias="createNextTaskType")
    last_assistant_message: str | None = Field(default=None, alias="lastAssistantMessage")
    sent_at: str | None = Field(default=None, alias="sentAt")


def _codex_supervisor(request: Request) -> Any | None:
    """Return the live supervisor, or None if the daemon didn't start one."""

    supervisor = getattr(request.app.state, "codex", None)
    if supervisor is None:
        return None
    return supervisor


def _serialize_project(project: Project) -> dict[str, Any]:
    return {
        "id": project.id,
        "worktree": project.worktree,
        "vcs": project.vcs,
        "time": {
            "created": project.time.created,
            "updated": project.time.updated,
        },
        "sandboxes": list(project.sandboxes or []),
    }


def _event_payload(payload: CodexEventRequest) -> dict[str, Any]:
    return payload.model_dump(by_alias=True)


def _find_existing_codex_event(
    db: Any,
    *,
    task_id: str,
    run_id: str,
    event: str,
) -> Event | None:
    rows = db.query(Event).filter(Event.event_type == f"codex.{event}").all()
    for row in rows:
        try:
            payload = json.loads(row.payload_json)
        except json.JSONDecodeError:
            continue
        if (
            payload.get("taskId") == task_id
            and payload.get("runId") == run_id
            and payload.get("event") == event
        ):
            return row
    return None


def _task_snapshot(task: Any) -> dict[str, str | None]:
    return {
        "id": task.id,
        "task_type": task.task_type,
        "status": task.status,
        "repository_id": task.repository_id,
    }


def _activity_for_codex_event(payload: CodexEventRequest) -> str:
    label = payload.task_type or "task"
    if payload.event == "started":
        return f"Codex {label} started (run {payload.run_id})."
    parts = [f"Codex {label} finished (run {payload.run_id})."]
    if payload.set_task_type:
        parts.append(f"set task_type={payload.set_task_type}")
    if payload.set_status:
        parts.append(f"set status={payload.set_status}")
    if payload.create_next_task_type:
        parts.append(f"created next task_type={payload.create_next_task_type}")
    return " ".join(parts)


def _followup_description(parent: Any, final_message: str | None) -> str:
    details = (final_message or parent.description or "").strip()
    if details:
        return f"Follow-up from task {parent.id}: {parent.title}\n\n{details}"
    return f"Follow-up from task {parent.id}: {parent.title}"


def _event_actions(payload: CodexEventRequest, task: Any) -> tuple[dict[str, Any], str | None]:
    update_kwargs: dict[str, Any] = {}
    task_type = payload.task_type or getattr(task, "task_type", None)

    if payload.set_status is not None and payload.set_status not in TASK_AGENT_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid setStatus: {payload.set_status}")
    if payload.set_task_type is not None and payload.set_task_type not in TASK_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid setTaskType: {payload.set_task_type}")
    if payload.create_next_task_type is not None and payload.create_next_task_type not in TASK_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid createNextTaskType: {payload.create_next_task_type}")

    if payload.event == "started":
        if payload.set_status != "working":
            raise HTTPException(status_code=400, detail="started callback requires setStatus=working")
        if payload.set_task_type is not None or payload.create_next_task_type is not None:
            raise HTTPException(status_code=400, detail="started callback only supports setStatus")
        update_kwargs["status"] = payload.set_status
        return update_kwargs, None

    if payload.set_status is None:
        raise HTTPException(status_code=400, detail="done callback requires setStatus")
    update_kwargs["status"] = payload.set_status

    if task_type in {"coding", "reviewing"} and payload.set_task_type is None:
        raise HTTPException(status_code=400, detail=f"done callback for {task_type} requires setTaskType")
    if payload.set_task_type is not None:
        update_kwargs["task_type"] = payload.set_task_type
    return update_kwargs, payload.create_next_task_type


def _followup_title(next_task_type: str, parent: Any) -> str:
    title_prefix = "Review" if next_task_type == "reviewing" else next_task_type.title()
    return f"{title_prefix}: {parent.title}"


def _find_existing_followup(service: TaskService, parent: Any, next_task_type: str) -> Any | None:
    expected_title = _followup_title(next_task_type, parent)
    expected_description_prefix = f"Follow-up from task {parent.id}:"
    for task in service.list(task_type=next_task_type, repository_id=parent.repository_id):
        if task.title == expected_title and (task.description or "").startswith(expected_description_prefix):
            return task
    return None


def _ensure_followup_task(
    service: TaskService,
    parent: Any,
    next_task_type: str,
    final_message: str | None,
) -> Any | None:
    existing = _find_existing_followup(service, parent, next_task_type)
    if existing is not None:
        return None
    followup = service.create(
        _followup_title(next_task_type, parent),
        description=_followup_description(parent, final_message),
        repository_id=parent.repository_id,
        task_type=next_task_type,
        auto_classify=False,
    )
    service.add_activity(followup.id, f"Created from task {parent.id}.")
    service.add_activity(parent.id, f"Created {next_task_type} task {followup.id}.")
    return followup


@router.get("/codex/status")
async def codex_status(request: Request) -> Any:
    supervisor = _codex_supervisor(request)
    if supervisor is None:
        return JSONResponse(
            status_code=503,
            content={"detail": "daemon supervisor not initialized"},
        )
    return supervisor.status().model_dump()


@router.get("/codex/health")
async def codex_health(request: Request) -> Any:
    """Report whether the local codex integration is healthy."""

    supervisor = _codex_supervisor(request)
    if supervisor is None:
        return JSONResponse(
            status_code=503,
            content={"detail": "daemon supervisor not initialized"},
        )
    status = supervisor.status()
    if status.state != "running":
        return JSONResponse(
            status_code=503,
            content={"detail": f"codex is {status.state}", "status": status.model_dump()},
        )
    client = supervisor.client()
    try:
        health = await client.health()
    except CodexError as exc:
        return JSONResponse(
            status_code=502,
            content={"detail": str(exc), "status": status.model_dump()},
        )
    finally:
        try:
            await client.aclose()
        except Exception:  # noqa: BLE001
            pass
    return {"healthy": health.healthy, "version": health.version, "status": status.model_dump()}


@router.get("/codex/projects")
async def codex_projects(request: Request) -> Any:
    supervisor = _codex_supervisor(request)
    if supervisor is None:
        return JSONResponse(
            status_code=503,
            content={"detail": "daemon supervisor not initialized"},
        )
    client = supervisor.client()
    try:
        projects = await client.list_projects()
    except CodexError as exc:
        return JSONResponse(status_code=502, content={"detail": str(exc)})
    finally:
        try:
            await client.aclose()
        except Exception:  # noqa: BLE001
            pass
    return [_serialize_project(project) for project in projects]


@router.get("/codex/projects/current")
async def codex_current_project(request: Request) -> Any:
    supervisor = _codex_supervisor(request)
    if supervisor is None:
        return JSONResponse(
            status_code=503,
            content={"detail": "daemon supervisor not initialized"},
        )
    client = supervisor.client()
    try:
        project = await client.current_project()
    except CodexError as exc:
        return JSONResponse(status_code=502, content={"detail": str(exc)})
    finally:
        try:
            await client.aclose()
        except Exception:  # noqa: BLE001
            pass
    return _serialize_project(project)


@router.post("/codex/exec")
async def codex_exec(request: Request, payload: CodexExecRequest) -> Any:
    supervisor = _codex_supervisor(request)
    if supervisor is None:
        return JSONResponse(
            status_code=503,
            content={"detail": "daemon supervisor not initialized"},
        )
    client = supervisor.client()
    try:
        result: CodexExecResult = await client.exec(payload.prompt, json_mode=payload.json_mode)
    except CodexError as exc:
        return JSONResponse(
            status_code=502,
            content={
                "detail": str(exc),
                "stdout": getattr(exc, "stdout", None),
                "stderr": getattr(exc, "stderr", None),
            },
        )
    finally:
        try:
            await client.aclose()
        except Exception:  # noqa: BLE001
            pass
    response: dict[str, Any] = {
        "stdout": result.stdout,
        "stderr": result.stderr,
        "exit_code": result.exit_code,
    }
    if result.json_payload is not None:
        response["json"] = result.json_payload
    return response


@router.post("/codex/events")
async def codex_event(payload: CodexEventRequest) -> dict[str, Any]:
    with get_db_session() as db:
        service = TaskService(db, get_obsidian())
        task = service.get(payload.task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")

        update_kwargs, next_task_type = _event_actions(payload, task)
        duplicate = (
            _find_existing_codex_event(
                db,
                task_id=payload.task_id,
                run_id=payload.run_id,
                event=payload.event,
            )
            is not None
        )

        if duplicate:
            return {
                "accepted": True,
                "duplicate": True,
                "event": payload.event,
                "taskId": payload.task_id,
                "runId": payload.run_id,
                "task": _task_snapshot(task),
            }

        try:
            db.add(
                Event(
                    id=str(uuid.uuid4()),
                    event_type=f"codex.{payload.event}",
                    payload_json=json.dumps(_event_payload(payload), sort_keys=True),
                )
            )
            task = service.update(payload.task_id, **update_kwargs)
            if task is None:
                raise HTTPException(status_code=404, detail="Task not found")
            if next_task_type:
                _ensure_followup_task(service, task, next_task_type, payload.last_assistant_message)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        service.add_activity(payload.task_id, _activity_for_codex_event(payload))

        return {
            "accepted": True,
            "duplicate": False,
            "event": payload.event,
            "taskId": payload.task_id,
            "runId": payload.run_id,
            "task": _task_snapshot(task),
        }

