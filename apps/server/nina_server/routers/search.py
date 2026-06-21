from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from nina_core.search.indexer import ask_obsidian, index_notes, search

from ..dependencies import _active_config_path, _active_vault_path
from ..schemas import AskQuery, SearchOpen, SearchQuery


router = APIRouter()


@router.post("/search")
async def search_endpoint(request: Request, data: SearchQuery) -> list[dict[str, Any]]:
    db_path = _active_config_path()
    return search(db_path, data.query, data.limit)


@router.post("/search/reindex")
async def reindex_endpoint(request: Request) -> dict[str, bool]:
    db_path = _active_config_path()
    vault_path = _active_vault_path()
    index_notes(db_path, vault_path)
    return {"reindexed": True}


@router.post("/search/open")
async def open_endpoint(request: Request, data: SearchOpen) -> dict[str, bool]:
    import subprocess

    vault_path = _active_vault_path()
    full_path = Path(vault_path) / data.path
    if not full_path.exists():
        raise HTTPException(status_code=404, detail="Note not found")
    subprocess.run(["xdg-open", f"obsidian://open?path={full_path}"], capture_output=True)
    return {"opened": True}


@router.post("/ask")
async def ask_endpoint(request: Request, data: AskQuery) -> dict[str, Any]:
    db_path = _active_config_path()
    vault_path = _active_vault_path()
    return await ask_obsidian(db_path, vault_path, data.question, data.limit)
