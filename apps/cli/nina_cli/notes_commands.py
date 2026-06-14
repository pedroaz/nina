from __future__ import annotations

import json
import sys
from typing import Any

import typer
from rich.console import Console

from .api import request

console = Console()
note_app = typer.Typer(help="Note commands")


def _print_json(data: Any) -> None:
    typer.echo(json.dumps(data, indent=2, ensure_ascii=False))


@note_app.command("list")
def note_list(
    folder: str | None = typer.Option(None, "--folder", help="Vault-relative folder prefix"),
    nina_type: str | None = typer.Option(None, "--type", help="Filter by nina_type"),
    limit: int = typer.Option(20, "--limit", help="Maximum number of notes"),
    json_output: bool = typer.Option(False, "--json", help="Print JSON"),
) -> None:
    params: list[tuple[str, str]] = [("limit", str(limit))]
    if folder:
        params.append(("folder", folder))
    if nina_type:
        params.append(("nina_type", nina_type))
    query = "&".join(f"{k}={v}" for k, v in params)
    response = request("GET", f"/notes?{query}")
    data = response.json()
    if json_output:
        _print_json(data)
        return
    notes = data.get("notes", [])
    if not notes:
        console.print("No notes found.")
        return
    for note in notes:
        title = note.get("title") or note.get("path")
        ntype = note.get("nina_type") or "?"
        path = note.get("path")
        console.print(f"- [{ntype}] {title} ({path})")


@note_app.command("show")
def note_show(
    path: str = typer.Argument(..., help="Vault-relative path of the note"),
    json_output: bool = typer.Option(False, "--json", help="Print JSON"),
) -> None:
    encoded = path.lstrip("/")
    response = request("GET", f"/notes/{encoded}")
    data = response.json()
    if json_output:
        _print_json(data)
        return
    console.print(f"# {data.get('title') or data.get('path')}")
    console.print(f"Path: {data.get('path')}")
    console.print(f"Type: {data.get('nina_type')}")
    body = data.get("body") or ""
    sys.stdout.write(body)
    if not body.endswith("\n"):
        sys.stdout.write("\n")


@note_app.command("create")
def note_create(
    path: str = typer.Argument(..., help="Vault-relative path of the note"),
    body: str = typer.Option(..., "--body", help="Note body (markdown)"),
    nina_type: str | None = typer.Option(None, "--type", help="Optional nina_type"),
    from_file: str | None = typer.Option(
        None, "--from-file", help="Read body from this file instead of --body"
    ),
) -> None:
    if from_file:
        body = open(from_file).read()
    response = request(
        "POST",
        "/notes",
        json={"path": path, "body": body, "nina_type": nina_type},
    )
    data = response.json()
    console.print(f"Created {data.get('path')}")


@note_app.command("append")
def note_append(
    path: str = typer.Argument(..., help="Vault-relative path of the note"),
    body: str = typer.Option(..., "--body", help="Content to append"),
    from_file: str | None = typer.Option(
        None, "--from-file", help="Read body from this file instead of --body"
    ),
) -> None:
    if from_file:
        body = open(from_file).read()
    encoded = path.lstrip("/")
    response = request("PATCH", f"/notes/{encoded}", json={"append": body})
    data = response.json()
    console.print(f"Appended to {data.get('path')}")


@note_app.command("update")
def note_update(
    path: str = typer.Argument(..., help="Vault-relative path of the note"),
    body: str | None = typer.Option(None, "--body", help="New full body"),
    from_file: str | None = typer.Option(
        None, "--from-file", help="Read new body from this file"
    ),
) -> None:
    if from_file:
        body = open(from_file).read()
    if body is None:
        console.print("Provide --body or --from-file.")
        raise typer.Exit(1)
    encoded = path.lstrip("/")
    response = request("PATCH", f"/notes/{encoded}", json={"body": body})
    data = response.json()
    console.print(f"Updated {data.get('path')}")


@note_app.command("open")
def note_open(path: str = typer.Argument(..., help="Vault-relative path of the note")) -> None:
    encoded = path.lstrip("/")
    request("POST", "/search/open", json={"path": encoded})
    console.print(f"Requested Obsidian to open {path}")
