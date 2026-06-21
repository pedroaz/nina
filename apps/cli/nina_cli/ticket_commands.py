from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from .api import request
from .repo_commands import resolve_repository_id

console = Console()

ticket_app = typer.Typer(help="Ticket commands")


@ticket_app.command("list")
def ticket_list(
    task_type: str | None = typer.Option(None, "--type", help="Filter by task_type"),
    status: str | None = typer.Option(None, help="Filter by agent status (idle/working/error)"),
) -> None:
    params: dict[str, Any] = {}
    if task_type:
        params["task_type"] = task_type
    if status:
        params["status"] = status
    resp = request("GET", "/tickets", params=params)
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


@ticket_app.command("create")
def ticket_create(
    title: str,
    description: str = typer.Option("", help="Description"),
    repository: str = typer.Option(
        None, "--repo", help="Repository id, name, or path for coding/reviewing tasks"
    ),
    task_type: str = typer.Option(
        None, "--type", help="Initial task_type (defaults to unclassified)"
    ),
    no_classify: bool = typer.Option(False, "--no-classify", help="Skip background classifier"),
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
    resp = request("POST", "/tickets", json=data)
    task = resp.json()
    console.print(f"Created ticket {task['id']} (type={task['task_type']})")


@ticket_app.command("show")
def ticket_show(ticket_id: str) -> None:
    resp = request("GET", f"/tickets/{ticket_id}")
    task = resp.json()
    console.print(f"ID: {task['id']}")
    console.print(f"Title: {task['title']}")
    console.print(f"Type: {task['task_type']}")
    console.print(f"Status: {task['status']}")
    if task.get("repository_id"):
        console.print(f"Repository: {task.get('repository_name') or task['repository_id']}")
        if task.get("repository_path"):
            console.print(f"Repository path: {task['repository_path']}")
    if task["classification_reason"]:
        console.print(f"Reason: {task['classification_reason']}")


@ticket_app.command("delete")
def ticket_delete(ticket_id: str) -> None:
    request("DELETE", f"/tickets/{ticket_id}")
    console.print(f"Deleted ticket {ticket_id}")


@ticket_app.command("classify")
def ticket_classify(ticket_id: str) -> None:
    resp = request("POST", f"/tickets/{ticket_id}/classify")
    payload = resp.json()
    if payload.get("status") != "completed":
        console.print(f"Classification failed: {payload}")
        raise typer.Exit(1)
    output = payload.get("output", {})
    console.print(
        f"Classified ticket {ticket_id} as {output.get('task_type')}"
        + (f" — {output.get('reason')}" if output.get("reason") else "")
    )


@ticket_app.command("type")
def ticket_type(ticket_id: str, new_type: str) -> None:
    request("PATCH", f"/tickets/{ticket_id}", json={"task_type": new_type})
    console.print(f"Ticket {ticket_id} is now {new_type}")


@ticket_app.command("run")
def ticket_run(ticket_id: str) -> None:
    resp = request("POST", f"/tickets/{ticket_id}/run")
    payload = resp.json()
    if payload.get("status") != "completed":
        console.print(f"Run failed: {payload}")
        raise typer.Exit(1)
    output = payload.get("output", {})
    would = output.get("would_route_to")
    if output.get("status") == "completed" and output.get("task_type") == "done":
        console.print(f"Ticket {ticket_id} completed.")
    elif would:
        console.print(f"Ticket {ticket_id} running {would}.")
    else:
        console.print(f"Ticket {ticket_id} skipped: {output.get('reason', 'no route')}")


@ticket_app.command("archive")
def ticket_archive(ticket_id: str) -> None:
    resp = request("POST", f"/tickets/{ticket_id}/archive")
    task = resp.json()
    console.print(f"Archived ticket {task['id']}")


@ticket_app.command("unarchive")
def ticket_unarchive(ticket_id: str) -> None:
    resp = request("POST", f"/tickets/{ticket_id}/unarchive")
    task = resp.json()
    console.print(f"Unarchived ticket {task['id']}")
