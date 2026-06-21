import json
import os
from typing import Any

import httpx
import typer

from nina_core.config import (
    get_config_dir,
    get_runtime_path,
    get_token_path,
    load_effective_config,
    read_token,
)

from .output import console

DEFAULT_API_TIMEOUT = 10.0


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


def api_url(path: str) -> str:
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return f"{api_base()}{path}"


def _request_headers(extra_headers: dict[str, str] | None = None) -> dict[str, str]:
    request_headers = headers()
    if extra_headers:
        request_headers.update(extra_headers)
    return request_headers


def _error_detail(response: httpx.Response) -> str:
    try:
        detail = response.json().get("detail")
    except Exception:
        detail = response.text
    return str(detail)


def _httpx_request(method: str, path: str, **kwargs: Any) -> httpx.Response:
    timeout = kwargs.pop("timeout", DEFAULT_API_TIMEOUT)
    extra_headers = kwargs.pop("headers", None)
    return httpx.request(
        method,
        api_url(path),
        headers=_request_headers(extra_headers),
        timeout=timeout,
        **kwargs,
    )


def request(method: str, path: str, **kwargs: Any) -> httpx.Response:
    try:
        resp = _httpx_request(method, path, **kwargs)
        resp.raise_for_status()
        return resp
    except httpx.ConnectError:
        console.print("Daemon is not running. Start it with `nina daemon start` or `make dev`.")
        raise typer.Exit(1) from None
    except httpx.HTTPStatusError as exc:
        console.print(f"Request failed ({exc.response.status_code}): {_error_detail(exc.response)}")
        raise typer.Exit(1) from None


def request_json(method: str, path: str, **kwargs: Any) -> Any:
    return request(method, path, **kwargs).json()


def try_request(method: str, path: str, **kwargs: Any) -> httpx.Response | None:
    try:
        resp = _httpx_request(method, path, **kwargs)
        resp.raise_for_status()
        return resp
    except httpx.HTTPError:
        return None


def try_request_json(method: str, path: str, **kwargs: Any) -> Any | None:
    response = try_request(method, path, **kwargs)
    if response is None:
        return None
    try:
        return response.json()
    except (ValueError, TypeError):
        return None
