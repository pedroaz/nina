from __future__ import annotations

import shlex
import subprocess
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from nina_core.search.indexer import ask_obsidian, index_notes, scan_vault, search

from ..dependencies import _active_config_path, _active_vault_path, _request_config, get_db_session
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
    with get_db_session() as db:
        scan_vault(db, vault_path)
    index_notes(db_path, vault_path)
    return {"reindexed": True}


@router.post("/search/open")
async def open_endpoint(request: Request, data: SearchOpen) -> dict[str, bool]:
    vault_path = _active_vault_path()
    full_path = Path(vault_path) / data.path
    if not full_path.exists():
        raise HTTPException(status_code=404, detail="Note not found")

    config = _request_config(request)
    command_template = config.meetings.open_command or "xdg-open obsidian://open?path={path}"
    try:
        command = [part.format(path=str(full_path)) for part in shlex.split(command_template)]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid open command: {exc}") from exc

    if not command:
        raise HTTPException(status_code=400, detail="Open command is empty")

    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=10)
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(status_code=500, detail="Open command timed out") from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Open command failed: {exc}") from exc

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "Open command exited with an error").strip()
        raise HTTPException(status_code=500, detail=detail[:500])

    return {"opened": True}


@router.post("/ask")
async def ask_endpoint(request: Request, data: AskQuery) -> dict[str, Any]:
    db_path = _active_config_path()
    vault_path = _active_vault_path()
    return await ask_obsidian(db_path, vault_path, data.question, data.limit)
