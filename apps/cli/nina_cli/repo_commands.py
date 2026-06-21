from __future__ import annotations

from typing import Any

import typer
from rich.table import Table

from .api import request
from .output import console


repo_app = typer.Typer(help="Repository commands")


def resolve_repository_id(value: str | None) -> str | None:
    if not value:
        return None
    repos = request("GET", "/repositories").json()
    matches = [
        repo
        for repo in repos
        if value in {repo.get("id"), repo.get("name"), repo.get("path")}
    ]
    if len(matches) == 1:
        return str(matches[0]["id"])
    if len(matches) > 1:
        console.print(f"Repository reference is ambiguous: {value}")
        raise typer.Exit(1)
    console.print(f"Repository not found: {value}. Register it with nina repo add PATH.")
    raise typer.Exit(1)


def _print_repo(repo: dict[str, Any]) -> None:
    console.print(f"ID: {repo['id']}")
    console.print(f"Name: {repo['name']}")
    console.print(f"Path: {repo['path']}")
    console.print(f"Created: {repo['created_at']}")
    console.print(f"Updated: {repo['updated_at']}")


@repo_app.command("list")
def repo_list() -> None:
    repos = request("GET", "/repositories").json()
    table = Table("ID", "Name", "Path")
    for repo in repos:
        table.add_row(repo["id"], repo["name"], repo["path"])
    console.print(table)


@repo_app.command("add")
def repo_add(
    path: str,
    name: str | None = typer.Option(None, "--name", "-n", help="Display name"),
) -> None:
    repo = request("POST", "/repositories", json={"path": path, "name": name}).json()
    console.print(f"Registered repository {repo['name']} ({repo['id']})")
    console.print(repo["path"])


@repo_app.command("show")
def repo_show(repository: str) -> None:
    repo_id = resolve_repository_id(repository)
    repo = request("GET", f"/repositories/{repo_id}").json()
    _print_repo(repo)


@repo_app.command("remove")
def repo_remove(repository: str) -> None:
    repo_id = resolve_repository_id(repository)
    request("DELETE", f"/repositories/{repo_id}")
    console.print(f"Removed repository {repository}")
