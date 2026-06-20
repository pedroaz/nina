"""Async HTTP client for the opencode server.

Thin wrapper around `httpx.AsyncClient` that handles basic auth, timeouts,
and turns non-2xx responses into `OpencodeError`. The daemon is the only
caller; the TUI and CLI go through the daemon's `/opencode/*` endpoints
so the bearer-token boundary is preserved.
"""

from __future__ import annotations

import base64
from typing import Any

import httpx

from .models import Health, Project


class OpencodeError(RuntimeError):
    """Raised for any opencode HTTP failure.

    The daemon's `/opencode/*` endpoints translate this into a 502/503
    response so the client can show a sensible error.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        body: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


def _basic_auth_header(username: str, password: str) -> str:
    raw = f"{username}:{password}".encode("utf-8")
    encoded = base64.b64encode(raw).decode("ascii")
    return f"Basic {encoded}"


class OpencodeClient:
    """Async HTTP client for one opencode server.

    A new instance is cheap. The supervisor holds one for its lifetime
    and the request handlers create short-lived ones when needed.
    """

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        *,
        timeout: float = 5.0,
    ) -> None:
        self._base_url = f"http://{host}:{port}"
        self._auth = _basic_auth_header(username, password)
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    @property
    def base_url(self) -> str:
        return self._base_url

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers={"Authorization": self._auth},
                timeout=self._timeout,
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "OpencodeClient":
        await self._get_client()
        return self

    async def __aexit__(self, *_exc: Any) -> None:
        await self.aclose()

    async def _request(self, method: str, path: str) -> Any:
        try:
            client = await self._get_client()
            response = await client.request(method, path)
        except httpx.HTTPError as exc:
            raise OpencodeError(f"opencode request failed: {exc}") from exc
        if response.status_code in (401, 403):
            raise OpencodeError(
                "opencode authentication failed",
                status_code=response.status_code,
                body=response.text,
            )
        if not response.is_success:
            raise OpencodeError(
                f"opencode returned HTTP {response.status_code}",
                status_code=response.status_code,
                body=response.text,
            )
        return response.json()

    async def health(self) -> Health:
        data = await self._request("GET", "/global/health")
        return Health.model_validate(data)

    async def list_projects(self) -> list[Project]:
        data = await self._request("GET", "/project")
        if not isinstance(data, list):
            raise OpencodeError(
                "opencode /project did not return a list",
                body=str(data)[:200],
            )
        return [Project.model_validate(item) for item in data]  # type: ignore[arg-type]

    async def current_project(self) -> Project:
        data = await self._request("GET", "/project/current")
        if not isinstance(data, dict):
            raise OpencodeError(
                "opencode /project/current did not return an object",
                body=str(data)[:200],
            )
        return Project.model_validate(data)
