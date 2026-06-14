import json
import os
from typing import Any

import httpx
import typer
from rich.console import Console

from nina_core.config import (
    get_config_dir,
    get_runtime_path,
    get_token_path,
    load_effective_config,
    read_token,
)

console = Console()


def api_base() -> str:
    config_dir = get_config_dir(os.environ.get("NINA_PROFILE", "default"))
    runtime_path = get_runtime_path(config_dir)
    if runtime_path.exists():
        try:
            data = json.loads(runtime_path.read_text())
            host = data.get("daemon_host")
            port = data.get("daemon_port")
            if host and port:
                return f"http://{host}:{port}"
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            pass
    config = load_effective_config(config_dir)
    return f"http://{config.daemon_host}:{config.daemon_port}"


def headers() -> dict[str, str]:
    config_dir = get_config_dir(os.environ.get("NINA_PROFILE", "default"))
    token_path = get_token_path(config_dir)
    return {
        "Authorization": f"Bearer {read_token(token_path)}",
        "Content-Type": "application/json",
    }


def request(method: str, path: str, **kwargs: Any) -> httpx.Response:
    try:
        resp = httpx.request(method, f"{api_base()}{path}", headers=headers(), timeout=10, **kwargs)
        resp.raise_for_status()
        return resp
    except httpx.ConnectError:
        console.print("Daemon is not running. Start it with `nina daemon start` or `make dev`.")
        raise typer.Exit(1) from None
    except httpx.HTTPStatusError as exc:
        detail = None
        try:
            detail = exc.response.json().get("detail")
        except Exception:
            detail = exc.response.text
        console.print(f"Request failed ({exc.response.status_code}): {detail}")
        raise typer.Exit(1) from None
