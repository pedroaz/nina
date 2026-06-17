import os
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from starlette.middleware.base import BaseHTTPMiddleware

from nina_core.config import (
    NinaConfig,
    ensure_vault_structure,
    get_config_dir,
    get_config_path,
    load_effective_config,
    merge_config,
)
from nina_core.db import create_database
from nina_core.llm.provider import LLMRequest, LLMService
from nina_core.obsidian.service import ObsidianService
from nina_core.projects.kanban import get_kanban_board, move_task
from nina_core.projects.service import ProjectService, TaskService
from nina_core.scheduler.service import SchedulerService
from nina_core.search.indexer import ask_obsidian, index_notes, search, create_fts_table
from nina_core.sessions.service import SessionService
import nina_core
from nina_core.workflows.runner import WorkflowRunner

app = FastAPI(title="Nina Daemon", version=nina_core.__version__)


class LLMConfigResponse(BaseModel):
    provider: str
    model: str
    base_url: str | None = None


class ResearchConfigResponse(BaseModel):
    provider: str
    model: str


class SchedulerConfigResponse(BaseModel):
    daily_summary_time: str


class TranscriptionConfigResponse(BaseModel):
    backend: str
    model: str
    device: str
    compute_type: str
    language: str | None = None


class MeetingsConfigResponse(BaseModel):
    default_source: str
    auto_summarize: bool
    sample_rate: int
    channels: int
    open_command: str
    play_command: str
    default_gain: float
    auto_normalize: bool
    normalize_target_dbfs: float
    noise_reduction: str


class ConfigResponse(BaseModel):
    profile: str
    config_dir: str
    config_path: str
    vault_path: str
    database_path: str
    daemon_host: str
    daemon_port: int
    llm: LLMConfigResponse
    research: ResearchConfigResponse
    scheduler: SchedulerConfigResponse
    transcription: TranscriptionConfigResponse
    meetings: MeetingsConfigResponse
    log_level: str


class LLMConfigUpdate(BaseModel):
    provider: str | None = None
    model: str | None = None
    base_url: str | None = None


class ResearchConfigUpdate(BaseModel):
    provider: str | None = None
    model: str | None = None


class SchedulerConfigUpdate(BaseModel):
    daily_summary_time: str | None = None


class TranscriptionConfigUpdate(BaseModel):
    backend: str | None = None
    model: str | None = None
    device: str | None = None
    compute_type: str | None = None
    language: str | None = None


class MeetingsConfigUpdate(BaseModel):
    default_source: str | None = None
    auto_summarize: bool | None = None
    sample_rate: int | None = None
    channels: int | None = None
    open_command: str | None = None
    play_command: str | None = None
    default_gain: float | None = None
    auto_normalize: bool | None = None
    normalize_target_dbfs: float | None = None
    noise_reduction: str | None = None


class ConfigUpdate(BaseModel):
    vault_path: str | None = None
    database_path: str | None = None
    daemon_host: str | None = None
    daemon_port: int | None = None
    log_level: str | None = None
    llm: LLMConfigUpdate | None = None
    research: ResearchConfigUpdate | None = None
    scheduler: SchedulerConfigUpdate | None = None
    transcription: TranscriptionConfigUpdate | None = None
    meetings: MeetingsConfigUpdate | None = None


def _request_config_dir(request: Request) -> Path:
    config_dir = getattr(request.app.state, "config_dir", None)
    if config_dir is not None:
        return Path(config_dir)
    profile = getattr(request.app.state, "profile", os.environ.get("NINA_PROFILE", "default"))
    return get_config_dir(str(profile))


def _request_config(request: Request) -> NinaConfig:
    config = getattr(request.app.state, "config", None)
    if isinstance(config, NinaConfig):
        return config
    config_dir = _request_config_dir(request)
    return load_effective_config(config_dir)


def _config_response(config_dir: Path, config: NinaConfig) -> ConfigResponse:
    return ConfigResponse(
        profile=config.profile,
        config_dir=str(config_dir),
        config_path=str(get_config_path(config_dir)),
        vault_path=config.vault_path,
        database_path=config.database_path,
        daemon_host=config.daemon_host,
        daemon_port=config.daemon_port,
        llm=LLMConfigResponse(
            provider=config.llm.provider,
            model=config.llm.model,
            base_url=config.llm.base_url,
        ),
        research=ResearchConfigResponse(
            provider=config.research.provider,
            model=config.research.model,
        ),
        scheduler=SchedulerConfigResponse(daily_summary_time=config.scheduler.daily_summary_time),
        transcription=TranscriptionConfigResponse(
            backend=config.transcription.backend,
            model=config.transcription.model,
            device=config.transcription.device,
            compute_type=config.transcription.compute_type,
            language=config.transcription.language,
        ),
        meetings=MeetingsConfigResponse(
            default_source=config.meetings.default_source,
            auto_summarize=config.meetings.auto_summarize,
            sample_rate=config.meetings.sample_rate,
            channels=config.meetings.channels,
            open_command=config.meetings.open_command,
            play_command=config.meetings.play_command,
            default_gain=config.meetings.default_gain,
            auto_normalize=config.meetings.auto_normalize,
            normalize_target_dbfs=config.meetings.normalize_target_dbfs,
            noise_reduction=config.meetings.noise_reduction,
        ),
        log_level=config.log_level,
    )


def apply_runtime_config(app: FastAPI, config_dir: Path, config: NinaConfig) -> NinaConfig:
    """Resolve paths and stash the active NinaConfig on the FastAPI app.

    We deliberately do NOT mirror settings into `NINA_*` environment
    variables. The config file is the single source of truth; services
    read it via `load_effective_config` or by being passed the typed
    `NinaConfig`. Bootstrap env vars (`NINA_CONFIG_DIR`, `NINA_TOKEN`)
    are set by the launcher before this function runs.
    """
    resolved = config.with_resolved_paths(config_dir)
    app.state.profile = resolved.profile
    app.state.config_dir = config_dir
    app.state.config_path = get_config_path(config_dir)
    app.state.config = resolved
    return resolved


def _changed_config_fields(previous: NinaConfig, updated: NinaConfig) -> list[str]:
    changed: list[str] = []
    if previous.vault_path != updated.vault_path:
        changed.append("vault_path")
    if previous.database_path != updated.database_path:
        changed.append("database_path")
    if previous.daemon_host != updated.daemon_host:
        changed.append("daemon_host")
    if previous.daemon_port != updated.daemon_port:
        changed.append("daemon_port")
    if previous.llm.provider != updated.llm.provider:
        changed.append("llm.provider")
    if previous.llm.model != updated.llm.model:
        changed.append("llm.model")
    if previous.llm.base_url != updated.llm.base_url:
        changed.append("llm.base_url")
    if previous.scheduler.daily_summary_time != updated.scheduler.daily_summary_time:
        changed.append("scheduler.daily_summary_time")
    if previous.log_level != updated.log_level:
        changed.append("log_level")
    if previous.transcription.backend != updated.transcription.backend:
        changed.append("transcription.backend")
    if previous.transcription.model != updated.transcription.model:
        changed.append("transcription.model")
    if previous.transcription.device != updated.transcription.device:
        changed.append("transcription.device")
    if previous.transcription.compute_type != updated.transcription.compute_type:
        changed.append("transcription.compute_type")
    if previous.transcription.language != updated.transcription.language:
        changed.append("transcription.language")
    if previous.meetings.default_source != updated.meetings.default_source:
        changed.append("meetings.default_source")
    if previous.meetings.auto_summarize != updated.meetings.auto_summarize:
        changed.append("meetings.auto_summarize")
    if previous.meetings.sample_rate != updated.meetings.sample_rate:
        changed.append("meetings.sample_rate")
    if previous.meetings.channels != updated.meetings.channels:
        changed.append("meetings.channels")
    if previous.meetings.open_command != updated.meetings.open_command:
        changed.append("meetings.open_command")
    if previous.meetings.play_command != updated.meetings.play_command:
        changed.append("meetings.play_command")
    if previous.meetings.auto_normalize != updated.meetings.auto_normalize:
        changed.append("meetings.auto_normalize")
    if previous.meetings.normalize_target_dbfs != updated.meetings.normalize_target_dbfs:
        changed.append("meetings.normalize_target_dbfs")
    if previous.meetings.noise_reduction != updated.meetings.noise_reduction:
        changed.append("meetings.noise_reduction")
    return changed


class TokenAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Any) -> Any:
        if request.url.path == "/health":
            return await call_next(request)
        auth = request.headers.get("Authorization", "")
        expected = f"Bearer {os.environ.get('NINA_TOKEN', '')}"
        if auth != expected:
            return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
        return await call_next(request)


app.add_middleware(TokenAuthMiddleware)


@app.get("/health")
async def health(request: Request) -> dict[str, Any]:
    config = _request_config(request)
    return {
        "status": "ok",
        "profile": config.profile,
        "vault_path": config.vault_path,
    }


@app.get("/config")
async def get_config(request: Request) -> ConfigResponse:
    config_dir = _request_config_dir(request)
    config = _request_config(request)
    return _config_response(config_dir, config)


@app.patch("/config")
async def update_config(request: Request, data: ConfigUpdate) -> dict[str, Any]:
    config_dir = _request_config_dir(request)
    current = _request_config(request)
    patch = data.model_dump(exclude_unset=True, exclude_none=False)
    if not patch:
        return {
            "config": _config_response(config_dir, current).model_dump(),
            "changed_fields": [],
            "restart_required": False,
        }

    updated = merge_config(current, patch, config_dir)
    updated.save(get_config_path(config_dir))
    changed_fields = _changed_config_fields(current, updated)
    apply_runtime_config(request.app, config_dir, updated)

    if current.vault_path != updated.vault_path:
        ensure_vault_structure(Path(updated.vault_path))
    if current.database_path != updated.database_path:
        create_database(updated.database_path)
        create_fts_table(updated.database_path)
        scheduler = getattr(request.app.state, "scheduler", None)
        if scheduler is not None:
            scheduler.shutdown()
        new_scheduler = SchedulerService(updated.database_path)
        request.app.state.scheduler = new_scheduler
        new_scheduler.start()

    restart_required = any(
        field in {"daemon_host", "daemon_port", "log_level"} for field in changed_fields
    )
    return {
        "config": _config_response(config_dir, updated).model_dump(),
        "changed_fields": changed_fields,
        "restart_required": restart_required,
    }


def _active_config_path() -> str:
    """Database path from the active NinaConfig on the app state.

    Falls back to the bootstrap env var only if the config has not been
    loaded yet (e.g. unit tests that bypass `apply_runtime_config`).
    """
    config = getattr(app.state, "config", None)
    if config is not None:
        return str(config.database_path)
    return os.environ.get("NINA_DATABASE_PATH", "")


def _active_vault_path() -> str:
    config = getattr(app.state, "config", None)
    if config is not None:
        return str(config.vault_path)
    return os.environ.get("NINA_VAULT_PATH", "")


def get_db() -> Session:
    db_path = _active_config_path()
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def get_obsidian() -> ObsidianService:
    return ObsidianService(_active_vault_path())


def get_scheduler(request: Request) -> SchedulerService:
    scheduler = getattr(request.app.state, "scheduler", None)
    if scheduler is not None:
        return scheduler
    return SchedulerService(_active_config_path())


def get_session_service(request: Request) -> SessionService:
    config = _request_config(request)
    return SessionService(
        _active_config_path(),
        _active_vault_path(),
        llm_config=config.llm,
        search_config=config.search,
    )


class ProjectResponse(BaseModel):
    id: str
    name: str
    description: str
    status: str
    note_path: str | None
    created_at: str
    updated_at: str


class ProjectCreate(BaseModel):
    name: str
    description: str = ""


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    status: str | None = None


class TaskResponse(BaseModel):
    id: str
    project_id: str | None
    title: str
    description: str
    status: str
    kanban_column: str
    kanban_position: int
    note_path: str | None
    created_at: str
    updated_at: str


class TaskCreate(BaseModel):
    title: str
    description: str = ""
    project_id: str | None = None


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None
    kanban_column: str | None = None
    kanban_position: int | None = None


class KanbanMove(BaseModel):
    task_id: str
    to_column: str
    to_position: int


class SearchQuery(BaseModel):
    query: str
    limit: int = 20


class AskQuery(BaseModel):
    question: str
    limit: int = 5


class SessionCreate(BaseModel):
    mode: Literal["chat", "agent"]
    title: str | None = None


class SessionMessageCreate(BaseModel):
    content: str


class ResearchRunInput(BaseModel):
    topic: str


class SearchReindex(BaseModel):
    pass


class SearchOpen(BaseModel):
    path: str


class WorkflowInput(BaseModel):
    input: dict[str, Any] = {}


class JobCreate(BaseModel):
    name: str
    workflow_name: str = "summarize-last-day"
    schedule: str
    enabled: bool = True


class JobUpdate(BaseModel):
    enabled: bool


class MeetingCreate(BaseModel):
    title: str
    source: str = "mic"
    device_name: str | None = None
    sample_rate: int = 16000
    channels: int = 1
    audio_format: str = "wav"


class MeetingRecord(BaseModel):
    title: str
    source: str | None = None
    device: str | None = None
    mic_device: str | None = None
    system_device: str | None = None
    sample_rate: int | None = None
    channels: int | None = None
    duration_seconds: int | None = None
    gain: float | None = None
    auto_normalize: bool | None = None
    normalize_target_dbfs: float | None = None
    noise_reduction: str | None = None


class MeetingStop(BaseModel):
    duration_seconds: int | None = None
    size_bytes: int | None = None
    error: str | None = None


@app.get("/projects")
async def list_projects(request: Request) -> list[ProjectResponse]:
    db = get_db()
    obsidian = get_obsidian()
    service = ProjectService(db, obsidian)
    projects = service.list()
    return [
        ProjectResponse(
            id=p.id,
            name=p.name,
            description=p.description,
            status=p.status,
            note_path=p.note_path,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p in projects
    ]


@app.post("/projects")
async def create_project(request: Request, data: ProjectCreate) -> ProjectResponse:
    db = get_db()
    obsidian = get_obsidian()
    service = ProjectService(db, obsidian)
    project = service.create(data.name, data.description)
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        status=project.status,
        note_path=project.note_path,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@app.get("/projects/{project_id}")
async def get_project(request: Request, project_id: str) -> ProjectResponse:
    db = get_db()
    obsidian = get_obsidian()
    service = ProjectService(db, obsidian)
    project = service.get(project_id)
    if not project:
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        status=project.status,
        note_path=project.note_path,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@app.patch("/projects/{project_id}")
async def update_project(request: Request, project_id: str, data: ProjectUpdate) -> ProjectResponse:
    db = get_db()
    obsidian = get_obsidian()
    service = ProjectService(db, obsidian)
    project = service.update(project_id, data.name, data.description, data.status)
    if not project:
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        status=project.status,
        note_path=project.note_path,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@app.delete("/projects/{project_id}")
async def delete_project(request: Request, project_id: str) -> dict[str, bool]:
    db = get_db()
    obsidian = get_obsidian()
    service = ProjectService(db, obsidian)
    if not service.delete(project_id):
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    return {"deleted": True}


@app.get("/tasks")
async def list_tasks(request: Request) -> list[TaskResponse]:
    db = get_db()
    obsidian = get_obsidian()
    service = TaskService(db, obsidian)
    tasks = service.list()
    return [
        TaskResponse(
            id=t.id,
            project_id=t.project_id,
            title=t.title,
            description=t.description,
            status=t.status,
            kanban_column=t.kanban_column,
            kanban_position=t.kanban_position,
            note_path=t.note_path,
            created_at=t.created_at,
            updated_at=t.updated_at,
        )
        for t in tasks
    ]


@app.post("/tasks")
async def create_task(request: Request, data: TaskCreate) -> TaskResponse:
    db = get_db()
    obsidian = get_obsidian()
    service = TaskService(db, obsidian)
    task = service.create(data.title, data.description, data.project_id)
    return TaskResponse(
        id=task.id,
        project_id=task.project_id,
        title=task.title,
        description=task.description,
        status=task.status,
        kanban_column=task.kanban_column,
        kanban_position=task.kanban_position,
        note_path=task.note_path,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


@app.get("/tickets")
async def list_tickets(request: Request) -> list[TaskResponse]:
    return await list_tasks(request)


@app.post("/tickets")
async def create_ticket(request: Request, data: TaskCreate) -> TaskResponse:
    return await create_task(request, data)


@app.get("/tickets/{ticket_id}")
async def get_ticket(request: Request, ticket_id: str) -> TaskResponse:
    return await get_task(request, ticket_id)


@app.patch("/tickets/{ticket_id}")
async def update_ticket(request: Request, ticket_id: str, data: TaskUpdate) -> TaskResponse:
    return await update_task(request, ticket_id, data)


@app.delete("/tickets/{ticket_id}")
async def delete_ticket(request: Request, ticket_id: str) -> dict[str, bool]:
    return await delete_task(request, ticket_id)


@app.get("/tasks/{task_id}")
async def get_task(request: Request, task_id: str) -> TaskResponse:
    db = get_db()
    obsidian = get_obsidian()
    service = TaskService(db, obsidian)
    task = service.get(task_id)
    if not task:
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    return TaskResponse(
        id=task.id,
        project_id=task.project_id,
        title=task.title,
        description=task.description,
        status=task.status,
        kanban_column=task.kanban_column,
        kanban_position=task.kanban_position,
        note_path=task.note_path,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


@app.patch("/tasks/{task_id}")
async def update_task(request: Request, task_id: str, data: TaskUpdate) -> TaskResponse:
    db = get_db()
    obsidian = get_obsidian()
    service = TaskService(db, obsidian)
    task = service.update(
        task_id,
        data.title,
        data.description,
        data.status,
        data.kanban_column,
        data.kanban_position,
    )
    if not task:
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    return TaskResponse(
        id=task.id,
        project_id=task.project_id,
        title=task.title,
        description=task.description,
        status=task.status,
        kanban_column=task.kanban_column,
        kanban_position=task.kanban_position,
        note_path=task.note_path,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


@app.delete("/tasks/{task_id}")
async def delete_task(request: Request, task_id: str) -> dict[str, bool]:
    db = get_db()
    obsidian = get_obsidian()
    service = TaskService(db, obsidian)
    if not service.delete(task_id):
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    return {"deleted": True}


@app.post("/tasks/{task_id}/archive")
async def archive_task(request: Request, task_id: str) -> TaskResponse:
    db = get_db()
    obsidian = get_obsidian()
    service = TaskService(db, obsidian)
    task = service.archive(task_id)
    if not task:
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    return TaskResponse(
        id=task.id,
        project_id=task.project_id,
        title=task.title,
        description=task.description,
        status=task.status,
        kanban_column=task.kanban_column,
        kanban_position=task.kanban_position,
        note_path=task.note_path,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


@app.post("/tasks/{task_id}/unarchive")
async def unarchive_task(request: Request, task_id: str) -> TaskResponse:
    db = get_db()
    obsidian = get_obsidian()
    service = TaskService(db, obsidian)
    task = service.unarchive(task_id)
    if not task:
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    return TaskResponse(
        id=task.id,
        project_id=task.project_id,
        title=task.title,
        description=task.description,
        status=task.status,
        kanban_column=task.kanban_column,
        kanban_position=task.kanban_position,
        note_path=task.note_path,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


@app.get("/kanban")
async def get_kanban(request: Request) -> dict[str, Any]:
    db = get_db()
    board = get_kanban_board(db)
    result: dict[str, Any] = {}
    for column, tasks in board.items():
        result[column] = [
            {
                "id": t.id,
                "title": t.title,
                "status": t.status,
                "kanban_position": t.kanban_position,
            }
            for t in tasks
        ]
    return result


@app.post("/kanban/move")
async def kanban_move(request: Request, data: KanbanMove) -> TaskResponse:
    db = get_db()
    task = move_task(db, data.task_id, data.to_column, data.to_position)
    if not task:
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    get_obsidian().update_task_note(task)
    return TaskResponse(
        id=task.id,
        project_id=task.project_id,
        title=task.title,
        description=task.description,
        status=task.status,
        kanban_column=task.kanban_column,
        kanban_position=task.kanban_position,
        note_path=task.note_path,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


@app.post("/search")
async def search_endpoint(request: Request, data: SearchQuery) -> list[dict[str, Any]]:
    db_path = _active_config_path()
    return search(db_path, data.query, data.limit)


@app.post("/search/reindex")
async def reindex_endpoint(request: Request) -> dict[str, Any]:
    db_path = _active_config_path()
    vault_path = _active_vault_path()
    index_notes(db_path, vault_path)
    return {"reindexed": True}


@app.post("/search/open")
async def open_endpoint(request: Request, data: SearchOpen) -> dict[str, Any]:
    import subprocess

    vault_path = _active_vault_path()
    full_path = os.path.join(vault_path, data.path)
    subprocess.run(["xdg-open", f"obsidian://open?path={full_path}"], capture_output=True)
    return {"opened": True}


@app.post("/ask")
async def ask_endpoint(request: Request, data: AskQuery) -> dict[str, Any]:
    db_path = _active_config_path()
    vault_path = _active_vault_path()
    return await ask_obsidian(db_path, vault_path, data.question, data.limit)


@app.post("/llm/complete")
async def llm_complete(request: Request, data: LLMRequest) -> dict[str, Any]:
    db_path = _active_config_path()
    service = LLMService(db_path)
    response = await service.complete(data)
    return {"response": response.response, "model": response.model, "provider": response.provider}


@app.get("/llm/interactions")
async def llm_interactions(request: Request) -> list[dict[str, Any]]:
    db_path = _active_config_path()
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from nina_core.models.models import LLMInteraction

    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    interactions = db.query(LLMInteraction).order_by(LLMInteraction.created_at.desc()).all()
    return [
        {
            "id": i.id,
            "provider": i.provider,
            "model": i.model,
            "purpose": i.purpose,
            "status": i.status,
            "created_at": i.created_at,
        }
        for i in interactions
    ]


@app.get("/sessions")
async def list_sessions(request: Request, mode: str | None = None) -> list[dict[str, Any]]:
    return get_session_service(request).list_sessions(mode)


@app.post("/sessions")
async def create_session(request: Request, data: SessionCreate) -> dict[str, Any]:
    return get_session_service(request).create_session(data.mode, data.title)


@app.get("/sessions/{session_id}")
async def get_session(request: Request, session_id: str) -> dict[str, Any]:
    session = get_session_service(request).get_session(session_id)
    if not session:
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    return session


@app.post("/sessions/{session_id}/messages")
async def send_session_message(
    request: Request, session_id: str, data: SessionMessageCreate
) -> dict[str, Any]:
    service = get_session_service(request)
    try:
        return await service.send_message(session_id, data.content)
    except RuntimeError as exc:
        message = str(exc)
        status = 404 if message.startswith("Unknown session") else 400
        return JSONResponse(status_code=status, content={"detail": message})


@app.post("/sessions/{session_id}/cancel")
async def cancel_session(request: Request, session_id: str) -> dict[str, Any]:
    service = get_session_service(request)
    ok = service.request_cancel(session_id)
    if not ok:
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    return {"cancelled": True}


@app.post("/sessions/{session_id}/clear-cancel")
async def clear_session_cancel(request: Request, session_id: str) -> dict[str, Any]:
    service = get_session_service(request)
    service.clear_cancel(session_id)
    return {"cleared": True}


class NotesQuery(BaseModel):
    folder: str | None = None
    nina_type: str | None = None
    limit: int = 20


class NoteCreate(BaseModel):
    path: str
    body: str
    nina_type: str | None = None
    frontmatter_patch: dict[str, Any] | None = None


class NoteUpdate(BaseModel):
    body: str | None = None
    append: str | None = None
    frontmatter_patch: dict[str, Any] | None = None


def get_note_service(request: Request):
    from nina_core.notes.service import NoteService

    return NoteService(
        _active_config_path(),
        _active_vault_path(),
    )


@app.get("/notes")
async def list_notes_endpoint(
    request: Request,
    folder: str | None = None,
    nina_type: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    return {
        "notes": get_note_service(request).list_notes(
            folder=folder, nina_type=nina_type, limit=limit
        )
    }


@app.get("/notes/{path:path}")
async def get_note_endpoint(request: Request, path: str) -> dict[str, Any]:
    from nina_core.notes.service import NotePathError

    try:
        note = get_note_service(request).get_note(path)
    except NotePathError as exc:
        return JSONResponse(status_code=400, content={"detail": str(exc)})
    if note is None:
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    return note


@app.post("/notes")
async def create_note_endpoint(request: Request, data: NoteCreate) -> dict[str, Any]:
    from nina_core.notes.service import NotePathError

    try:
        return get_note_service(request).create_note(
            data.path, data.body, nina_type=data.nina_type, frontmatter_patch=data.frontmatter_patch
        )
    except NotePathError as exc:
        return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.patch("/notes/{path:path}")
async def update_note_endpoint(request: Request, path: str, data: NoteUpdate) -> dict[str, Any]:
    from nina_core.notes.service import NotePathError

    service = get_note_service(request)
    try:
        if data.append is not None:
            return service.append_note(path, data.append)
        if data.body is not None:
            return service.update_note(path, data.body, frontmatter_patch=data.frontmatter_patch)
        if data.frontmatter_patch is not None:
            return service.update_note(
                path,
                service.get_note(path)["body"] if service.get_note(path) else "",
                frontmatter_patch=data.frontmatter_patch,
            )
    except NotePathError as exc:
        return JSONResponse(status_code=400, content={"detail": str(exc)})
    return JSONResponse(
        status_code=400, content={"detail": "Provide body, append, or frontmatter_patch"}
    )


@app.post("/research/run")
async def run_research(request: Request, data: ResearchRunInput) -> dict[str, Any]:
    db_path = _active_config_path()
    runner = WorkflowRunner(db_path, config=_request_config(request))
    result = runner.run("research-topic", {"topic": data.topic})
    if result.get("status") != "completed":
        return JSONResponse(status_code=400, content=result)
    output = dict(result.get("output", {}))
    output["workflow_run_id"] = result.get("id")
    output["status"] = result.get("status")
    output["created_at"] = result.get("created_at")
    return output


@app.get("/workflows")
async def list_workflows(request: Request) -> list[str]:
    return [
        "summarize-last-day",
        "research-topic",
        "reindex-vault",
        "transcribe-meeting",
        "summarize-meeting",
        "meeting-pipeline",
    ]


@app.post("/workflows/{workflow_name}/run")
async def run_workflow(request: Request, workflow_name: str, data: WorkflowInput) -> dict[str, Any]:
    db_path = _active_config_path()
    runner = WorkflowRunner(db_path, config=_request_config(request))
    return runner.run(workflow_name, data.input)


@app.get("/workflow-runs")
async def list_workflow_runs(request: Request) -> list[dict[str, Any]]:
    db_path = _active_config_path()
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from nina_core.models.models import WorkflowRun

    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    runs = db.query(WorkflowRun).order_by(WorkflowRun.created_at.desc()).all()
    return [
        {
            "id": r.id,
            "workflow_name": r.workflow_name,
            "status": r.status,
            "created_at": r.created_at,
        }
        for r in runs
    ]


@app.get("/workflow-runs/{run_id}")
async def get_workflow_run(request: Request, run_id: str) -> dict[str, Any]:
    db_path = _active_config_path()
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from nina_core.models.models import WorkflowRun

    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    run = db.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()
    if not run:
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    return {
        "id": run.id,
        "workflow_name": run.workflow_name,
        "status": run.status,
        "input": run.input_json,
        "created_at": run.created_at,
    }


@app.get("/jobs")
async def list_jobs(request: Request) -> list[dict[str, Any]]:
    return get_scheduler(request).list_jobs()


@app.post("/jobs")
async def create_job(request: Request, data: JobCreate) -> dict[str, Any]:
    try:
        return get_scheduler(request).create_job(
            data.name,
            data.workflow_name,
            data.schedule,
            data.enabled,
        )
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.patch("/jobs/{job_name}")
async def update_job(request: Request, job_name: str, data: JobUpdate) -> dict[str, Any]:
    service = get_scheduler(request)
    job = service.enable_job(job_name) if data.enabled else service.disable_job(job_name)
    if not job:
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    return job


@app.post("/jobs/{job_name}/run")
async def run_job(request: Request, job_name: str) -> dict[str, Any]:
    run = get_scheduler(request).run_job_now(job_name)
    if not run:
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    return run


@app.get("/job-runs")
async def list_job_runs(
    request: Request, job_name: str | None = None, limit: int = 20
) -> list[dict[str, Any]]:
    return get_scheduler(request).list_job_runs(job_name, limit)


def get_meeting_service(request: Request):
    from nina_core.meetings.service import MeetingService

    config = _request_config(request)
    return MeetingService(
        config.database_path,
        get_config_dir_resolved(request) / "recordings",
        str(config.vault_path),
    )


def get_meeting_recorder(request: Request):
    from nina_core.meetings.manager import MeetingRecordingManager

    recorder = getattr(request.app.state, "meeting_recorder", None)
    if recorder is None:
        recorder = MeetingRecordingManager()
        request.app.state.meeting_recorder = recorder
    return recorder


def get_config_dir_resolved(request: Request) -> Path:
    config_dir = getattr(request.app.state, "config_dir", None)
    if config_dir is not None:
        return Path(config_dir)
    profile = os.environ.get("NINA_PROFILE", "default")
    return get_config_dir(str(profile))


@app.post("/meetings")
async def create_meeting(request: Request, data: MeetingCreate) -> dict[str, Any]:
    service = get_meeting_service(request)
    return service.start(
        title=data.title,
        source=data.source,
        device_name=data.device_name,
        sample_rate=data.sample_rate,
        channels=data.channels,
        audio_format=data.audio_format,
    )


@app.post("/meetings/record")
async def record_meeting(request: Request, data: MeetingRecord) -> dict[str, Any]:
    from nina_core.meetings.manager import RecordingRequest
    from nina_core.meetings.recorder import RecorderError

    config = _request_config(request)
    recorder = get_meeting_recorder(request)
    config_dir = get_config_dir_resolved(request)
    try:
        return recorder.start(
            config=config,
            config_dir=config_dir,
            request=RecordingRequest(
                title=data.title,
                source=data.source,
                device=data.device,
                mic_device=data.mic_device,
                system_device=data.system_device,
                sample_rate=data.sample_rate,
                channels=data.channels,
                duration_seconds=data.duration_seconds,
                gain=data.gain,
                auto_normalize=data.auto_normalize,
                normalize_target_dbfs=data.normalize_target_dbfs,
                noise_reduction=data.noise_reduction,
            ),
        )
    except RecorderError as exc:
        status_code = 409 if "already active" in str(exc).lower() else 400
        return JSONResponse(status_code=status_code, content={"detail": str(exc)})


@app.get("/meetings")
async def list_meetings(
    request: Request,
    status: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    service = get_meeting_service(request)
    return {"meetings": service.list(status=status, limit=limit)}


@app.get("/meetings/{meeting_id}")
async def get_meeting(request: Request, meeting_id: str) -> dict[str, Any]:
    service = get_meeting_service(request)
    meeting = service.get(meeting_id)
    if meeting is None:
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    return meeting


@app.post("/meetings/{meeting_id}/stop")
async def stop_meeting(
    request: Request, meeting_id: str, data: MeetingStop | None = None
) -> dict[str, Any]:
    from nina_core.meetings.recorder import RecorderError

    service = get_meeting_service(request)
    recorder = get_meeting_recorder(request)
    payload = data or MeetingStop()
    try:
        meeting = recorder.stop(meeting_id)
    except RecorderError as exc:
        return JSONResponse(status_code=400, content={"detail": str(exc)})
    if meeting is not None:
        if payload.error is not None:
            service.update_status(meeting_id, error=payload.error)
            meeting = service.get(meeting_id) or meeting
        return meeting
    meeting = service.stop(
        meeting_id,
        duration_seconds=payload.duration_seconds,
        size_bytes=payload.size_bytes,
        error=payload.error,
    )
    if meeting is None:
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    return meeting


@app.post("/meetings/{meeting_id}/pipeline")
async def pipeline_meeting(request: Request, meeting_id: str) -> dict[str, Any]:
    """Run transcribe + summarize back-to-back for an existing meeting.

    This is the endpoint the TUI's `Ctrl+E` hotkey hits. The two stages run
    sequentially inside one workflow run so progress events stream out in
    order over `/events/stream`.
    """
    import asyncio
    import concurrent.futures

    from nina_core.workflows.runner import WorkflowRunner

    db_path = _active_config_path()

    def _run() -> dict[str, Any]:
        runner = WorkflowRunner(db_path, config=_request_config(request))
        return runner.run("meeting-pipeline", {"meeting_id": meeting_id, "input": {}})

    loop = asyncio.get_running_loop()
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        result = await loop.run_in_executor(executor, _run)
    if result.get("status") != "completed":
        return JSONResponse(status_code=400, content=result)
    return result


@app.get("/meetings/{meeting_id}/transcript")
async def get_meeting_transcript(request: Request, meeting_id: str) -> dict[str, Any]:
    service = get_meeting_service(request)
    meeting = service.get(meeting_id)
    if meeting is None:
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    transcript_path = meeting.get("transcript_path")
    if not transcript_path:
        return {"transcript": "", "status": meeting.get("status")}
    full = Path(transcript_path)
    if not full.is_file():
        return {"transcript": "", "status": meeting.get("status")}
    return {"transcript": full.read_text(), "status": meeting.get("status")}


@app.delete("/meetings/{meeting_id}")
async def delete_meeting(request: Request, meeting_id: str) -> dict[str, Any]:
    service = get_meeting_service(request)
    ok = service.delete(meeting_id)
    if not ok:
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    return {"deleted": True}


@app.get("/meetings/devices")
@app.get("/meetings-devices")
async def list_meeting_devices() -> dict[str, Any]:
    from nina_core.meetings.recorder import (
        list_input_devices,
        list_pulse_sources,
        list_soundcard_devices,
    )

    soundcard = list_soundcard_devices()
    return {
        "inputs": list_input_devices(),
        "pulse_sources": list_pulse_sources(),
        "soundcard_microphones": soundcard.get("microphones", []),
        "soundcard_speakers": soundcard.get("speakers", []),
    }
