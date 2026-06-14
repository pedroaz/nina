import os
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from nina_core.config import get_config_dir, get_token_path, read_token

console = Console()


def _api_base() -> str:
    return "http://127.0.0.1:8765"


def _headers() -> dict[str, str]:
    config_dir = get_config_dir(os.environ.get("NINA_PROFILE", "default"))
    token_path = get_token_path(config_dir)
    return {
        "Authorization": f"Bearer {read_token(token_path)}",
        "Content-Type": "application/json",
    }


project_app = typer.Typer(help="Project commands")
app = typer.Typer(help="Nina CLI")
app.add_typer(project_app, name="project")


@project_app.command("list")
def project_list() -> None:
    import httpx

    resp = httpx.get(f"{_api_base()}/projects", headers=_headers())
    resp.raise_for_status()
    projects = resp.json()
    table = Table("ID", "Name", "Status")
    for p in projects:
        table.add_row(p["id"], p["name"], p["status"])
    console.print(table)


@project_app.command("create")
def project_create(name: str, description: str = typer.Option("", help="Description")) -> None:
    import httpx

    resp = httpx.post(
        f"{_api_base()}/projects",
        headers=_headers(),
        json={"name": name, "description": description},
    )
    resp.raise_for_status()
    p = resp.json()
    console.print(f"Created project {p['id']}")


@project_app.command("show")
def project_show(project_id: str) -> None:
    import httpx

    resp = httpx.get(f"{_api_base()}/projects/{project_id}", headers=_headers())
    resp.raise_for_status()
    p = resp.json()
    console.print(f"ID: {p['id']}")
    console.print(f"Name: {p['name']}")
    console.print(f"Status: {p['status']}")
    console.print(f"Note: {p['note_path']}")


@project_app.command("delete")
def project_delete(project_id: str) -> None:
    import httpx

    resp = httpx.delete(f"{_api_base()}/projects/{project_id}", headers=_headers())
    resp.raise_for_status()
    console.print(f"Deleted project {project_id}")


@project_app.command("update")
def project_update(
    project_id: str,
    name: str = typer.Option(None, help="Name"),
    status: str = typer.Option(None, help="Status"),
) -> None:
    import httpx

    data: dict[str, Any] = {}
    if name:
        data["name"] = name
    if status:
        data["status"] = status
    resp = httpx.patch(f"{_api_base()}/projects/{project_id}", headers=_headers(), json=data)
    resp.raise_for_status()
    console.print(f"Updated project {project_id}")
