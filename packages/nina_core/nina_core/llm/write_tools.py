from __future__ import annotations

from typing import Any

from nina_core.llm.tools import ToolContext, ToolRegistry, ToolSpec, _string_schema
from nina_core.notes.service import NotePathError, NoteService
from nina_core.notes.service import safe_resolve_path as _safe_resolve


def _notes_service(ctx: ToolContext) -> NoteService:
    return NoteService(ctx.db_path, ctx.vault_path)


def _require(value: Any, name: str) -> Any:
    if value is None or value == "":
        raise ValueError(f"{name} is required")
    return value


def _tickets_create(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from nina_core.projects.service import TaskService

    title = _require(args.get("title"), "title")
    description = args.get("description") or ""
    project_id = args.get("project_id")
    kanban_column = args.get("kanban_column")
    service = TaskService(ctx.db, ctx.obsidian)
    task = service.create(title, description, project_id)
    if kanban_column and kanban_column != task.kanban_column:
        from nina_core.projects.kanban import move_task

        moved = move_task(ctx.db, task.id, kanban_column, 0)
        if moved is not None:
            ctx.obsidian.update_task_note(moved)
            task = moved
    return {"ticket": _ticket_summary(task)}


def _tickets_update(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from nina_core.projects.service import TaskService

    ticket_id = _require(args.get("id"), "id")
    service = TaskService(ctx.db, ctx.obsidian)
    task = service.update(
        ticket_id,
        title=args.get("title"),
        description=args.get("description"),
        status=args.get("status"),
        kanban_column=args.get("kanban_column"),
        kanban_position=args.get("kanban_position"),
    )
    if task is None:
        return {"error": f"Ticket not found: {ticket_id}"}
    return {"ticket": _ticket_summary(task)}


def _tickets_move(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from nina_core.projects.kanban import move_task

    ticket_id = _require(args.get("id"), "id")
    column = _require(args.get("column"), "column")
    position = int(args.get("position") or 0)
    task = move_task(ctx.db, ticket_id, column, position)
    if task is None:
        return {"error": f"Ticket not found or column invalid: {ticket_id}"}
    ctx.obsidian.update_task_note(task)
    return {"ticket": _ticket_summary(task)}


def _tickets_delete(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from nina_core.projects.service import TaskService

    ticket_id = _require(args.get("id"), "id")
    service = TaskService(ctx.db, ctx.obsidian)
    deleted = service.delete(ticket_id)
    return {"deleted": deleted, "id": ticket_id}


def _tickets_archive(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from nina_core.projects.service import TaskService

    ticket_id = _require(args.get("id"), "id")
    service = TaskService(ctx.db, ctx.obsidian)
    task = service.archive(ticket_id)
    if task is None:
        return {"error": f"Ticket not found: {ticket_id}"}
    return {"ticket": _ticket_summary(task)}


def _tickets_unarchive(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from nina_core.projects.service import TaskService

    ticket_id = _require(args.get("id"), "id")
    service = TaskService(ctx.db, ctx.obsidian)
    task = service.unarchive(ticket_id)
    if task is None:
        return {"error": f"Ticket not found: {ticket_id}"}
    return {"ticket": _ticket_summary(task)}


def _projects_create(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from nina_core.projects.service import ProjectService

    name = _require(args.get("name"), "name")
    description = args.get("description") or ""
    service = ProjectService(ctx.db, ctx.obsidian)
    project = service.create(name, description)
    return {"project": _project_summary(project)}


def _projects_update(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from nina_core.projects.service import ProjectService

    project_id = _require(args.get("id"), "id")
    service = ProjectService(ctx.db, ctx.obsidian)
    project = service.update(
        project_id,
        name=args.get("name"),
        description=args.get("description"),
        status=args.get("status"),
    )
    if project is None:
        return {"error": f"Project not found: {project_id}"}
    return {"project": _project_summary(project)}


def _projects_delete(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from nina_core.projects.service import ProjectService

    project_id = _require(args.get("id"), "id")
    service = ProjectService(ctx.db, ctx.obsidian)
    deleted = service.delete(project_id)
    return {"deleted": deleted, "id": project_id}


def _notes_create(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    path = _require(args.get("path"), "path")
    body = _require(args.get("body"), "body")
    nina_type = args.get("nina_type")
    return _notes_service(ctx).create_note(path, body, nina_type=nina_type)


def _notes_append(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    path = _require(args.get("path"), "path")
    body = _require(args.get("body"), "body")
    return _notes_service(ctx).append_note(path, body)


def _notes_update(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    path = _require(args.get("path"), "path")
    body = _require(args.get("body"), "body")
    return _notes_service(ctx).update_note(
        path, body, frontmatter_patch=args.get("frontmatter_patch")
    )


def _research_run(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from nina_core.workflows.runner import WorkflowRunner

    topic = _require(args.get("topic"), "topic")
    runner = WorkflowRunner(ctx.db_path)
    result = runner.run("research-topic", {"topic": topic})
    if result.get("status") != "completed":
        return {"error": f"Research workflow failed: {result.get('status')}", "result": result}
    output = dict(result.get("output", {}))
    output["workflow_run_id"] = result.get("id")
    output["status"] = result.get("status")
    return output


def _workflows_run(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from nina_core.workflows.runner import WorkflowRunner

    name = _require(args.get("name"), "name")
    input_data = args.get("input") or {}
    runner = WorkflowRunner(ctx.db_path)
    return runner.run(name, input_data)


def _jobs_run(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from nina_core.scheduler.service import SchedulerService

    name = _require(args.get("name"), "name")
    service = SchedulerService(ctx.db_path)
    run = service.run_job_now(name)
    if run is None:
        return {"error": f"Job not found: {name}"}
    return {"run": run}


def _jobs_enable(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from nina_core.scheduler.service import SchedulerService

    name = _require(args.get("name"), "name")
    service = SchedulerService(ctx.db_path)
    job = service.enable_job(name)
    if job is None:
        return {"error": f"Job not found: {name}"}
    return {"job": job}


def _jobs_disable(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from nina_core.scheduler.service import SchedulerService

    name = _require(args.get("name"), "name")
    service = SchedulerService(ctx.db_path)
    job = service.disable_job(name)
    if job is None:
        return {"error": f"Job not found: {name}"}
    return {"job": job}


def _search_reindex(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from nina_core.search.indexer import index_notes

    index_notes(ctx.db_path, str(ctx.vault_path))
    return {"reindexed": True}


def _obsidian_open(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    path = _require(args.get("path"), "path")
    try:
        _safe_resolve(ctx.vault_path, path)
    except NotePathError as exc:
        return {"error": str(exc)}
    ok = _notes_service(ctx).open_in_obsidian(path)
    return {"opened": ok}


def _ticket_summary(task: Any) -> dict[str, Any]:
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "status": task.status,
        "kanban_column": task.kanban_column,
        "kanban_position": task.kanban_position,
        "project_id": task.project_id,
        "note_path": task.note_path,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
    }


def _project_summary(project: Any) -> dict[str, Any]:
    return {
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "status": project.status,
        "note_path": project.note_path,
        "created_at": project.created_at,
        "updated_at": project.updated_at,
    }


def register_write_tools(registry: ToolRegistry) -> None:
    """Register Nina's write tool set.

    These tools are only exposed to agent sessions. Chat sessions only see
    the read tools registered by `register_default_tools`.
    """

    registry.register(
        ToolSpec(
            name="tickets_create",
            description="Create a new ticket (task) in the kanban.",
            parameters=_string_schema(
                {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "project_id": {"type": "string"},
                    "kanban_column": {
                        "type": "string",
                        "description": "One of Backlog/Todo/Doing/Review/Done",
                    },
                },
                required=["title"],
            ),
            handler=_tickets_create,
            read_only=False,
        )
    )
    registry.register(
        ToolSpec(
            name="tickets_update",
            description="Update fields on an existing ticket.",
            parameters=_string_schema(
                {
                    "id": {"type": "string"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "status": {"type": "string"},
                    "kanban_column": {"type": "string"},
                    "kanban_position": {"type": "integer"},
                },
                required=["id"],
            ),
            handler=_tickets_update,
            read_only=False,
        )
    )
    registry.register(
        ToolSpec(
            name="tickets_move",
            description="Move a ticket to a different kanban column and position.",
            parameters=_string_schema(
                {
                    "id": {"type": "string"},
                    "column": {"type": "string"},
                    "position": {"type": "integer", "minimum": 0},
                },
                required=["id", "column"],
            ),
            handler=_tickets_move,
            read_only=False,
        )
    )
    registry.register(
        ToolSpec(
            name="tickets_delete",
            description="Soft-delete a ticket (moves the note to System/Deleted).",
            parameters=_string_schema({"id": {"type": "string"}}, required=["id"]),
            handler=_tickets_delete,
            read_only=False,
        )
    )
    registry.register(
        ToolSpec(
            name="tickets_archive",
            description="Archive a ticket (moves the note to System/Archived).",
            parameters=_string_schema({"id": {"type": "string"}}, required=["id"]),
            handler=_tickets_archive,
            read_only=False,
        )
    )
    registry.register(
        ToolSpec(
            name="tickets_unarchive",
            description="Restore an archived ticket.",
            parameters=_string_schema({"id": {"type": "string"}}, required=["id"]),
            handler=_tickets_unarchive,
            read_only=False,
        )
    )
    registry.register(
        ToolSpec(
            name="projects_create",
            description="Create a new project.",
            parameters=_string_schema(
                {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                },
                required=["name"],
            ),
            handler=_projects_create,
            read_only=False,
        )
    )
    registry.register(
        ToolSpec(
            name="projects_update",
            description="Update fields on an existing project.",
            parameters=_string_schema(
                {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "status": {"type": "string"},
                },
                required=["id"],
            ),
            handler=_projects_update,
            read_only=False,
        )
    )
    registry.register(
        ToolSpec(
            name="projects_delete",
            description="Soft-delete a project (moves the note to System/Deleted).",
            parameters=_string_schema({"id": {"type": "string"}}, required=["id"]),
            handler=_projects_delete,
            read_only=False,
        )
    )
    registry.register(
        ToolSpec(
            name="notes_create",
            description="Create a new Markdown note under the vault.",
            parameters=_string_schema(
                {
                    "path": {"type": "string"},
                    "body": {"type": "string"},
                    "nina_type": {"type": "string"},
                },
                required=["path", "body"],
            ),
            handler=_notes_create,
            read_only=False,
        )
    )
    registry.register(
        ToolSpec(
            name="notes_append",
            description="Append content to an existing note.",
            parameters=_string_schema(
                {"path": {"type": "string"}, "body": {"type": "string"}},
                required=["path", "body"],
            ),
            handler=_notes_append,
            read_only=False,
        )
    )
    registry.register(
        ToolSpec(
            name="notes_update",
            description="Replace the body (and optionally frontmatter) of an existing note.",
            parameters=_string_schema(
                {
                    "path": {"type": "string"},
                    "body": {"type": "string"},
                    "frontmatter_patch": {
                        "type": "object",
                        "additionalProperties": True,
                    },
                },
                required=["path", "body"],
            ),
            handler=_notes_update,
            read_only=False,
        )
    )
    registry.register(
        ToolSpec(
            name="research_run",
            description="Run the research workflow for a topic. Writes a research note into the vault.",
            parameters=_string_schema({"topic": {"type": "string"}}, required=["topic"]),
            handler=_research_run,
            read_only=False,
        )
    )
    registry.register(
        ToolSpec(
            name="workflows_run",
            description="Run a workflow by name (e.g. 'research-topic').",
            parameters=_string_schema(
                {
                    "name": {"type": "string"},
                    "input": {"type": "object", "additionalProperties": True},
                },
                required=["name"],
            ),
            handler=_workflows_run,
            read_only=False,
        )
    )
    registry.register(
        ToolSpec(
            name="jobs_run",
            description="Run a scheduled job immediately (does not change the schedule).",
            parameters=_string_schema({"name": {"type": "string"}}, required=["name"]),
            handler=_jobs_run,
            read_only=False,
        )
    )
    registry.register(
        ToolSpec(
            name="jobs_enable",
            description="Enable a scheduled job.",
            parameters=_string_schema({"name": {"type": "string"}}, required=["name"]),
            handler=_jobs_enable,
            read_only=False,
        )
    )
    registry.register(
        ToolSpec(
            name="jobs_disable",
            description="Disable a scheduled job.",
            parameters=_string_schema({"name": {"type": "string"}}, required=["name"]),
            handler=_jobs_disable,
            read_only=False,
        )
    )
    registry.register(
        ToolSpec(
            name="search_reindex",
            description="Reindex the Obsidian vault (FTS5 + embeddings).",
            parameters=_string_schema({}),
            handler=_search_reindex,
            read_only=False,
        )
    )
    registry.register(
        ToolSpec(
            name="obsidian_open",
            description="Open a note in Obsidian via the system URI scheme.",
            parameters=_string_schema({"path": {"type": "string"}}, required=["path"]),
            handler=_obsidian_open,
            read_only=False,
        )
    )
