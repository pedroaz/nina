from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from .api import request

console = Console()

ticket_app = typer.Typer(help="Ticket commands")


@ticket_app.command("list")
def ticket_list(
    task_type: str | None = typer.Option(None, "--type", help="Filter by task_type"),
    status: str | None = typer.Option(None, help="Filter by agent status (idle/working)"),
) -> None:
    params: dict[str, Any] = {}
    if task_type:
        params["task_type"] = task_type
    if status:
        params["status"] = status
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    path = "/tickets" + (f"?{qs}" if qs else "")
    resp = request("GET", path)
    tasks = resp.json()
    table = Table("ID", "Title", "Type", "Status", "opencode_project_id")
    for t in tasks:
        table.add_row(
            t["id"],
            t["title"],
            t["task_type"],
            t["status"],
            t.get("opencode_project_id") or "",
        )
    console.print(table)


@ticket_app.command("create")
def ticket_create(
    title: str,
    description: str = typer.Option("", help="Description"),
    opencode_project_id: str = typer.Option(
        None, "--opencode-project-id", help="Server-assigned opencode project id"
    ),
    task_type: str = typer.Option(
        None, "--type", help="Initial task_type (defaults to unclassified)"
    ),
    no_classify: bool = typer.Option(False, "--no-classify", help="Skip background classifier"),
) -> None:
    data: dict[str, Any] = {"title": title, "description": description}
    if opencode_project_id:
        data["opencode_project_id"] = opencode_project_id
    if task_type:
        data["task_type"] = task_type
    if no_classify:
        data["auto_classify"] = False
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
    if task.get("opencode_project_id"):
        console.print(f"opencode_project_id: {task['opencode_project_id']}")
    if task["classification_reason"]:
        console.print(f"Reason: {task['classification_reason']}")
    console.print(f"Note: {task['note_path']}")


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
    if would:
        console.print(f"Ticket {ticket_id} routed to {would} (placeholder).")
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
