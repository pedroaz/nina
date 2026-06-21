from __future__ import annotations

from pydantic import BaseModel


class TaskResponse(BaseModel):
    id: str
    repository_id: str | None
    repository_name: str | None
    repository_path: str | None
    title: str
    description: str
    task_type: str
    status: str
    classified_at: str | None
    classification_reason: str | None
    classification_model: str | None
    created_at: str
    updated_at: str


class TaskCreate(BaseModel):
    title: str
    description: str = ""
    repository_id: str | None = None
    task_type: str | None = None
    auto_classify: bool = True
    auto_run: bool = False
    auto_run_background: bool = False


class TaskRunRequest(BaseModel):
    background: bool = False
    codex_timeout_seconds: float | None = None


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    task_type: str | None = None
    status: str | None = None
    repository_id: str | None = None
