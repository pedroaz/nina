from __future__ import annotations

import json
from typing import Any

import typer
from rich.console import Console

from .api import request

console = Console()
llm_app = typer.Typer(help="LLM commands")


@llm_app.command("test")
def llm_test(
    prompt: str,
    model: str | None = typer.Option(None, help="Override the configured model"),
    json_output: bool = typer.Option(False, "--json", help="Print JSON"),
) -> None:
    payload: dict[str, Any] = {"purpose": "cli_test", "prompt": prompt}
    if model:
        payload["model"] = model
    resp = request("POST", "/llm/complete", json=payload)
    data = resp.json()
    if json_output:
        typer.echo(json.dumps(data, indent=2, sort_keys=False))
        return
    console.print(f"Provider: {data['provider']}")
    console.print(f"Model: {data['model']}")
    console.print(data["response"])
