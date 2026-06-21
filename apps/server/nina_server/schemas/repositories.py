from __future__ import annotations

from pydantic import BaseModel


class RepositoryCreate(BaseModel):
    path: str
    name: str | None = None


class RepositoryResponse(BaseModel):
    id: str
    name: str
    path: str
    created_at: str
    updated_at: str


class RepositoryWorktreeResponse(BaseModel):
    path: str
    head: str | None = None
    branch: str | None = None
    bare: bool = False
    detached: bool = False
    locked: str | None = None
    prunable: str | None = None
