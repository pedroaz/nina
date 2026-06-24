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
    pipeline_stage: str | None
    pipeline_error: str | None
    note_path: str | None
    pipeline_rework_count: int
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
    pipeline_stage: str | None = None
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
    pipeline_stage: str | None = None
    pipeline_error: str | None = None
    pipeline_rework_count: int | None = None
    repository_id: str | None = None
