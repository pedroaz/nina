from __future__ import annotations

import json
from typing import Any

import typer
from rich.console import Console

from .api import request

console = Console()
chat_app = typer.Typer(help="Chat commands")


def _load_or_create_chat_session(title: str = "Chat") -> dict[str, Any]:
    sessions = request("GET", "/sessions?mode=chat").json()
    if sessions:
        return request("GET", f"/sessions/{sessions[0]['id']}").json()
    return request("POST", "/sessions", json={"mode": "chat", "title": title}).json()


@chat_app.command("test")
def chat_test(
    prompt: str,
    json_output: bool = typer.Option(False, "--json", help="Print JSON"),
) -> None:
    content = prompt.strip()
    if not content:
        console.print("Prompt cannot be empty.")
        raise typer.Exit(1)

    session = _load_or_create_chat_session()
    resp = request(
        "POST",
        f"/sessions/{session['id']}/messages",
        json={"content": content},
    )
    data = resp.json()
    if json_output:
        typer.echo(json.dumps(data, indent=2, sort_keys=False))
        return

    console.print(f"Session: {data['session']['id']}")
    console.print(data["assistant"]["content"])
    sources = data.get("sources") or []
    if sources:
        console.print("\nSources:")
        for source in sources:
            title = source.get("title") or source.get("path") or "Source"
            location = source.get("path") or source.get("url") or ""
            if location:
                console.print(f"- {title}: {location}")
            else:
                console.print(f"- {title}")
