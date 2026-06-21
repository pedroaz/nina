from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from nina_core.config import get_config_dir
from nina_core.integrations import (
    INTEGRATION_NAMES,
    delete_credentials,
    get_integration,
    load_credentials,
    save_credentials,
)

from .api import request
from .output import print_json


console = Console()
integrations_app = typer.Typer(help="External integrations (Confluence, Jira, Slack, Teams)")


def _request_json(
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    if payload is None:
        response = request(method, path, **kwargs)
    else:
        response = request(method, path, json=payload, **kwargs)
    if not response.content:
        return {}
    try:
        return response.json()
    except json.JSONDecodeError:
        return {"raw": response.text}


def _format_status(value: str) -> str:
    if value == "ok":
        return "[green]ok[/green]"
    if value == "failed":
        return "[red]failed[/red]"
    if value == "not_configured":
        return "[grey50]not configured[/grey50]"
    return value


def _format_time(value: str | None) -> str:
    if not value:
        return "never"
    return value


@integrations_app.callback(invoke_without_command=True)
def integrations_main(
    ctx: typer.Context,
    json_output: bool = typer.Option(False, "--json", help="Print JSON"),
) -> None:
    if ctx.invoked_subcommand is not None:
        return
    data = _request_json("GET", "/integrations")
    items = data.get("integrations", [])
    if json_output:
        print_json(items)
        return
    if not items:
        console.print("No integrations registered.")
        return
    table = Table(
        "Name",
        "Status",
        "Configured",
        "Last test",
        "Identity",
        "Latency",
        title="Integrations",
    )
    for item in items:
        last = item.get("last_test") or {}
        identity = last.get("identity") or {}
        identity_line = identity.get("display_name") or "—"
        if identity.get("workspace"):
            identity_line = f"{identity_line} ({identity['workspace']})"
        table.add_row(
            item.get("display_name", item.get("name", "")),
            _format_status(item.get("status", "")),
            "yes" if item.get("configured") else "no",
            _format_time(last.get("tested_at")),
            identity_line,
            f"{last.get('latency_ms', 0)}ms" if last else "—",
        )
    console.print(table)


@integrations_app.command("list")
def integrations_list(
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """List all integrations and their last test result."""

    integrations_main.callback(None, json_output=json_output)  # type: ignore[arg-type]


@integrations_app.command("status")
def integrations_status(
    name: str = typer.Argument(..., help="Integration name"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Show a single integration's details and last test result."""

    data = _request_json("GET", f"/integrations/{name}")
    if not data or "name" not in data:
        console.print(f"Unknown integration: {name}")
        raise typer.Exit(1)
    if json_output:
        print_json(data)
        return
    last = data.get("last_test") or {}
    identity = last.get("identity") or {}
    lines = [
        f"Name: {data.get('display_name')} ({data.get('name')})",
        f"Description: {data.get('description')}",
        f"Auth style: {data.get('auth_style')}",
        f"Docs: {data.get('docs_url')}",
        f"Configured: {'yes' if data.get('configured') else 'no'}",
        f"Status: {_format_status(data.get('status', ''))}",
        f"Last test: {_format_time(last.get('tested_at'))}",
    ]
    if last.get("latency_ms") is not None:
        lines.append(f"Latency: {last.get('latency_ms')}ms")
    if identity:
        lines.append(
            "Identity: "
            + identity.get("display_name", "")
            + (f" <{identity.get('email')}>" if identity.get("email") else "")
        )
        if identity.get("workspace"):
            lines.append(f"Workspace: {identity['workspace']}")
    if last.get("error"):
        lines.append(f"Error: {last['error']}")
    console.print("\n".join(lines))


@integrations_app.command("test")
def integrations_test(
    name: str | None = typer.Argument(
        None, help="Integration name (omit with --all to test every configured one)"
    ),
    all: bool = typer.Option(False, "--all", help="Test every configured integration"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Run the identity ping for one (or all configured) integration(s)."""

    if all and name:
        console.print("Pass either a name or --all, not both.")
        raise typer.Exit(2)
    if not all and not name:
        console.print("Provide an integration name or pass --all.")
        raise typer.Exit(2)
    targets: list[str] = []
    if all:
        listed = _request_json("GET", "/integrations").get("integrations", [])
        targets = [
            item["name"]
            for item in listed
            if item.get("configured") and item.get("name") in INTEGRATION_NAMES()
        ]
        if not targets:
            console.print("No configured integrations to test.")
            return
    else:
        available = list(INTEGRATION_NAMES())
        if name not in available:
            console.print(f"Unknown integration: {name}")
            console.print(f"Available: {', '.join(sorted(available))}")
            raise typer.Exit(1)
        targets = [name]
    results: list[dict[str, Any]] = []
    for target in targets:
        with console.status(f"Testing {target}…"):
            data = _request_json("POST", f"/integrations/{target}/test")
        results.append({"name": target, "result": data})
    if json_output:
        print_json(results)
        return
    table = Table("Name", "Status", "Latency", "Identity", "Error", title="Test results")
    for entry in results:
        result = entry["result"]
        identity = (result.get("identity") or {}) if isinstance(result, dict) else {}
        identity_line = identity.get("display_name") or "—"
        table.add_row(
            entry["name"],
            _format_status(result.get("status", "")) if isinstance(result, dict) else "—",
            f"{result.get('latency_ms', 0)}ms" if isinstance(result, dict) else "—",
            identity_line,
            (result.get("error") or "—") if isinstance(result, dict) else "—",
        )
    console.print(table)


@integrations_app.command("history")
def integrations_history(
    name: str = typer.Argument(..., help="Integration name"),
    limit: int = typer.Option(10, "--limit", "-n"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """List recent test runs for an integration."""

    if name not in INTEGRATION_NAMES():
        console.print(f"Unknown integration: {name}")
        raise typer.Exit(1)
    data = _request_json(
        "GET", f"/integrations/{name}/tests", payload=None, params={"limit": limit}
    )
    rows = data.get("tests", [])
    if json_output:
        print_json(rows)
        return
    if not rows:
        console.print("No test history yet.")
        return
    table = Table("When", "Status", "Latency", "Identity", "Error", title=f"{name} test history")
    for row in rows:
        identity = row.get("identity") or {}
        table.add_row(
            row.get("tested_at", ""),
            _format_status(row.get("status", "")),
            f"{row.get('latency_ms', 0)}ms",
            identity.get("display_name") or "—",
            row.get("error") or "—",
        )
    console.print(table)


@integrations_app.command("configure")
def integrations_configure(
    name: str = typer.Argument(..., help="Integration name"),
    set_json: str | None = typer.Option(
        None,
        "--json",
        help="Raw JSON object of credentials. Reads stdin if '-'.",
    ),
) -> None:
    """Store credentials for an integration.

    Pass `--json` inline, `--json -` to read from stdin, or run interactively
    to be prompted for each documented field.
    """

    if name not in INTEGRATION_NAMES():
        console.print(f"Unknown integration: {name}")
        raise typer.Exit(1)

    payload: dict[str, Any]
    raw = set_json
    if raw is None:
        raw = typer.prompt(
            "Paste credentials as JSON (or press Ctrl+C to abort)",
            default="",
            show_default=False,
        )
        if not raw.strip():
            console.print("No credentials provided.")
            raise typer.Exit(1)
    elif raw == "-":
        raw = sys.stdin.read()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        console.print(f"Invalid JSON: {exc}")
        raise typer.Exit(2) from None
    if not isinstance(parsed, dict) or not parsed:
        console.print("Credentials JSON must be a non-empty object.")
        raise typer.Exit(2)
    payload = {str(k): v for k, v in parsed.items() if v is not None}
    save_credentials(name, payload, config_dir=get_config_dir())
    try:
        typer.echo(
            f"Saved credentials for {name} at {Path(get_config_dir()) / 'integrations' / f'{name}.json'}"
        )
    finally:
        _refresh_token_env()


def _refresh_token_env() -> None:
    # The CLI is invoked without going through the daemon; this is a no-op
    # placeholder so the function can be extended later if needed.
    return None


@integrations_app.command("clear")
def integrations_clear(
    name: str = typer.Argument(..., help="Integration name"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
) -> None:
    """Remove stored credentials for an integration."""

    if name not in INTEGRATION_NAMES():
        console.print(f"Unknown integration: {name}")
        raise typer.Exit(1)
    if not yes:
        confirm = typer.confirm(f"Delete stored credentials for {name}?")
        if not confirm:
            raise typer.Abort()
    deleted = delete_credentials(name, config_dir=get_config_dir())
    if deleted:
        console.print(f"Removed credentials for {name}.")
    else:
        console.print(f"No credentials were stored for {name}.")


@integrations_app.command("show-fields")
def integrations_show_fields(
    name: str = typer.Argument(..., help="Integration name"),
) -> None:
    """Print the credential fields a given integration expects."""

    integration = get_integration(name)
    if integration is None:
        console.print(f"Unknown integration: {name}")
        raise typer.Exit(1)
    creds = load_credentials(name, config_dir=get_config_dir()) or {}
    console.print(f"Integration: {integration.info.display_name} ({name})")
    console.print(f"Auth style: {integration.info.auth_style}")
    console.print("Configured fields:")
    if not creds:
        console.print("  (none)")
        return
    for key, value in creds.items():
        marker = "set" if value else "empty"
        console.print(f"  - {key}: {marker}")


@integrations_app.command("path")
def integrations_path() -> None:
    """Print the directory that holds stored integration credentials."""

    config_dir = get_config_dir()
    integrations_dir = config_dir / "integrations"
    console.print(str(integrations_dir))
