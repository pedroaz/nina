from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from .api import request
from .repo_commands import resolve_repository_id

console = Console()


task_app = typer.Typer(help="Task commands")


@task_app.command("list")
def task_list(
    task_type: str | None = typer.Option(None, "--type", help="Filter by task_type"),
    status: str | None = typer.Option(None, help="Filter by agent status (idle/working/error)"),
    include_archived: bool = typer.Option(False, "--all", help="Include archived tasks"),
) -> None:
    params: dict[str, Any] = {}
    if task_type:
        params["task_type"] = task_type
    if status:
        params["status"] = status
    if include_archived:
        params["include_archived"] = True
    resp = request("GET", "/tasks", params=params)
    tasks = resp.json()
    table = Table("ID", "Title", "Type", "Agent", "Repository")
    for t in tasks:
        table.add_row(
            t["id"],
            t["title"],
            t["task_type"],
            t["status"],
            t.get("repository_name") or t.get("repository_path") or "",
        )
    console.print(table)


@task_app.command("create")
def task_create(
    title: str,
    description: str = typer.Option("", help="Description"),
    repository: str = typer.Option(
        None, "--repo", help="Repository id, name, or path for coding/reviewing tasks"
    ),
    task_type: str = typer.Option(
        None,
        "--type",
        help="Initial task_type (defaults to unclassified, which triggers AI classification)",
    ),
    no_classify: bool = typer.Option(
        False, "--no-classify", help="Skip the background AI classifier"
    ),
    auto_run: bool = typer.Option(
        False, "--auto-run", help="After creation, classify if needed and run the task"
    ),
) -> None:
    data: dict[str, Any] = {"title": title, "description": description}
    repository_id = resolve_repository_id(repository)
    if repository_id:
        data["repository_id"] = repository_id
    if task_type:
        data["task_type"] = task_type
    if no_classify:
        data["auto_classify"] = False
    if auto_run:
        data["auto_run"] = True
    resp = request("POST", "/tasks", json=data)
    t = resp.json()
    console.print(f"Created task {t['id']} (type={t['task_type']})")


@task_app.command("show")
def task_show(task_id: str) -> None:
    resp = request("GET", f"/tasks/{task_id}")
    t = resp.json()
    console.print(f"ID: {t['id']}")
    console.print(f"Title: {t['title']}")
    console.print(f"Type: {t['task_type']}")
    console.print(f"Status: {t['status']}")
    if t.get("repository_id"):
        console.print(f"Repository: {t.get('repository_name') or t['repository_id']}")
        if t.get("repository_path"):
            console.print(f"Repository path: {t['repository_path']}")
    console.print(f"Classified at: {t['classified_at'] or '(not yet)'}")
    if t["classification_reason"]:
        console.print(f"Reason: {t['classification_reason']}")
    if t["classification_model"]:
        console.print(f"Model: {t['classification_model']}")


@task_app.command("delete")
def task_delete(task_id: str) -> None:
    request("DELETE", f"/tasks/{task_id}")
    console.print(f"Deleted task {task_id}")


@task_app.command("classify")
def task_classify(task_id: str) -> None:
    """Re-run the AI classifier on a task."""

    resp = request("POST", f"/tasks/{task_id}/classify")
    payload = resp.json()
    if payload.get("status") != "completed":
        console.print(f"Classification failed: {payload}")
        raise typer.Exit(1)
    output = payload.get("output", {})
    console.print(
        f"Classified task {task_id} as {output.get('task_type')}"
        + (f" — {output.get('reason')}" if output.get("reason") else "")
    )


@task_app.command("type")
def task_type(task_id: str, new_type: str) -> None:
    """Set the task_type directly, bypassing the AI classifier."""

    request("PATCH", f"/tasks/{task_id}", json={"task_type": new_type})
    console.print(f"Task {task_id} is now {new_type}")


@task_app.command("run")
def task_run(task_id: str) -> None:
    """Route the task to its handler. Stub for now."""

    resp = request("POST", f"/tasks/{task_id}/run")
    payload = resp.json()
    if payload.get("status") != "completed":
        console.print(f"Run failed: {payload}")
        raise typer.Exit(1)
    output = payload.get("output", {})
    would = output.get("would_route_to")
    if output.get("status") == "completed" and output.get("task_type") == "done":
        console.print(f"Task {task_id} completed.")
    elif would:
        console.print(f"Task {task_id} running {would}.")
    else:
        console.print(f"Task {task_id} skipped: {output.get('reason', 'no route')}")


@task_app.command("archive")
def task_archive(task_id: str) -> None:
    resp = request("POST", f"/tasks/{task_id}/archive")
    task = resp.json()
    console.print(f"Archived task {task['id']}")


@task_app.command("unarchive")
def task_unarchive(task_id: str) -> None:
    resp = request("POST", f"/tasks/{task_id}/unarchive")
    task = resp.json()
    console.print(f"Unarchived task {task['id']}")


@task_app.command("board")
def task_board() -> None:
    """Print the type-grouped view (replaces `nina kanban show`)."""

    resp = request("GET", "/tasks/grouped-by-type")
    grouped = resp.json()
    table = Table("Type", "Count", "IDs")
    for task_type, items in grouped.items():
        ids = ", ".join(item["id"] for item in items)
        table.add_row(task_type, str(len(items)), ids)
    console.print(table)
