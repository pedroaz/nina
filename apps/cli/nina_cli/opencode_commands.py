from __future__ import annotations

from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from .api import request

console = Console()
opencode_app = typer.Typer(help="opencode integration commands")
projects_app = typer.Typer(help="opencode project commands")
opencode_app.add_typer(projects_app, name="projects")


def _print_json(payload: Any) -> None:
    console.print_json(data=payload)


def _format_uptime(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    minutes, secs = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m {secs}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m"


def _format_status(status: dict[str, Any]) -> None:
    state = status.get("state", "unknown")
    version = status.get("version") or "—"
    pid = status.get("pid")
    host = status.get("host", "?")
    port = status.get("port", "?")
    binary = status.get("binary_path") or "—"
    enabled = status.get("enabled")
    installed = status.get("binary_installed")
    uptime = _format_uptime(status.get("uptime_seconds"))
    last_error = status.get("last_error")

    if state == "running":
        state_line = f"OpenCode: {version} ([bold green]{state}[/bold green]"
    elif state in {"disabled", "not_installed", "stopped", "failed"}:
        state_line = f"OpenCode: ([bold yellow]{state}[/bold yellow]"
    else:
        state_line = f"OpenCode: ([bold]{state}[/bold]"
    if pid:
        state_line += f" pid {pid}"
    state_line += ")"
    console.print(state_line)
    console.print(f"  Binary: {binary}  (enabled={enabled}, installed={installed})")
    console.print(f"  Listen: http://{host}:{port}")
    if status.get("state") == "running":
        console.print(f"  Uptime: {uptime}")
    if last_error:
        console.print(f"  [yellow]Last error:[/yellow] {last_error}")


@opencode_app.command("status", help="Show the supervised opencode server status.")
def opencode_status(
    as_json: bool = typer.Option(False, "--json", help="Emit JSON"),
) -> None:
    status = request("GET", "/opencode/status").json()
    if as_json:
        _print_json(status)
        return
    _format_status(status)


@projects_app.command("list", help="List projects the opencode server knows about.")
def opencode_projects_list(
    as_json: bool = typer.Option(False, "--json", help="Emit JSON"),
) -> None:
    projects = request("GET", "/opencode/projects").json()
    if as_json:
        _print_json(projects)
        return
    if not projects:
        console.print("[yellow]No opencode projects registered.[/yellow]")
        return
    table = Table("ID", "Worktree", "VCS", "Created", "Updated")
    for project in projects:
        time = project.get("time") or {}
        table.add_row(
            project.get("id", ""),
            project.get("worktree", ""),
            project.get("vcs") or "—",
            str(time.get("created", "")),
            str(time.get("updated", "")),
        )
    console.print(table)


@projects_app.command("current", help="Show the current opencode project (if any).")
def opencode_projects_current(
    as_json: bool = typer.Option(False, "--json", help="Emit JSON"),
) -> None:
    project = request("GET", "/opencode/projects/current").json()
    if as_json:
        _print_json(project)
        return
    time = project.get("time") or {}
    console.print(f"ID: {project.get('id', '')}")
    console.print(f"Worktree: {project.get('worktree', '')}")
    console.print(f"VCS: {project.get('vcs') or '—'}")
    console.print(f"Created: {time.get('created', '')}")
    console.print(f"Updated: {time.get('updated', '')}")
