import hashlib
import os
from pathlib import Path
from typing import Any

import frontmatter
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from nina_core.models.models import Note


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def scan_vault(db: Session, vault_path: str) -> list[Note]:
    vault = Path(vault_path)
    notes: list[Note] = []
    for root, _dirs, files in os.walk(vault):
        for filename in files:
            if not filename.endswith(".md"):
                continue
            path = Path(root) / filename
            rel_path = str(path.relative_to(vault))
            content = path.read_text()
            post = frontmatter.loads(content)
            title = post.metadata.get("title", path.stem)
            content_hash = _hash_file(path)
            note = db.query(Note).filter(Note.path == rel_path).first()
            now = _now()
            if not note:
                note = Note(
                    id=_hash_path(rel_path),
                    nina_type=post.metadata.get("nina_type", "note"),
                    entity_id=post.metadata.get("nina_id"),
                    path=rel_path,
                    title=title,
                    content_hash=content_hash,
                    last_indexed_at=now,
                    created_at=now,
                    updated_at=now,
                )
                db.add(note)
            elif note.content_hash != content_hash:
                note.title = title
                note.content_hash = content_hash
                note.last_indexed_at = now
                note.updated_at = now
            notes.append(note)
    db.commit()
    return notes


def _hash_path(path: str) -> str:
    return hashlib.sha256(path.encode()).hexdigest()[:32]


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def create_fts_table(db_path: str) -> None:
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    with engine.connect() as conn:
        conn.execute(
            text(
                "CREATE VIRTUAL TABLE IF NOT EXISTS note_search USING fts5(note_id UNINDEXED, title, body, path UNINDEXED, nina_type UNINDEXED)"
            )
        )
        conn.commit()


def index_notes(db_path: str, vault_path: str) -> None:
    create_fts_table(db_path)
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM note_search"))
        conn.commit()
    vault = Path(vault_path)
    for root, _dirs, files in os.walk(vault):
        for filename in files:
            if not filename.endswith(".md"):
                continue
            path = Path(root) / filename
            rel_path = str(path.relative_to(vault))
            content = path.read_text()
            post = frontmatter.loads(content)
            note_id = post.metadata.get("nina_id", "")
            nina_type = post.metadata.get("nina_type", "note")
            title = post.metadata.get("title", path.stem)
            body = post.content
            with engine.connect() as conn:
                conn.execute(
                    text(
                        "INSERT INTO note_search (note_id, title, body, path, nina_type) VALUES (:note_id, :title, :body, :path, :nina_type)"
                    ),
                    {
                        "note_id": note_id,
                        "title": title,
                        "body": body,
                        "path": rel_path,
                        "nina_type": nina_type,
                    },
                )
                conn.commit()


def search(db_path: str, query: str, limit: int = 20) -> list[dict[str, Any]]:
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    with engine.connect() as conn:
        result = conn.execute(
            text(
                "SELECT note_id, title, body, path, nina_type FROM note_search WHERE note_search MATCH :query LIMIT :limit"
            ),
            {"query": query, "limit": limit},
        )
        return [
            {
                "note_id": row[0],
                "title": row[1],
                "body": row[2],
                "path": row[3],
                "nina_type": row[4],
            }
            for row in result
        ]


def _context_excerpt(body: str, max_chars: int = 1600) -> str:
    compact = "\n".join(line.strip() for line in body.splitlines() if line.strip())
    if len(compact) <= max_chars:
        return compact
    return f"{compact[:max_chars].rstrip()}..."


def _ask_search_query(question: str) -> str:
    import re

    tokens = re.findall(r"[A-Za-z0-9_]+", question)
    if not tokens:
        return question
    return " OR ".join(tokens[:12])


def _build_ask_prompt(question: str, sources: list[dict[str, str]]) -> str:
    context_blocks = []
    for index, source in enumerate(sources, start=1):
        context_blocks.append(
            "\n".join(
                [
                    "Source {}: {}".format(index, source["title"]),
                    "Path: {}".format(source["path"]),
                    source["excerpt"],
                ]
            )
        )
    context = "\n\n---\n\n".join(context_blocks) or "No matching Obsidian notes were found."
    return "\n".join(
        [
            "Answer the question using only the Obsidian note context below.",
            "If the context is insufficient, say what is missing instead of guessing.",
            "Cite relevant source paths inline where useful.",
            "",
            f"Question: {question}",
            "",
            "Obsidian context:",
            context,
        ]
    )


async def ask_obsidian(db_path: str, vault_path: str, question: str, limit: int = 5) -> dict[str, Any]:
    from nina_core.llm.provider import LLMRequest, LLMService

    index_notes(db_path, vault_path)
    matches = search(db_path, _ask_search_query(question), limit)
    vault = Path(vault_path)
    sources = [
        {
            "title": match["title"],
            "path": match["path"],
            "nina_type": match["nina_type"],
            "excerpt": _context_excerpt(match["body"]),
        }
        for match in matches
        if (vault / match["path"]).is_file()
    ]
    response = await LLMService(db_path).complete(
        LLMRequest(
            purpose="obsidian_ask",
            prompt=_build_ask_prompt(question, sources),
        )
    )
    return {
        "answer": response.response,
        "sources": sources,
        "model": response.model,
        "provider": response.provider,
    }
