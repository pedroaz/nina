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
from nina_core.integrations.registry import get_integration
from nina_core.integrations.credentials import (
    delete_credentials,
    load_credentials,
    save_credentials,
)
from nina_core.integrations.service import IntegrationService
from nina_core.llm.provider import LLMRequest, LLMService
from nina_core.obsidian.service import ObsidianService
from nina_core.opencode import (
    OpencodeError,
    Project,
)
from nina_core.scheduler.service import SchedulerService
from nina_core.search.indexer import ask_obsidian, index_notes, search, create_fts_table
from nina_core.sessions.service import SessionService
from nina_core.tasks.service import TaskService
import nina_core
from nina_core.workflows.runner import WORKFLOW_DESCRIPTIONS, WorkflowRunner

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


class OpencodeConfigResponse(BaseModel):
    enabled: bool
    binary_path: str
    host: str
    port: int
    username: str
    password_ref: str
    startup_timeout_seconds: float
    shutdown_timeout_seconds: float


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
    opencode: OpencodeConfigResponse
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


class OpencodeConfigUpdate(BaseModel):
    enabled: bool | None = None
    binary_path: str | None = None
    host: str | None = None
    port: int | None = None
    username: str | None = None
    password_ref: str | None = None
    startup_timeout_seconds: float | None = None
    shutdown_timeout_seconds: float | None = None


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
    opencode: OpencodeConfigUpdate | None = None


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
        opencode=OpencodeConfigResponse(
            enabled=config.opencode.enabled,
            binary_path=config.opencode.binary_path,
            host=config.opencode.host,
            port=config.opencode.port,
            username=config.opencode.username,
            password_ref=config.opencode.password_ref,
            startup_timeout_seconds=config.opencode.startup_timeout_seconds,
            shutdown_timeout_seconds=config.opencode.shutdown_timeout_seconds,
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
    if previous.opencode.enabled != updated.opencode.enabled:
        changed.append("opencode.enabled")
    if previous.opencode.binary_path != updated.opencode.binary_path:
        changed.append("opencode.binary_path")
    if previous.opencode.host != updated.opencode.host:
        changed.append("opencode.host")
    if previous.opencode.port != updated.opencode.port:
        changed.append("opencode.port")
    if previous.opencode.username != updated.opencode.username:
        changed.append("opencode.username")
    if previous.opencode.password_ref != updated.opencode.password_ref:
        changed.append("opencode.password_ref")
    if previous.opencode.startup_timeout_seconds != updated.opencode.startup_timeout_seconds:
        changed.append("opencode.startup_timeout_seconds")
    if previous.opencode.shutdown_timeout_seconds != updated.opencode.shutdown_timeout_seconds:
        changed.append("opencode.shutdown_timeout_seconds")
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
        field
        in {
            "daemon_host",
            "daemon_port",
            "log_level",
            "opencode.enabled",
            "opencode.binary_path",
            "opencode.host",
            "opencode.port",
            "opencode.username",
            "opencode.password_ref",
            "opencode.startup_timeout_seconds",
            "opencode.shutdown_timeout_seconds",
        }
        for field in changed_fields
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


class TaskResponse(BaseModel):
    id: str
    opencode_project_id: str | None
    title: str
    description: str
    task_type: str
    status: str
    classified_at: str | None
    classification_reason: str | None
    classification_model: str | None
    note_path: str | None
    created_at: str
    updated_at: str


class TaskCreate(BaseModel):
    title: str
    description: str = ""
    opencode_project_id: str | None = None
    task_type: str | None = None
    auto_classify: bool = True


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    task_type: str | None = None
    status: str | None = None
    opencode_project_id: str | None = None


def _task_to_response(t: Any) -> TaskResponse:
    return TaskResponse(
        id=t.id,
        opencode_project_id=t.opencode_project_id,
        title=t.title,
        description=t.description,
        task_type=t.task_type,
        status=t.status,
        classified_at=t.classified_at,
        classification_reason=t.classification_reason,
        classification_model=t.classification_model,
        note_path=t.note_path,
        created_at=t.created_at,
        updated_at=t.updated_at,
    )


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


class IntegrationCredentialsUpdate(BaseModel):
    credentials: dict[str, Any]


@app.get("/tasks")
async def list_tasks(
    request: Request,
    task_type: str | None = None,
    status: str | None = None,
    include_archived: bool = False,
) -> list[TaskResponse]:
    db = get_db()
    obsidian = get_obsidian()
    service = TaskService(db, obsidian)
    tasks = service.list(task_type=task_type, status=status, include_archived=include_archived)
    return [_task_to_response(t) for t in tasks]


@app.post("/tasks")
async def create_task(request: Request, data: TaskCreate) -> TaskResponse:
    db = get_db()
    obsidian = get_obsidian()
    service = TaskService(db, obsidian)
    task = service.create(
        data.title,
        data.description,
        data.opencode_project_id,
        task_type=data.task_type or "unclassified",
        auto_classify=data.auto_classify,
    )
    return _task_to_response(task)


@app.get("/tasks/grouped-by-type")
async def tasks_grouped_by_type(request: Request) -> dict[str, list[TaskResponse]]:
    """Return active tasks grouped by `task_type`, sorted by `classified_at` desc.

    Replaces the legacy `/kanban` endpoint. The shape is `{type: [task, ...]}`.
    """

    db = get_db()
    obsidian = get_obsidian()
    service = TaskService(db, obsidian)
    tasks = service.list()
    grouped: dict[str, list[TaskResponse]] = {}
    for task in tasks:
        grouped.setdefault(task.task_type, []).append(_task_to_response(task))
    return grouped


@app.get("/tickets")
async def list_tickets(
    request: Request,
    task_type: str | None = None,
    status: str | None = None,
    include_archived: bool = False,
) -> list[TaskResponse]:
    return await list_tasks(
        request, task_type=task_type, status=status, include_archived=include_archived
    )


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


@app.post("/tickets/{ticket_id}/classify")
async def classify_ticket(request: Request, ticket_id: str) -> dict[str, Any]:
    return await classify_task(request, ticket_id)


@app.post("/tickets/{ticket_id}/run")
async def run_ticket(request: Request, ticket_id: str) -> dict[str, Any]:
    return await run_task(request, ticket_id)


@app.get("/tasks/{task_id}")
async def get_task(request: Request, task_id: str) -> TaskResponse:
    db = get_db()
    obsidian = get_obsidian()
    service = TaskService(db, obsidian)
    task = service.get(task_id)
    if not task:
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    return _task_to_response(task)


@app.patch("/tasks/{task_id}")
async def update_task(request: Request, task_id: str, data: TaskUpdate) -> TaskResponse:
    db = get_db()
    obsidian = get_obsidian()
    service = TaskService(db, obsidian)
    try:
        task = service.update(
            task_id,
            title=data.title,
            description=data.description,
            task_type=data.task_type,
            status=data.status,
            opencode_project_id=(
                data.opencode_project_id if "opencode_project_id" in data.model_fields_set else None
            ),
        )
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"detail": str(exc)})
    if not task:
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    return _task_to_response(task)


@app.delete("/tasks/{task_id}")
async def delete_task(request: Request, task_id: str) -> dict[str, bool]:
    db = get_db()
    obsidian = get_obsidian()
    service = TaskService(db, obsidian)
    if not service.delete(task_id):
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    return {"deleted": True}


@app.post("/tasks/{task_id}/classify")
async def classify_task(request: Request, task_id: str) -> dict[str, Any]:
    db_path = _active_config_path()
    config = _request_config(request)
    runner = WorkflowRunner(db_path, config=config)
    result = runner.run("classify-task", {"task_id": task_id})
    if result.get("status") != "completed":
        return JSONResponse(status_code=400, content=result)
    return result


@app.post("/tasks/{task_id}/run")
async def run_task(request: Request, task_id: str) -> dict[str, Any]:
    db_path = _active_config_path()
    config = _request_config(request)
    runner = WorkflowRunner(db_path, config=config)
    result = runner.run("run-task", {"task_id": task_id})
    if result.get("status") != "completed":
        return JSONResponse(status_code=400, content=result)
    return result


@app.post("/tasks/{task_id}/archive")
async def archive_task(request: Request, task_id: str) -> TaskResponse:
    db = get_db()
    obsidian = get_obsidian()
    service = TaskService(db, obsidian)
    task = service.archive(task_id)
    if not task:
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    return _task_to_response(task)


@app.post("/tasks/{task_id}/unarchive")
async def unarchive_task(request: Request, task_id: str) -> TaskResponse:
    db = get_db()
    obsidian = get_obsidian()
    service = TaskService(db, obsidian)
    task = service.unarchive(task_id)
    if not task:
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    return _task_to_response(task)


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
async def list_workflows(request: Request) -> list[dict[str, str]]:
    """Return the known workflow names with a short description of each.

    Clients (CLI, TUI) use this to render "what does this job do?"
    context next to a scheduled job's cron entry.
    """
    return [
        {"name": name, "description": WORKFLOW_DESCRIPTIONS.get(name, "")}
        for name in [
            "summarize-last-day",
            "research-topic",
            "reindex-vault",
            "transcribe-meeting",
            "summarize-meeting",
            "meeting-pipeline",
            "classify-task",
            "run-task",
        ]
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


def get_integration_service(request: Request) -> IntegrationService:
    config = _request_config(request)
    return IntegrationService(config.database_path, config_dir=_request_config_dir(request))


@app.get("/integrations")
async def list_integrations_endpoint(request: Request) -> dict[str, Any]:
    return {"integrations": get_integration_service(request).list()}


@app.get("/integrations/{name}")
async def get_integration_endpoint(request: Request, name: str) -> Any:
    integration = get_integration_service(request).get(name)
    if integration is None:
        return JSONResponse(status_code=404, content={"detail": "Unknown integration"})
    return integration


@app.post("/integrations/{name}/test")
async def test_integration_endpoint(request: Request, name: str) -> Any:
    if get_integration(name) is None:
        return JSONResponse(status_code=404, content={"detail": "Unknown integration"})
    try:
        result = await get_integration_service(request).test(name)
    except KeyError:
        return JSONResponse(status_code=404, content={"detail": "Unknown integration"})
    return result


@app.get("/integrations/{name}/tests")
async def list_integration_tests_endpoint(request: Request, name: str, limit: int = 10) -> Any:
    if get_integration(name) is None:
        return JSONResponse(status_code=404, content={"detail": "Unknown integration"})
    return {"tests": get_integration_service(request).list_tests(name, limit=limit)}


@app.put("/integrations/{name}/credentials")
async def put_integration_credentials(
    request: Request, name: str, data: IntegrationCredentialsUpdate
) -> dict[str, Any]:
    if get_integration(name) is None:
        return JSONResponse(status_code=404, content={"detail": "Unknown integration"})
    if not isinstance(data.credentials, dict) or not data.credentials:
        return JSONResponse(
            status_code=400, content={"detail": "credentials must be a non-empty object"}
        )
    path = save_credentials(name, data.credentials, config_dir=_request_config_dir(request))
    return {"saved": True, "path": str(path)}


@app.delete("/integrations/{name}/credentials")
async def delete_integration_credentials(request: Request, name: str) -> dict[str, Any]:
    if get_integration(name) is None:
        return JSONResponse(status_code=404, content={"detail": "Unknown integration"})
    deleted = delete_credentials(name, config_dir=_request_config_dir(request))
    return {"deleted": deleted}


@app.get("/integrations/{name}/credentials")
async def get_integration_credentials(request: Request, name: str) -> dict[str, Any]:
    """Return the *shape* of stored credentials without exposing secrets.

    Used by the TUI/CLI to show which fields are configured (`true`/`false`).
    The actual values are never returned over the API.
    """

    if get_integration(name) is None:
        return JSONResponse(status_code=404, content={"detail": "Unknown integration"})
    creds = load_credentials(name, config_dir=_request_config_dir(request)) or {}
    return {
        "configured_fields": {key: bool(value) for key, value in creds.items()},
    }


# --- opencode integration -----------------------------------------------


def _opencode_supervisor(request: Request):
    """Return the live supervisor, or 503 if the daemon didn't start one."""

    supervisor = getattr(request.app.state, "opencode", None)
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


@app.get("/opencode/status")
async def opencode_status(request: Request) -> dict[str, Any]:
    supervisor = _opencode_supervisor(request)
    if supervisor is None:
        return JSONResponse(
            status_code=503,
            content={"detail": "opencode supervisor not initialized"},
        )
    return supervisor.status().model_dump()


@app.get("/opencode/health")
async def opencode_health(request: Request) -> dict[str, Any]:
    """Proxy the opencode server's `/global/health`. Returns 502 if
    opencode is not reachable."""

    supervisor = _opencode_supervisor(request)
    if supervisor is None:
        return JSONResponse(
            status_code=503,
            content={"detail": "opencode supervisor not initialized"},
        )
    status = supervisor.status()
    if status.state != "running":
        return JSONResponse(
            status_code=503,
            content={"detail": f"opencode is {status.state}", "status": status.model_dump()},
        )
    client = supervisor.client()
    try:
        health = await client.health()
    except OpencodeError as exc:
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


@app.get("/opencode/projects")
async def opencode_projects(request: Request) -> list[dict[str, Any]]:
    supervisor = _opencode_supervisor(request)
    if supervisor is None:
        return JSONResponse(
            status_code=503,
            content={"detail": "opencode supervisor not initialized"},
        )
    client = supervisor.client()
    try:
        projects = await client.list_projects()
    except OpencodeError as exc:
        return JSONResponse(status_code=502, content={"detail": str(exc)})
    finally:
        try:
            await client.aclose()
        except Exception:  # noqa: BLE001
            pass
    return [_serialize_project(p) for p in projects]


@app.get("/opencode/projects/current")
async def opencode_current_project(request: Request) -> dict[str, Any]:
    supervisor = _opencode_supervisor(request)
    if supervisor is None:
        return JSONResponse(
            status_code=503,
            content={"detail": "opencode supervisor not initialized"},
        )
    client = supervisor.client()
    try:
        project = await client.current_project()
    except OpencodeError as exc:
        return JSONResponse(status_code=502, content={"detail": str(exc)})
    finally:
        try:
            await client.aclose()
        except Exception:  # noqa: BLE001
            pass
    return _serialize_project(project)
