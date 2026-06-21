from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from nina_core.notes.service import NotePathError

from ..dependencies import get_note_service
from ..schemas import NoteCreate, NoteUpdate


router = APIRouter()


@router.get("/notes")
async def list_notes_endpoint(
    request: Request,
    folder: str | None = None,
    nina_type: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    return {
        "notes": get_note_service(request).list_notes(
            folder=folder,
            nina_type=nina_type,
            limit=limit,
        )
    }


@router.get("/notes/{path:path}")
async def get_note_endpoint(request: Request, path: str) -> dict[str, Any]:
    try:
        note = get_note_service(request).get_note(path)
    except NotePathError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if note is None:
        raise HTTPException(status_code=404, detail="Not found")
    return note


@router.post("/notes")
async def create_note_endpoint(request: Request, data: NoteCreate) -> dict[str, Any]:
    try:
        return get_note_service(request).create_note(
            data.path,
            data.body,
            nina_type=data.nina_type,
            frontmatter_patch=data.frontmatter_patch,
        )
    except NotePathError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.patch("/notes/{path:path}")
async def update_note_endpoint(request: Request, path: str, data: NoteUpdate) -> dict[str, Any]:
    service = get_note_service(request)
    try:
        if data.append is not None:
            return service.append_note(path, data.append)
        if data.body is not None:
            return service.update_note(path, data.body, frontmatter_patch=data.frontmatter_patch)
        if data.frontmatter_patch is not None:
            note = service.get_note(path)
            return service.update_note(
                path,
                note["body"] if note else "",
                frontmatter_patch=data.frontmatter_patch,
            )
    except NotePathError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    raise HTTPException(status_code=400, detail="Provide body, append, or frontmatter_patch")
