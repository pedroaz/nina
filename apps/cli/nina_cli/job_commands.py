import typer
from rich.console import Console
from rich.table import Table

from .api import request

console = Console()
job_app = typer.Typer(help="Job commands")


@job_app.command("list")
def job_list() -> None:
    resp = request("GET", "/jobs")
    jobs = resp.json()
    table = Table("Name", "Workflow", "Schedule", "Enabled", "Last Run", "Next Run")
    for job in jobs:
        table.add_row(
            job["name"],
            job["workflow_name"],
            job["schedule"],
            "yes" if job["enabled"] else "no",
            job.get("last_run_at") or "",
            job.get("next_run_at") or "",
        )
    console.print(table)


@job_app.command("create")
def job_create(
    name: str,
    schedule: str = typer.Option(..., help="Cron expression, e.g. '0 7 * * *'"),
    workflow: str = typer.Option("summarize-last-day", help="Workflow name"),
    disabled: bool = typer.Option(False, help="Create disabled"),
) -> None:
    resp = request(
        "POST",
        "/jobs",
        json={
            "name": name,
            "workflow_name": workflow,
            "schedule": schedule,
            "enabled": not disabled,
        },
    )
    job = resp.json()
    console.print(f"Saved job {job['name']}")


@job_app.command("enable")
def job_enable(name: str) -> None:
    resp = request("PATCH", f"/jobs/{name}", json={"enabled": True})
    job = resp.json()
    console.print(f"Enabled job {job['name']}")


@job_app.command("disable")
def job_disable(name: str) -> None:
    resp = request("PATCH", f"/jobs/{name}", json={"enabled": False})
    job = resp.json()
    console.print(f"Disabled job {job['name']}")


@job_app.command("run")
def job_run(name: str) -> None:
    resp = request("POST", f"/jobs/{name}/run")
    run = resp.json()
    console.print(f"Ran job {run['job_name']} -> {run['status']} ({run['id']})")


@job_app.command("runs")
def job_runs(
    name: str | None = typer.Option(None, help="Filter by job name"),
    limit: int = typer.Option(20, help="Maximum runs to show"),
) -> None:
    params: dict[str, str | int] = {"limit": limit}
    if name:
        params["job_name"] = name
    resp = request("GET", "/job-runs", params=params)
    runs = resp.json()
    table = Table("ID", "Job", "Status", "Workflow Run", "Started", "Completed", "Error")
    for run in runs:
        table.add_row(
            run["id"],
            run["job_name"],
            run["status"],
            run.get("workflow_run_id") or "",
            run.get("started_at") or "",
            run.get("completed_at") or "",
            run.get("error") or "",
        )
    console.print(table)
