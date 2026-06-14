from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import frontmatter
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from nina_core.models.models import Note
from nina_core.obsidian.service import ObsidianService


REFUSED_PREFIXES = (
    "System/Indexes/",
    "System/Logs/",
    "System/Deleted/",
    "Templates/",
)


class NotePathError(ValueError):
    """Raised when a requested note path is not safe to use."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_path(path: str) -> str:
    import hashlib

    return hashlib.sha256(path.encode()).hexdigest()[:32]


def _hash_file(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_resolve_path(vault_path: Path, requested: str) -> Path:
    """Resolve a vault-relative path to an absolute path safely.

    - Rejects absolute paths, `..` traversal, and empty paths.
    - Rejects paths under refused prefixes (System indexes/logs/deleted, Templates).
    - Returns the absolute path; the file may or may not exist.
    """

    if not requested:
        raise NotePathError("Path cannot be empty")
    if Path(requested).is_absolute():
        raise NotePathError("Absolute paths are not allowed")
    normalized = requested.replace("\\", "/").lstrip("/")
    parts = [p for p in normalized.split("/") if p not in ("", ".")]
    if any(p == ".." for p in parts):
        raise NotePathError("Path traversal is not allowed")
    if normalized.startswith(REFUSED_PREFIXES):
        raise NotePathError(
            f"Writes and reads under {normalized.split('/', 2)[0]}/{normalized.split('/', 2)[1] if '/' in normalized else ''} are not allowed"
        )
    resolved = (vault_path / normalized).resolve()
    try:
        resolved.relative_to(vault_path.resolve())
    except ValueError as exc:
        raise NotePathError("Path resolves outside the vault") from exc
    return resolved


class NoteService:
    def __init__(self, db_path: str, vault_path: Path | str) -> None:
        self.db_path = db_path
        self.vault_path = Path(vault_path)
        self.obsidian = ObsidianService(self.vault_path)
        self.engine = create_engine(f"sqlite:///{db_path}", echo=False)
        self.SessionLocal = sessionmaker(bind=self.engine)

    def _session(self) -> Session:
        return self.SessionLocal()

    def list_notes(
        self,
        folder: str | None = None,
        nina_type: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        db = self._session()
        try:
            query = db.query(Note)
            if nina_type:
                query = query.filter(Note.nina_type == nina_type)
            rows = query.order_by(Note.updated_at.desc()).limit(max(1, limit)).all()
            out: list[dict[str, Any]] = []
            for note in rows:
                if folder and not note.path.startswith(folder.rstrip("/") + "/") and note.path != folder:
                    continue
                out.append(self._serialize(note))
            return out
        finally:
            db.close()

    def get_note(self, path: str) -> dict[str, Any] | None:
        normalized = path.lstrip("/")
        db = self._session()
        try:
            note = db.query(Note).filter(Note.path == normalized).first()
        finally:
            db.close()
        if note is None:
            return None
        full_path = self.vault_path / normalized
        if not full_path.is_file():
            return None
        text = full_path.read_text()
        post = frontmatter.loads(text)
        return {
            "path": note.path,
            "title": note.title,
            "nina_type": note.nina_type,
            "entity_id": note.entity_id,
            "frontmatter": dict(post.metadata),
            "body": post.content,
            "mtime": full_path.stat().st_mtime,
        }

    def create_note(
        self,
        path: str,
        body: str,
        nina_type: str | None = None,
        frontmatter_patch: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        full_path = safe_resolve_path(self.vault_path, path)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(body)
        return self._index_after_write(path, body, nina_type, frontmatter_patch)

    def append_note(self, path: str, body: str) -> dict[str, Any]:
        full_path = safe_resolve_path(self.vault_path, path)
        if not full_path.is_file():
            raise NotePathError(f"Cannot append to missing note: {path}")
        existing = full_path.read_text()
        separator = "" if existing.endswith("\n") else "\n"
        full_path.write_text(existing + separator + body)
        new_text = full_path.read_text()
        post = frontmatter.loads(new_text)
        return self._index_after_write(path, post.content)

    def update_note(
        self,
        path: str,
        body: str,
        frontmatter_patch: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        full_path = safe_resolve_path(self.vault_path, path)
        if not full_path.is_file():
            raise NotePathError(f"Cannot update missing note: {path}")
        post = frontmatter.loads(full_path.read_text())
        post.content = body
        if frontmatter_patch:
            for key, value in frontmatter_patch.items():
                post.metadata[key] = value
        full_path.write_text(frontmatter.dumps(post))
        return self._index_after_write(path, body, frontmatter_patch=frontmatter_patch)

    def open_in_obsidian(self, path: str) -> bool:
        import subprocess

        full_path = safe_resolve_path(self.vault_path, path)
        if not full_path.is_file():
            return False
        subprocess.run(
            ["xdg-open", f"obsidian://open?path={full_path}"],
            capture_output=True,
            check=False,
        )
        return True

    def _serialize(self, note: Note) -> dict[str, Any]:
        return {
            "path": note.path,
            "title": note.title,
            "nina_type": note.nina_type,
            "entity_id": note.entity_id,
            "last_indexed_at": note.last_indexed_at,
            "created_at": note.created_at,
            "updated_at": note.updated_at,
        }

    def _index_after_write(
        self,
        path: str,
        body: str,
        nina_type: str | None = None,
        frontmatter_patch: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        from nina_core.search.indexer import index_note

        normalized = path.lstrip("/")
        try:
            index_note(
                self.db_path,
                self.vault_path,
                normalized,
                nina_type=nina_type,
                frontmatter_patch=frontmatter_patch,
            )
        except Exception:
            # Indexing is best-effort; the write itself succeeded.
            pass
        # Also upsert the Note row so list_notes and get_note work without
        # requiring a full scan_vault pass.
        self._upsert_note_row(normalized, nina_type, frontmatter_patch)
        db = self._session()
        try:
            note = db.query(Note).filter(Note.path == normalized).first()
            if note is not None:
                return self._serialize(note)
            return {"path": normalized}
        finally:
            db.close()

    def _upsert_note_row(
        self,
        normalized_path: str,
        nina_type: str | None = None,
        frontmatter_patch: dict[str, Any] | None = None,
    ) -> None:
        full_path = self.vault_path / normalized_path
        if not full_path.is_file():
            return
        content = full_path.read_text()
        post = frontmatter.loads(content)
        title = post.metadata.get("title", full_path.stem)
        resolved_nina_type = nina_type or post.metadata.get("nina_type", "note")
        if frontmatter_patch:
            post.metadata.update(frontmatter_patch)
        content_hash = _hash_file(full_path)
        now = _now()
        db = self._session()
        try:
            note = db.query(Note).filter(Note.path == normalized_path).first()
            if note is None:
                note = Note(
                    id=_hash_path(normalized_path),
                    nina_type=resolved_nina_type,
                    entity_id=post.metadata.get("nina_id"),
                    path=normalized_path,
                    title=title,
                    content_hash=content_hash,
                    last_indexed_at=now,
                    created_at=now,
                    updated_at=now,
                )
                db.add(note)
            else:
                note.title = title
                note.content_hash = content_hash
                note.nina_type = resolved_nina_type
                note.last_indexed_at = now
                note.updated_at = now
                if frontmatter_patch and "nina_id" in frontmatter_patch:
                    note.entity_id = frontmatter_patch["nina_id"]
            db.commit()
        finally:
            db.close()
