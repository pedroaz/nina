from __future__ import annotations

import shlex
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request

from nina_core.search.indexer import ask_obsidian, index_notes, scan_vault, search

from ..dependencies import _active_config_path, _active_vault_path, _request_config, get_db_session
from ..schemas import AskQuery, SearchOpen, SearchQuery


router = APIRouter()

AUTO_OPEN_COMMAND = "auto"
LEGACY_OBSIDIAN_PATH_COMMAND = "xdg-open obsidian://open?path={path}"


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
    vault_path = Path(_active_vault_path()).resolve()
    full_path, rel_path = _resolve_note_path(vault_path, data.path)
    if not full_path.exists():
        raise HTTPException(status_code=404, detail="Note not found")

    config = _request_config(request)
    command_template = config.meetings.open_command or AUTO_OPEN_COMMAND
    try:
        command = _build_open_command(command_template, vault_path, full_path, rel_path)
    except (KeyError, ValueError) as exc:
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


def _resolve_note_path(vault_path: Path, requested: str) -> tuple[Path, Path]:
    requested_path = Path(requested)
    full_path = (
        requested_path.resolve()
        if requested_path.is_absolute()
        else (vault_path / requested_path).resolve()
    )
    try:
        rel_path = full_path.relative_to(vault_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Note path must be inside the vault") from exc
    return full_path, rel_path


def _build_open_command(
    command_template: str,
    vault_path: Path,
    full_path: Path,
    rel_path: Path,
) -> list[str]:
    template = command_template.strip()
    if template in {"", AUTO_OPEN_COMMAND, LEGACY_OBSIDIAN_PATH_COMMAND}:
        return ["xdg-open", _obsidian_uri(vault_path, rel_path)]

    values = _open_command_values(vault_path, full_path, rel_path)
    return [part.format(**values) for part in shlex.split(command_template)]


def _open_command_values(vault_path: Path, full_path: Path, rel_path: Path) -> dict[str, str]:
    return {
        "path": str(full_path),
        "relpath": rel_path.as_posix(),
        "vault": str(vault_path),
        "vault_name": vault_path.name,
        "uri": _obsidian_uri(vault_path, rel_path),
        "file_uri": full_path.as_uri(),
    }


def _obsidian_uri(vault_path: Path, rel_path: Path) -> str:
    return f"obsidian://open?vault={quote(vault_path.name)}&file={quote(rel_path.as_posix())}"


@router.post("/ask")
async def ask_endpoint(request: Request, data: AskQuery) -> dict[str, Any]:
    db_path = _active_config_path()
    vault_path = _active_vault_path()
    return await ask_obsidian(db_path, vault_path, data.question, data.limit)
