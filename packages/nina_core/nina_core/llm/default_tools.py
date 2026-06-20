from __future__ import annotations

from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from nina_core.llm.tools import ToolContext, ToolRegistry, ToolSpec, _string_schema
from nina_core.models.models import (
    JobRun,
    LLMInteraction,
    ScheduledJob,
    Task,
)
from nina_core.notes.service import NotePathError, NoteService
from nina_core.notes.service import safe_resolve_path as _safe_resolve
from nina_core.search.embeddings import EmbeddingStore, reindex_embeddings, rrf_merge
from nina_core.search.indexer import (
    _ask_search_query,
    _context_excerpt,
    search as fts_search,
)


def _build_session(db_path: str):
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    return engine, sessionmaker(bind=engine)


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _ticket_summary(task: Task) -> dict[str, Any]:
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "task_type": task.task_type,
        "status": task.status,
        "opencode_project_id": task.opencode_project_id,
        "classified_at": task.classified_at,
        "classification_reason": task.classification_reason,
        "classification_model": task.classification_model,
        "note_path": task.note_path,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
    }


def _ensure_indexes(ctx: ToolContext) -> None:
    from nina_core.search.indexer import index_notes

    index_notes(ctx.db_path, str(ctx.vault_path))


def _obsidian_search(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    query = (args.get("query") or "").strip()
    limit = max(1, min(int(args.get("limit") or 5), 25))
    if not query:
        return {"results": []}
    _ensure_indexes(ctx)
    matches = fts_search(ctx.db_path, _ask_search_query(query), limit)
    results = []
    for match in matches:
        results.append(
            {
                "path": match["path"],
                "title": match["title"],
                "nina_type": match["nina_type"],
                "snippet": _context_excerpt(match["body"], max_chars=320),
                "ranker": "lexical",
            }
        )
    return {"results": results}


def _obsidian_semantic_search(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    query = (args.get("query") or "").strip()
    limit = max(1, min(int(args.get("limit") or 5), 25))
    if not query:
        return {"results": []}
    try:
        store = EmbeddingStore(ctx.db_path, config=ctx.search_config)
    except Exception as exc:
        return {"error": f"Embedding service unavailable: {exc}", "results": []}
    rows = store.list_rows()
    if not rows:
        # Lazy reindex
        try:
            reindex_embeddings(ctx.db_path, str(ctx.vault_path), config=ctx.search_config)
        except Exception as exc:
            return {"error": f"Embedding reindex failed: {exc}", "results": []}
        rows = store.list_rows()
    try:
        scored = store.search(query, limit=limit)
    except Exception as exc:
        return {"error": str(exc), "results": []}
    return {
        "results": [
            {
                "path": r.path,
                "title": r.title,
                "nina_type": r.nina_type,
                "score": r.score,
                "ranker": "semantic",
            }
            for r in scored
        ]
    }


def _to_scored_rows(items: list[dict[str, Any]]) -> list[Any]:
    from nina_core.search.embeddings import ScoredRow

    return [
        ScoredRow(
            path=item["path"],
            title=item["title"],
            nina_type=item["nina_type"],
            score=item.get("score", 0.0),
            note_id=item.get("note_id", ""),
        )
        for item in items
    ]


def _obsidian_hybrid_search(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    query = (args.get("query") or "").strip()
    limit = max(1, min(int(args.get("limit") or 5), 25))
    if not query:
        return {"results": []}
    _ensure_indexes(ctx)
    lexical_matches = fts_search(ctx.db_path, _ask_search_query(query), limit)
    lexical_results = [
        {
            "path": m["path"],
            "title": m["title"],
            "nina_type": m["nina_type"],
            "score": 0.0,
            "note_id": m.get("note_id") or "",
        }
        for m in lexical_matches
    ]
    semantic_results: list[dict[str, Any]] = []
    semantic_error: str | None = None
    try:
        store = EmbeddingStore(ctx.db_path, config=ctx.search_config)
        if not store.list_rows():
            try:
                reindex_embeddings(ctx.db_path, str(ctx.vault_path), config=ctx.search_config)
            except Exception as exc:
                semantic_error = str(exc)
        if not semantic_error:
            semantic_results = [
                {
                    "path": r.path,
                    "title": r.title,
                    "nina_type": r.nina_type,
                    "score": r.score,
                    "note_id": r.note_id,
                }
                for r in store.search(query, limit=limit)
            ]
    except Exception as exc:
        semantic_error = str(exc)

    if not semantic_results and semantic_error:
        return {"error": semantic_error, "results": []}
    rankings = [_to_scored_rows(lexical_results), _to_scored_rows(semantic_results)]
    rankings = [r for r in rankings if r]
    merged = rrf_merge(rankings, k=60, limit=limit)
    return {
        "results": [
            {
                "path": r.path,
                "title": r.title,
                "nina_type": r.nina_type,
                "score": r.score,
                "ranker": "hybrid",
            }
            for r in merged
        ]
    }


def _obsidian_get_note(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    path = (args.get("path") or "").strip()
    if not path:
        return {"error": "path is required"}
    try:
        _safe_resolve(ctx.vault_path, path)
    except NotePathError as exc:
        return {"error": str(exc)}
    service = NoteService(ctx.db_path, ctx.vault_path)
    note = service.get_note(path)
    if note is None:
        return {"error": f"Note not found: {path}"}
    return note


def _obsidian_list_notes(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    folder = args.get("folder")
    nina_type = args.get("nina_type")
    limit = max(1, min(int(args.get("limit") or 20), 100))
    service = NoteService(ctx.db_path, ctx.vault_path)
    return {"notes": service.list_notes(folder=folder, nina_type=nina_type, limit=limit)}


def _kanban_get(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """Group active tickets by `task_type` and return them.

    The name is preserved for backwards compatibility (it used to mean the
    kanban board; now it returns the type-grouped view that replaced it).
    """

    from nina_core.tasks.service import TaskService

    db = ctx.db
    tasks = TaskService(db, ctx.obsidian).list()
    grouped: dict[str, list[dict[str, Any]]] = {}
    for task in tasks:
        grouped.setdefault(task.task_type, []).append(_ticket_summary(task))
    return {"columns": grouped}


def _tickets_list(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from nina_core.tasks.service import TaskService

    db = ctx.db
    task_type = args.get("task_type") or args.get("status")
    opencode_project_id = args.get("opencode_project_id")
    include_archived = bool(args.get("include_archived"))
    tasks = TaskService(db, ctx.obsidian).list(
        opencode_project_id=opencode_project_id,
        task_type=task_type,
        include_archived=include_archived,
    )
    return {"tickets": [_ticket_summary(t) for t in tasks]}


def _tickets_get(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from nina_core.tasks.service import TaskService

    needle = (args.get("id_or_title") or "").strip()
    if not needle:
        return {"error": "id_or_title is required"}
    db = ctx.db
    service = TaskService(db, ctx.obsidian)
    task = service.get(needle) if needle else None
    if task is None:
        # fallback: title contains search (case-insensitive)
        lowered = needle.lower()
        for t in service.list(include_archived=True):
            if lowered in (t.title or "").lower():
                task = t
                break
    if task is None:
        return {"error": f"Ticket not found: {needle}"}
    return {"ticket": _ticket_summary(task)}


def _jobs_list(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    _engine, SessionLocal = _build_session(ctx.db_path)
    db = SessionLocal()
    try:
        jobs = db.query(ScheduledJob).order_by(ScheduledJob.name).all()
        out = []
        for job in jobs:
            out.append(
                {
                    "id": job.id,
                    "name": job.name,
                    "workflow_name": job.workflow_name,
                    "schedule": job.schedule_value,
                    "enabled": bool(job.enabled),
                    "last_run_at": job.last_run_at,
                    "next_run_at": job.next_run_at,
                }
            )
        return {"jobs": out}
    finally:
        db.close()


def _job_runs(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    name = args.get("name")
    limit = max(1, min(int(args.get("limit") or 10), 100))
    _engine, SessionLocal = _build_session(ctx.db_path)
    db = SessionLocal()
    try:
        query = db.query(JobRun)
        if name:
            query = query.filter(JobRun.job_name == name)
        runs = query.order_by(JobRun.created_at.desc()).limit(limit).all()
        out = []
        for run in runs:
            out.append(
                {
                    "id": run.id,
                    "job_name": run.job_name,
                    "scheduled_job_id": run.scheduled_job_id,
                    "workflow_run_id": run.workflow_run_id,
                    "status": run.status,
                    "started_at": run.started_at,
                    "completed_at": run.completed_at,
                    "error": run.error,
                    "created_at": run.created_at,
                }
            )
        return {"runs": out}
    finally:
        db.close()


def _llm_logs(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    limit = max(1, min(int(args.get("limit") or 10), 100))
    _engine, SessionLocal = _build_session(ctx.db_path)
    db = SessionLocal()
    try:
        rows = (
            db.query(LLMInteraction).order_by(LLMInteraction.created_at.desc()).limit(limit).all()
        )
        out = []
        for row in rows:
            out.append(
                {
                    "id": row.id,
                    "provider": row.provider,
                    "model": row.model,
                    "purpose": row.purpose,
                    "status": row.status,
                    "created_at": row.created_at,
                    "completed_at": row.completed_at,
                }
            )
        return {"interactions": out}
    finally:
        db.close()


def register_default_tools(registry: ToolRegistry) -> None:
    """Register the read-only default Nina tool set.

    The agent tool set is registered separately (see register_default_write_tools).
    """

    registry.register(
        ToolSpec(
            name="obsidian_search",
            description=(
                "Search the Obsidian vault by keyword using SQLite FTS5. "
                "Returns a list of matching notes with title, path, type, and a short snippet. "
                "Use this to find notes that mention a specific term."
            ),
            parameters=_string_schema(
                {
                    "query": {"type": "string", "description": "Search query"},
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 25,
                        "description": "Maximum number of results (default 5)",
                    },
                },
                required=["query"],
            ),
            handler=_obsidian_search,
            read_only=True,
        )
    )
    registry.register(
        ToolSpec(
            name="obsidian_semantic_search",
            description=(
                "Search the Obsidian vault by semantic similarity using a local "
                "embedding model. Returns notes whose meaning is closest to the "
                "query, ranked by cosine similarity. Useful for paraphrased or "
                "concept-level questions that don't match exact keywords."
            ),
            parameters=_string_schema(
                {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 25},
                },
                required=["query"],
            ),
            handler=_obsidian_semantic_search,
            read_only=True,
        )
    )
    registry.register(
        ToolSpec(
            name="obsidian_hybrid_search",
            description=(
                "Hybrid retrieval: combines lexical FTS5 and semantic embedding "
                "search using Reciprocal Rank Fusion (RRF). Use this when you "
                "want the best of both recall modes — keyword match plus "
                "semantic similarity."
            ),
            parameters=_string_schema(
                {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 25},
                },
                required=["query"],
            ),
            handler=_obsidian_hybrid_search,
            read_only=True,
        )
    )
    registry.register(
        ToolSpec(
            name="obsidian_get_note",
            description=(
                "Read a single Obsidian note by its vault-relative path. "
                "Returns the full body, frontmatter, and metadata."
            ),
            parameters=_string_schema(
                {
                    "path": {
                        "type": "string",
                        "description": "Vault-relative path, e.g. 'Research/codex.md'",
                    },
                },
                required=["path"],
            ),
            handler=_obsidian_get_note,
            read_only=True,
        )
    )
    registry.register(
        ToolSpec(
            name="obsidian_list_notes",
            description=(
                "List Obsidian notes, optionally filtered by folder and Nina type. "
                "Returns metadata only (path, title, nina_type, last_indexed_at)."
            ),
            parameters=_string_schema(
                {
                    "folder": {
                        "type": "string",
                        "description": "Vault-relative folder prefix, e.g. 'Research' or 'Projects'",
                    },
                    "nina_type": {
                        "type": "string",
                        "description": "Filter by nina_type (e.g. 'note', 'task', 'research_report', 'project')",
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                        "description": "Maximum number of results (default 20)",
                    },
                },
            ),
            handler=_obsidian_list_notes,
            read_only=True,
        )
    )
    registry.register(
        ToolSpec(
            name="kanban_get",
            description="Return active tickets grouped by task_type.",
            parameters=_string_schema({}),
            handler=_kanban_get,
            read_only=True,
        )
    )
    registry.register(
        ToolSpec(
            name="tickets_list",
            description="List tickets (tasks) with optional filters.",
            parameters=_string_schema(
                {
                    "task_type": {
                        "type": "string",
                        "description": "Filter by task_type (e.g. unclassified, coding, research).",
                    },
                    "opencode_project_id": {
                        "type": "string",
                        "description": "Filter by the server-assigned opencode project id.",
                    },
                    "include_archived": {"type": "boolean"},
                },
            ),
            handler=_tickets_list,
            read_only=True,
        )
    )
    registry.register(
        ToolSpec(
            name="tickets_get",
            description="Fetch a single ticket by id prefix or title substring.",
            parameters=_string_schema(
                {"id_or_title": {"type": "string"}}, required=["id_or_title"]
            ),
            handler=_tickets_get,
            read_only=True,
        )
    )
    registry.register(
        ToolSpec(
            name="jobs_list",
            description="List scheduled jobs.",
            parameters=_string_schema({}),
            handler=_jobs_list,
            read_only=True,
        )
    )
    registry.register(
        ToolSpec(
            name="job_runs",
            description="List recent job runs, optionally filtered by job name.",
            parameters=_string_schema(
                {
                    "name": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                },
            ),
            handler=_job_runs,
            read_only=True,
        )
    )
    registry.register(
        ToolSpec(
            name="llm_logs",
            description="List recent LLM interaction log entries (provider, model, purpose, status).",
            parameters=_string_schema(
                {"limit": {"type": "integer", "minimum": 1, "maximum": 100}},
            ),
            handler=_llm_logs,
            read_only=True,
        )
    )
