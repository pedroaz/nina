from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from nina_core.repositories.service import RepositoryService

from ..dependencies import get_db_session
from ..schemas import RepositoryCreate, RepositoryResponse, RepositoryWorktreeResponse


router = APIRouter()


def _repository_to_response(repo: Any) -> RepositoryResponse:
    return RepositoryResponse(
        id=repo.id,
        name=repo.name,
        path=repo.path,
        created_at=repo.created_at,
        updated_at=repo.updated_at,
    )


def _worktree_to_response(worktree: Any) -> RepositoryWorktreeResponse:
    return RepositoryWorktreeResponse(
        path=worktree.path,
        head=worktree.head,
        branch=worktree.branch,
        bare=worktree.bare,
        detached=worktree.detached,
        locked=worktree.locked,
        prunable=worktree.prunable,
    )


@router.get("/repositories", response_model=list[RepositoryResponse])
async def list_repositories(request: Request) -> list[RepositoryResponse]:
    with get_db_session() as db:
        repos = RepositoryService(db).list()
        return [_repository_to_response(repo) for repo in repos]


@router.post("/repositories", response_model=RepositoryResponse)
async def create_repository(request: Request, data: RepositoryCreate) -> RepositoryResponse:
    with get_db_session() as db:
        try:
            repo = RepositoryService(db).create(data.path, name=data.name)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _repository_to_response(repo)


@router.get("/repositories/{repository_id}", response_model=RepositoryResponse)
async def get_repository(request: Request, repository_id: str) -> RepositoryResponse:
    with get_db_session() as db:
        repo = RepositoryService(db).get(repository_id)
        if repo is None:
            raise HTTPException(status_code=404, detail="Not found")
        return _repository_to_response(repo)


@router.get("/repositories/{repository_id}/worktrees", response_model=list[RepositoryWorktreeResponse])
async def list_repository_worktrees(
    request: Request, repository_id: str
) -> list[RepositoryWorktreeResponse]:
    with get_db_session() as db:
        try:
            worktrees = RepositoryService(db).list_worktrees(repository_id)
        except ValueError as exc:
            detail = str(exc)
            status = 404 if detail.startswith("Repository not found") else 400
            raise HTTPException(status_code=status, detail=detail) from exc
        return [_worktree_to_response(worktree) for worktree in worktrees]


@router.delete("/repositories/{repository_id}")
async def delete_repository(request: Request, repository_id: str) -> dict[str, bool]:
    with get_db_session() as db:
        try:
            deleted = RepositoryService(db).delete(repository_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not deleted:
            raise HTTPException(status_code=404, detail="Not found")
        return {"deleted": True}
