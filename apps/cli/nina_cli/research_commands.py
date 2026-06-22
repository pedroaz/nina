import typer
from rich.console import Console
from rich.table import Table

from .api import request
from .output import print_json

console = Console()
research_app = typer.Typer(help="Research commands")
DEFAULT_RESEARCH_REQUEST_TIMEOUT = 700.0


@research_app.command("run")
def research_run(
    topic: str,
    search_mode: str | None = typer.Option(
        None,
        "--search-mode",
        help="Override research search mode: live, cached, or disabled",
    ),
    as_json: bool = typer.Option(False, "--json", help="Emit JSON"),
    request_timeout: float = typer.Option(
        DEFAULT_RESEARCH_REQUEST_TIMEOUT,
        "--timeout",
        help="Daemon request timeout in seconds",
    ),
) -> None:
    payload = {"topic": topic}
    if search_mode is not None:
        payload["search_mode"] = search_mode
    resp = request("POST", "/research/run", json=payload, timeout=request_timeout)
    report = resp.json()
    if as_json:
        print_json(report)
        return
    console.print(f"Research note: {report['note_path']}")
    console.print(f"Search mode: {report.get('search_mode', '')}")
    console.print(f"Summary: {report['summary']}")
    sources = report.get("sources", [])
    if sources:
        table = Table("Title", "URL")
        for source in sources:
            table.add_row(source.get("title", ""), source.get("url", ""))
        console.print(table)
