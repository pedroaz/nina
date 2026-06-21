from __future__ import annotations

import json
from typing import Any

import typer
from rich.table import Table

from .api import request
from .output import console, print_json

workflow_app = typer.Typer(help="Workflow commands")


def _parse_input(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        console.print(f"Invalid JSON input: {exc}")
        raise typer.Exit(2) from None
    if not isinstance(parsed, dict):
        console.print("Workflow input must be a JSON object.")
        raise typer.Exit(2)
    return parsed


@workflow_app.command("list")
def workflow_list(
    json_output: bool = typer.Option(False, "--json", help="Print JSON"),
) -> None:
    workflows = request("GET", "/workflows").json()
    if json_output:
        print_json(workflows)
        return
    table = Table("Name", "Description")
    for workflow in workflows:
        table.add_row(workflow.get("name", ""), workflow.get("description", ""))
    console.print(table)


@workflow_app.command("run")
def workflow_run(
    workflow_name: str = typer.Argument(..., help="Workflow name"),
    input_json: str = typer.Option("{}", "--input-json", "-i", help="JSON object input"),
    json_output: bool = typer.Option(False, "--json", help="Print JSON"),
) -> None:
    payload = _parse_input(input_json)
    result = request("POST", f"/workflows/{workflow_name}/run", json={"input": payload}).json()
    if json_output:
        print_json(result)
        return
    console.print(
        f"Ran workflow {result.get('workflow_name', workflow_name)} -> "
        f"{result.get('status', 'unknown')} ({result.get('id', '')})"
    )
    output = result.get("output")
    if isinstance(output, dict) and output:
        for key, value in output.items():
            console.print(f"  {key}: {value}")


@workflow_app.command("runs")
def workflow_runs(
    json_output: bool = typer.Option(False, "--json", help="Print JSON"),
) -> None:
    runs = request("GET", "/workflow-runs").json()
    if json_output:
        print_json(runs)
        return
    table = Table("ID", "Workflow", "Status", "Created")
    for run in runs:
        table.add_row(
            run.get("id", ""),
            run.get("workflow_name", ""),
            run.get("status", ""),
            run.get("created_at", ""),
        )
    console.print(table)


@workflow_app.command("show")
def workflow_show(
    run_id: str = typer.Argument(..., help="Workflow run id"),
    json_output: bool = typer.Option(False, "--json", help="Print JSON"),
) -> None:
    run = request("GET", f"/workflow-runs/{run_id}").json()
    if json_output:
        print_json(run)
        return
    console.print(f"ID: {run.get('id', '')}")
    console.print(f"Workflow: {run.get('workflow_name', '')}")
    console.print(f"Status: {run.get('status', '')}")
    console.print(f"Created: {run.get('created_at', '')}")
    if run.get("input"):
        console.print(f"Input: {run['input']}")
