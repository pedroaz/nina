import typer
from rich.console import Console
from rich.table import Table

from .api import request

console = Console()
kanban_app = typer.Typer(help="Kanban commands")


@kanban_app.command("show")
def kanban_show() -> None:
    resp = request("GET", "/kanban")
    board = resp.json()
    table = Table("Column", "Position", "Task ID", "Title")
    for column, tasks in board.items():
        if not tasks:
            table.add_row(column, "", "", "(empty)")
            continue
        for task in tasks:
            table.add_row(column, str(task["kanban_position"]), task["id"], task["title"])
    console.print(table)


@kanban_app.command("move")
def kanban_move(
    task_id: str,
    to: str = typer.Option(..., "--to", "--column", help="Target kanban column"),
    position: int = typer.Option(0, help="Target zero-based position"),
) -> None:
    resp = request(
        "POST",
        "/kanban/move",
        json={"task_id": task_id, "to_column": to, "to_position": position},
    )
    task = resp.json()
    console.print(f"Moved task {task['id']} to {task['kanban_column']}:{task['kanban_position']}")
