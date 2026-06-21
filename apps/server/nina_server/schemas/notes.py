from __future__ import annotations

from pydantic import BaseModel


class NotesQuery(BaseModel):
    folder: str | None = None
    nina_type: str | None = None
    limit: int = 20


class NoteCreate(BaseModel):
    path: str
    body: str
    nina_type: str | None = None
    frontmatter_patch: dict[str, object] | None = None


class NoteUpdate(BaseModel):
    body: str | None = None
    append: str | None = None
    frontmatter_patch: dict[str, object] | None = None
