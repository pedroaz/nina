from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from .api import request

console = Console()


task_app = typer.Typer(help="Task commands")


@task_app.command("list")
def task_list() -> None:
    resp = request("GET", "/tasks")
    tasks = resp.json()
    table = Table("ID", "Title", "Status", "Column")
    for t in tasks:
        table.add_row(t["id"], t["title"], t["status"], t["kanban_column"])
    console.print(table)


@task_app.command("create")
def task_create(
    title: str,
    description: str = typer.Option("", help="Description"),
    project_id: str = typer.Option(None, help="Project ID"),
) -> None:
    data: dict[str, Any] = {"title": title, "description": description}
    if project_id:
        data["project_id"] = project_id
    resp = request("POST", "/tasks", json=data)
    t = resp.json()
    console.print(f"Created task {t['id']}")


@task_app.command("show")
def task_show(task_id: str) -> None:
    resp = request("GET", f"/tasks/{task_id}")
    t = resp.json()
    console.print(f"ID: {t['id']}")
    console.print(f"Title: {t['title']}")
    console.print(f"Status: {t['status']}")
    console.print(f"Column: {t['kanban_column']}")
    console.print(f"Note: {t['note_path']}")


@task_app.command("delete")
def task_delete(task_id: str) -> None:
    request("DELETE", f"/tasks/{task_id}")
    console.print(f"Deleted task {task_id}")


@task_app.command("update")
def task_update(
    task_id: str,
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
        request("PATCH", f"/tasks/{task_id}", json=data)
    if column:
        request(
            "POST",
            "/kanban/move",
            json={"task_id": task_id, "to_column": column, "to_position": 0},
        )
    console.print(f"Updated task {task_id}")


@task_app.command("move")
def task_move(
    task_id: str,
    column: str = typer.Option(..., "--column", "--to", help="Target kanban column"),
    position: int = typer.Option(0, help="Target zero-based position"),
) -> None:
    resp = request(
        "POST",
        "/kanban/move",
        json={"task_id": task_id, "to_column": column, "to_position": position},
    )
    task = resp.json()
    console.print(f"Moved task {task['id']} to {task['kanban_column']}:{task['kanban_position']}")


@task_app.command("done")
def task_done(task_id: str) -> None:
    request("PATCH", f"/tasks/{task_id}", json={"status": "done"})
    resp = request(
        "POST",
        "/kanban/move",
        json={"task_id": task_id, "to_column": "Done", "to_position": 0},
    )
    task = resp.json()
    console.print(f"Completed task {task['id']}")


@task_app.command("archive")
def task_archive(task_id: str) -> None:
    resp = request("POST", f"/tasks/{task_id}/archive")
    task = resp.json()
    console.print(f"Archived task {task['id']} -> {task['status']}")


@task_app.command("unarchive")
def task_unarchive(task_id: str) -> None:
    resp = request("POST", f"/tasks/{task_id}/unarchive")
    task = resp.json()
    console.print(f"Unarchived task {task['id']} -> {task['status']}")
