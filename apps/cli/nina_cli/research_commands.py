import typer
from rich.console import Console
from rich.table import Table

from .api import request

console = Console()
research_app = typer.Typer(help="Research commands")


@research_app.command("run")
def research_run(topic: str) -> None:
    resp = request("POST", "/research/run", json={"topic": topic})
    report = resp.json()
    console.print(f"Research note: {report['note_path']}")
    console.print(f"Summary: {report['summary']}")
    sources = report.get("sources", [])
    if sources:
        table = Table("Title", "URL")
        for source in sources:
            table.add_row(source.get("title", ""), source.get("url", ""))
        console.print(table)
