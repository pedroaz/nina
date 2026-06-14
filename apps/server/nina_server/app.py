import os
from typing import Any, Literal

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from starlette.middleware.base import BaseHTTPMiddleware

from nina_core.obsidian.service import ObsidianService
from nina_core.projects.kanban import get_kanban_board, move_task
from nina_core.projects.service import ProjectService, TaskService
from nina_core.search.indexer import ask_obsidian, index_notes, search
from nina_core.sessions.service import SessionService
from nina_core.llm.provider import LLMRequest, LLMService
from nina_core.scheduler.service import SchedulerService
from nina_core.workflows.runner import WorkflowRunner

app = FastAPI(title="Nina Daemon", version="0.1.0")


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
    return {
        "status": "ok",
        "profile": "default",
        "vault_path": os.environ.get("NINA_VAULT_PATH", ""),
    }


def get_db() -> Session:
    db_path = os.environ.get("NINA_DATABASE_PATH", "")
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def get_obsidian() -> ObsidianService:
    return ObsidianService(os.environ.get("NINA_VAULT_PATH", ""))


def get_scheduler(request: Request) -> SchedulerService:
    scheduler = getattr(request.app.state, "scheduler", None)
    if scheduler is not None:
        return scheduler
    return SchedulerService(os.environ.get("NINA_DATABASE_PATH", ""))


def get_session_service(request: Request) -> SessionService:
    return SessionService(
        os.environ.get("NINA_DATABASE_PATH", ""),
        os.environ.get("NINA_VAULT_PATH", ""),
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
    db_path = os.environ.get("NINA_DATABASE_PATH", "")
    return search(db_path, data.query, data.limit)


@app.post("/search/reindex")
async def reindex_endpoint(request: Request) -> dict[str, Any]:
    db_path = os.environ.get("NINA_DATABASE_PATH", "")
    vault_path = os.environ.get("NINA_VAULT_PATH", "")
    index_notes(db_path, vault_path)
    return {"reindexed": True}


@app.post("/search/open")
async def open_endpoint(request: Request, data: SearchOpen) -> dict[str, Any]:
    import subprocess

    vault_path = os.environ.get("NINA_VAULT_PATH", "")
    full_path = os.path.join(vault_path, data.path)
    subprocess.run(["xdg-open", f"obsidian://open?path={full_path}"], capture_output=True)
    return {"opened": True}


@app.post("/ask")
async def ask_endpoint(request: Request, data: AskQuery) -> dict[str, Any]:
    db_path = os.environ.get("NINA_DATABASE_PATH", "")
    vault_path = os.environ.get("NINA_VAULT_PATH", "")
    return await ask_obsidian(db_path, vault_path, data.question, data.limit)


@app.post("/llm/complete")
async def llm_complete(request: Request, data: LLMRequest) -> dict[str, Any]:
    db_path = os.environ.get("NINA_DATABASE_PATH", "")
    service = LLMService(db_path)
    response = await service.complete(data)
    return {"response": response.response, "model": response.model, "provider": response.provider}


@app.get("/llm/interactions")
async def llm_interactions(request: Request) -> list[dict[str, Any]]:
    db_path = os.environ.get("NINA_DATABASE_PATH", "")
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
async def send_session_message(request: Request, session_id: str, data: SessionMessageCreate) -> dict[str, Any]:
    service = get_session_service(request)
    try:
        return await service.send_message(session_id, data.content)
    except RuntimeError as exc:
        message = str(exc)
        status = 404 if message.startswith("Unknown session") else 400
        return JSONResponse(status_code=status, content={"detail": message})


@app.post("/research/run")
async def run_research(request: Request, data: ResearchRunInput) -> dict[str, Any]:
    db_path = os.environ.get("NINA_DATABASE_PATH", "")
    runner = WorkflowRunner(db_path)
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
    return ["summarize-last-day", "research-topic"]


@app.post("/workflows/{workflow_name}/run")
async def run_workflow(request: Request, workflow_name: str, data: WorkflowInput) -> dict[str, Any]:
    db_path = os.environ.get("NINA_DATABASE_PATH", "")
    runner = WorkflowRunner(db_path)
    return runner.run(workflow_name, data.input)


@app.get("/workflow-runs")
async def list_workflow_runs(request: Request) -> list[dict[str, Any]]:
    db_path = os.environ.get("NINA_DATABASE_PATH", "")
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
    db_path = os.environ.get("NINA_DATABASE_PATH", "")
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
