from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from nina_core.config import get_codex_task_logs_dir
from nina_core.repositories.service import RepositoryService
from nina_core.tasks.service import TaskService
from nina_core.workflows.runner import WorkflowRunner

from ..dependencies import _request_config, _request_config_dir, get_db_session, get_obsidian
from ..schemas import TaskCreate, TaskResponse, TaskRunRequest, TaskUpdate


router = APIRouter()
logger = logging.getLogger(__name__)


def _task_to_response(t: Any, repository: Any | None = None) -> TaskResponse:
    return TaskResponse(
        id=t.id,
        repository_id=t.repository_id or None,
        repository_name=getattr(repository, "name", None),
        repository_path=getattr(repository, "path", None),
        title=t.title,
        description=t.description,
        task_type=t.task_type,
        status=t.status,
        classified_at=t.classified_at,
        classification_reason=t.classification_reason,
        classification_model=t.classification_model,
        created_at=t.created_at,
        updated_at=t.updated_at,
    )


def _task_responses(db: Any, tasks: list[Any]) -> list[TaskResponse]:
    repo_service = RepositoryService(db)
    repos = {repo.id: repo for repo in repo_service.list()}
    return [_task_to_response(task, repos.get(task.repository_id)) for task in tasks]


def _safe_log_name(value: str) -> str:
    return value.replace("/", "_").replace(chr(92), "_")


def _task_log_dir(request: Request, task_id: str) -> Path:
    return get_codex_task_logs_dir(_request_config_dir(request)) / _safe_log_name(task_id)


def _log_runs(task_dir: Path) -> list[dict[str, str]]:
    if not task_dir.exists():
        return []
    files = sorted(task_dir.glob("*.log"), key=lambda path: path.stat().st_mtime, reverse=True)
    return [{"run_id": path.stem, "path": str(path)} for path in files]


@router.get("/tasks", response_model=list[TaskResponse])
async def list_tasks(
    request: Request,
    task_type: str | None = None,
    status: str | None = None,
    include_archived: bool = False,
    repository_id: str | None = None,
) -> list[TaskResponse]:
    with get_db_session() as db:
        obsidian = get_obsidian()
        service = TaskService(db, obsidian)
        tasks = service.list(
            task_type=task_type,
            status=status,
            include_archived=include_archived,
            repository_id=repository_id,
        )
        return _task_responses(db, tasks)


@router.post("/tasks", response_model=TaskResponse)
async def create_task(request: Request, data: TaskCreate) -> TaskResponse:
    wants_run = data.auto_run or data.auto_run_background
    with get_db_session() as db:
        obsidian = get_obsidian()
        service = TaskService(db, obsidian)
        try:
            task = service.create(
                data.title,
                data.description,
                repository_id=data.repository_id,
                task_type=data.task_type or "unclassified",
                auto_classify=data.auto_classify and not wants_run,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        task_id = task.id
        if not wants_run:
            return _task_to_response(task, RepositoryService(db).get(task.repository_id))

    run_input = _task_run_input(
        request,
        task_id,
        TaskRunRequest(
            background=data.auto_run_background,
        ),
    )
    if data.auto_run_background:
        _queue_task_run(task_id, _active_db_path(request), _request_config(request), run_input)
        with get_db_session() as db:
            task = TaskService(db, get_obsidian()).get(task_id)
            if not task:
                raise HTTPException(status_code=404, detail="Not found")
            return _task_to_response(task, RepositoryService(db).get(task.repository_id))

    runner = WorkflowRunner(_active_db_path(request), config=_request_config(request))
    result = runner.run("run-task", run_input)
    if result.get("status") != "completed":
        raise HTTPException(status_code=400, detail=result)
    with get_db_session() as db:
        task = TaskService(db, get_obsidian()).get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Not found")
        return _task_to_response(task, RepositoryService(db).get(task.repository_id))


@router.get("/tasks/grouped-by-type")
async def tasks_grouped_by_type(request: Request) -> dict[str, list[TaskResponse]]:
    """Return active tasks grouped by `task_type`, sorted by `classified_at` desc.

    Replaces the legacy `/kanban` endpoint. The shape is `{type: [task, ...]}`.
    """

    with get_db_session() as db:
        obsidian = get_obsidian()
        service = TaskService(db, obsidian)
        tasks = service.list()
        repos = {repo.id: repo for repo in RepositoryService(db).list()}
        grouped: dict[str, list[TaskResponse]] = {}
        for task in tasks:
            grouped.setdefault(task.task_type, []).append(
                _task_to_response(task, repos.get(task.repository_id))
            )
        return grouped


@router.get("/tickets", response_model=list[TaskResponse])
async def list_tickets(
    request: Request,
    task_type: str | None = None,
    status: str | None = None,
    include_archived: bool = False,
) -> list[TaskResponse]:
    return await list_tasks(
        request,
        task_type=task_type,
        status=status,
        include_archived=include_archived,
    )


@router.post("/tickets", response_model=TaskResponse)
async def create_ticket(request: Request, data: TaskCreate) -> TaskResponse:
    return await create_task(request, data)


@router.get("/tickets/{ticket_id}", response_model=TaskResponse)
async def get_ticket(request: Request, ticket_id: str) -> TaskResponse:
    return await get_task(request, ticket_id)


@router.patch("/tickets/{ticket_id}", response_model=TaskResponse)
async def update_ticket(request: Request, ticket_id: str, data: TaskUpdate) -> TaskResponse:
    return await update_task(request, ticket_id, data)


@router.delete("/tickets/{ticket_id}")
async def delete_ticket(request: Request, ticket_id: str) -> dict[str, bool]:
    return await delete_task(request, ticket_id)


@router.post("/tickets/{ticket_id}/classify")
async def classify_ticket(request: Request, ticket_id: str) -> dict[str, Any]:
    return await classify_task(request, ticket_id)


@router.post("/tickets/{ticket_id}/run")
async def run_ticket(request: Request, ticket_id: str) -> dict[str, Any]:
    return await run_task(request, ticket_id)


@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(request: Request, task_id: str) -> TaskResponse:
    with get_db_session() as db:
        obsidian = get_obsidian()
        service = TaskService(db, obsidian)
        task = service.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Not found")
        return _task_to_response(task, RepositoryService(db).get(task.repository_id))


@router.get("/tasks/{task_id}/codex-logs")
async def task_codex_logs(
    request: Request,
    task_id: str,
    tail: int = 200,
    run_id: str | None = None,
) -> dict[str, Any]:
    with get_db_session() as db:
        task = TaskService(db, get_obsidian()).get(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Not found")

    task_dir = _task_log_dir(request, task_id)
    runs = _log_runs(task_dir)
    selected_run_id = run_id or (runs[0]["run_id"] if runs else None)
    if selected_run_id is None:
        return {
            "task_id": task_id,
            "run_id": None,
            "path": str(task_dir),
            "lines": [],
            "tail": tail,
            "runs": runs,
        }

    log_path = task_dir / f"{_safe_log_name(selected_run_id)}.log"
    if not log_path.exists():
        raise HTTPException(status_code=404, detail="Log run not found")
    lines = log_path.read_text(errors="replace").splitlines()
    if tail >= 0:
        lines = lines[-tail:] if tail > 0 else []
    return {
        "task_id": task_id,
        "run_id": selected_run_id,
        "path": str(log_path),
        "lines": lines,
        "tail": tail,
        "runs": runs,
    }


@router.patch("/tasks/{task_id}", response_model=TaskResponse)
async def update_task(request: Request, task_id: str, data: TaskUpdate) -> TaskResponse:
    with get_db_session() as db:
        obsidian = get_obsidian()
        service = TaskService(db, obsidian)
        try:
            task = service.update(
                task_id,
                title=data.title,
                description=data.description,
                task_type=data.task_type,
                status=data.status,
                repository_id=(
                    (data.repository_id or "")
                    if "repository_id" in data.model_fields_set
                    else None
                ),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        if not task:
            raise HTTPException(status_code=404, detail="Not found")
        return _task_to_response(task, RepositoryService(db).get(task.repository_id))


@router.delete("/tasks/{task_id}")
async def delete_task(request: Request, task_id: str) -> dict[str, bool]:
    with get_db_session() as db:
        obsidian = get_obsidian()
        service = TaskService(db, obsidian)
        if not service.delete(task_id):
            raise HTTPException(status_code=404, detail="Not found")
    return {"deleted": True}


@router.post("/tasks/{task_id}/classify")
async def classify_task(request: Request, task_id: str) -> dict[str, Any]:
    db_path = _active_db_path(request)
    config = _request_config(request)
    runner = WorkflowRunner(db_path, config=config)
    result = runner.run("classify-task", {"task_id": task_id})
    if result.get("status") != "completed":
        raise HTTPException(status_code=400, detail=result)
    return result


@router.post("/tasks/{task_id}/run")
async def run_task(
    request: Request,
    task_id: str,
    data: TaskRunRequest | None = None,
) -> dict[str, Any]:
    db_path = _active_db_path(request)
    config = _request_config(request)
    run_input = _task_run_input(request, task_id, data)
    if data is not None and data.background:
        with get_db_session() as db:
            task = TaskService(db, get_obsidian()).get(task_id)
            if task is None:
                raise HTTPException(status_code=404, detail="Not found")
        _queue_task_run(task_id, db_path, config, run_input)
        return {"status": "queued", "task_id": task_id, "background": True}

    runner = WorkflowRunner(db_path, config=config)
    result = runner.run("run-task", run_input)
    if result.get("status") != "completed":
        raise HTTPException(status_code=400, detail=result)
    return result


@router.post("/tasks/{task_id}/archive", response_model=TaskResponse)
async def archive_task(request: Request, task_id: str) -> TaskResponse:
    with get_db_session() as db:
        obsidian = get_obsidian()
        service = TaskService(db, obsidian)
        task = service.archive(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Not found")
        return _task_to_response(task, RepositoryService(db).get(task.repository_id))


@router.post("/tasks/{task_id}/unarchive", response_model=TaskResponse)
async def unarchive_task(request: Request, task_id: str) -> TaskResponse:
    with get_db_session() as db:
        obsidian = get_obsidian()
        service = TaskService(db, obsidian)
        task = service.unarchive(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Not found")
        return _task_to_response(task, RepositoryService(db).get(task.repository_id))


def _task_run_input(
    request: Request,
    task_id: str,
    data: TaskRunRequest | None = None,
) -> dict[str, Any]:
    config = _request_config(request)
    host = config.daemon_host if config.daemon_host not in {"0.0.0.0", "::"} else "127.0.0.1"
    payload: dict[str, Any] = {
        "task_id": task_id,
        "nina_base_url": f"http://{host}:{config.daemon_port}",
        "nina_token": getattr(request.app.state, "token", "") or "",
    }
    if data is not None:
        if data.codex_timeout_seconds is not None:
            payload["codex_timeout_seconds"] = data.codex_timeout_seconds
    return payload


def _queue_task_run(
    task_id: str,
    db_path: str,
    config: Any,
    run_input: dict[str, Any],
) -> None:
    logger.info("nina.task task=%s event=queued workflow=run-task", task_id)
    with get_db_session() as db:
        service = TaskService(db, get_obsidian())
        task = service.get(task_id)
        if task is not None:
            service.update(task_id, status="working")
            service.add_activity(task_id, "Queued for Nina/Codex run.")

    def _worker() -> None:
        logger.info("nina.task task=%s event=background_started workflow=run-task", task_id)
        runner = WorkflowRunner(db_path, config=config)
        result = runner.run("run-task", run_input)
        logger.info(
            "nina.task task=%s event=background_finished workflow=run-task status=%s",
            task_id,
            result.get("status"),
        )
        if result.get("status") == "failed":
            error = str(result.get("output", {}).get("error") or "background run failed")
            logger.error("nina.task task=%s event=background_failed error=%s", task_id, error[:500])
            with get_db_session() as db:
                service = TaskService(db, get_obsidian())
                task = service.get(task_id)
                if task is not None:
                    service.update(task_id, status="error")
                    service.add_activity(task_id, f"Nina/Codex run failed: {error[:500]}")

    thread = threading.Thread(target=_worker, name=f"nina-task-run-{task_id}", daemon=True)
    thread.start()


def _active_db_path(request: Request) -> str:
    config = _request_config(request)
    return config.database_path
