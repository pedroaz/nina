"""Unit tests for the async opencode HTTP client."""

from __future__ import annotations

import base64
from typing import Any

import httpx
import pytest
from nina_core.opencode.client import OpencodeClient, OpencodeError


class _FakeAsyncTransport(httpx.AsyncBaseTransport):
    """Minimal async transport for `httpx.AsyncClient`."""

    def __init__(self, handler) -> None:
        self._handler = handler
        self.requests: list[httpx.Request] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self._handler(request)


def _auth_header(username: str, password: str) -> str:
    raw = f"{username}:{password}".encode()
    return "Basic " + base64.b64encode(raw).decode("ascii")


@pytest.mark.asyncio
async def test_health_sends_basic_auth_and_parses_payload() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers.get("Authorization")
        captured["path"] = request.url.path
        return httpx.Response(200, json={"healthy": True, "version": "1.17.8"})

    transport = _FakeAsyncTransport(handler)
    client = OpencodeClient("127.0.0.1", 5555, "nina", "secret")
    client._client = httpx.AsyncClient(  # type: ignore[attr-defined]
        base_url=client.base_url,
        transport=transport,
        headers={"Authorization": client._auth},  # type: ignore[attr-defined]
    )
    try:
        health = await client.health()
    finally:
        await client.aclose()

    assert captured["auth"] == _auth_header("nina", "secret")
    assert captured["path"] == "/global/health"
    assert health.healthy is True
    assert health.version == "1.17.8"


@pytest.mark.asyncio
async def test_list_projects_parses_list() -> None:
    payload = [
        {
            "id": "abc123",
            "worktree": "/home/u/proj",
            "vcs": "git",
            "time": {"created": 1700000000000, "updated": 1700000001000},
            "sandboxes": [],
        }
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    transport = _FakeAsyncTransport(handler)
    client = OpencodeClient("127.0.0.1", 5555, "nina", "secret")
    client._client = httpx.AsyncClient(  # type: ignore[attr-defined]
        base_url=client.base_url, transport=transport
    )
    try:
        projects = await client.list_projects()
    finally:
        await client.aclose()

    assert len(projects) == 1
    assert projects[0].id == "abc123"
    assert projects[0].worktree == "/home/u/proj"
    assert projects[0].vcs == "git"
    assert projects[0].time.created == 1700000000000


@pytest.mark.asyncio
async def test_401_raises_typed_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="unauthorized")

    transport = _FakeAsyncTransport(handler)
    client = OpencodeClient("127.0.0.1", 5555, "nina", "wrong")
    client._client = httpx.AsyncClient(  # type: ignore[attr-defined]
        base_url=client.base_url, transport=transport
    )
    try:
        with pytest.raises(OpencodeError) as exc:
            await client.health()
    finally:
        await client.aclose()
    assert exc.value.status_code == 401
    assert "authentication" in str(exc.value).lower()


@pytest.mark.asyncio
async def test_500_raises_typed_error_with_body() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    transport = _FakeAsyncTransport(handler)
    client = OpencodeClient("127.0.0.1", 5555, "nina", "secret")
    client._client = httpx.AsyncClient(  # type: ignore[attr-defined]
        base_url=client.base_url, transport=transport
    )
    try:
        with pytest.raises(OpencodeError) as exc:
            await client.list_projects()
    finally:
        await client.aclose()
    assert exc.value.status_code == 500
    assert exc.value.body == "boom"


@pytest.mark.asyncio
async def test_current_project_parses_object() -> None:
    payload = {
        "id": "current-id",
        "worktree": "/tmp/now",
        "vcs": None,
        "time": {"created": None, "updated": None},
        "sandboxes": [],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    transport = _FakeAsyncTransport(handler)
    client = OpencodeClient("127.0.0.1", 5555, "nina", "secret")
    client._client = httpx.AsyncClient(  # type: ignore[attr-defined]
        base_url=client.base_url, transport=transport
    )
    try:
        project = await client.current_project()
    finally:
        await client.aclose()
    assert project.id == "current-id"
    assert project.worktree == "/tmp/now"
    assert project.vcs is None
