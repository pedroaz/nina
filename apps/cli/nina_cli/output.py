from __future__ import annotations

import json
from typing import Any

import typer
from rich.console import Console

console = Console()


def print_json(data: Any, *, sort_keys: bool = False) -> None:
    typer.echo(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=sort_keys))
