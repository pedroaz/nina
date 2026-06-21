from __future__ import annotations

from typing import Any

import typer

from .api import request
from .output import console, print_json

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
        print_json(data)
        return
    console.print(f"Provider: {data['provider']}")
    console.print(f"Model: {data['model']}")
    console.print(data["response"])
