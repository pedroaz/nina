from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from .api import request

console = Console()
project_app = typer.Typer(help="Project commands")
app = typer.Typer(help="Nina CLI")
app.add_typer(project_app, name="project")


@project_app.command("list")
def project_list() -> None:
    projects = request("GET", "/projects").json()
    table = Table("ID", "Name", "Status")
    for p in projects:
        table.add_row(p["id"], p["name"], p["status"])
    console.print(table)


@project_app.command("create")
def project_create(name: str, description: str = typer.Option("", help="Description")) -> None:
    resp = request("POST", "/projects", json={"name": name, "description": description})
    p = resp.json()
    console.print(f"Created project {p['id']}")


@project_app.command("show")
def project_show(project_id: str) -> None:
    p = request("GET", f"/projects/{project_id}").json()
    console.print(f"ID: {p['id']}")
    console.print(f"Name: {p['name']}")
    console.print(f"Status: {p['status']}")
    console.print(f"Note: {p['note_path']}")


@project_app.command("delete")
def project_delete(project_id: str) -> None:
    request("DELETE", f"/projects/{project_id}")
    console.print(f"Deleted project {project_id}")


@project_app.command("update")
def project_update(
    project_id: str,
    name: str = typer.Option(None, help="Name"),
    status: str = typer.Option(None, help="Status"),
) -> None:
    data: dict[str, Any] = {}
    if name:
        data["name"] = name
    if status:
        data["status"] = status
    request("PATCH", f"/projects/{project_id}", json=data)
    console.print(f"Updated project {project_id}")
