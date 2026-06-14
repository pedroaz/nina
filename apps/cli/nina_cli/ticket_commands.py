from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from .api import request

console = Console()

ticket_app = typer.Typer(help="Ticket commands")


@ticket_app.command("list")
def ticket_list() -> None:
    resp = request("GET", "/tickets")
    tasks = resp.json()
    table = Table("ID", "Title", "Status", "Column")
    for task in tasks:
        table.add_row(task["id"], task["title"], task["status"], task["kanban_column"])
    console.print(table)


@ticket_app.command("create")
def ticket_create(
    title: str,
    description: str = typer.Option("", help="Description"),
    project_id: str = typer.Option(None, help="Project ID"),
) -> None:
    data: dict[str, Any] = {"title": title, "description": description}
    if project_id:
        data["project_id"] = project_id
    resp = request("POST", "/tickets", json=data)
    task = resp.json()
    console.print(f"Created ticket {task['id']}")


@ticket_app.command("show")
def ticket_show(ticket_id: str) -> None:
    resp = request("GET", f"/tickets/{ticket_id}")
    task = resp.json()
    console.print(f"ID: {task['id']}")
    console.print(f"Title: {task['title']}")
    console.print(f"Status: {task['status']}")
    console.print(f"Column: {task['kanban_column']}")
    console.print(f"Note: {task['note_path']}")


@ticket_app.command("delete")
def ticket_delete(ticket_id: str) -> None:
    request("DELETE", f"/tickets/{ticket_id}")
    console.print(f"Deleted ticket {ticket_id}")


@ticket_app.command("update")
def ticket_update(
    ticket_id: str,
    title: str = typer.Option(None, help="Title"),
    status: str = typer.Option(None, help="Status"),
    column: str = typer.Option(None, help="Kanban column"),
) -> None:
    data: dict[str, Any] = {}
    if title:
        data["title"] = title
    if status:
        data["status"] = status
    if data:
        request("PATCH", f"/tickets/{ticket_id}", json=data)
    if column:
        request(
            "POST",
            "/kanban/move",
            json={"task_id": ticket_id, "to_column": column, "to_position": 0},
        )
    console.print(f"Updated ticket {ticket_id}")


@ticket_app.command("move")
def ticket_move(
    ticket_id: str,
    column: str = typer.Option(..., "--column", "--to", help="Target kanban column"),
    position: int = typer.Option(0, help="Target zero-based position"),
) -> None:
    resp = request(
        "POST",
        "/kanban/move",
        json={"task_id": ticket_id, "to_column": column, "to_position": position},
    )
    task = resp.json()
    console.print(f"Moved ticket {task['id']} to {task['kanban_column']}:{task['kanban_position']}")


@ticket_app.command("done")
def ticket_done(ticket_id: str) -> None:
    request("PATCH", f"/tickets/{ticket_id}", json={"status": "done"})
    resp = request(
        "POST",
        "/kanban/move",
        json={"task_id": ticket_id, "to_column": "Done", "to_position": 0},
    )
    task = resp.json()
    console.print(f"Completed ticket {task['id']}")
