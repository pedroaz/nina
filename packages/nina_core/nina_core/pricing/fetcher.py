from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import httpx


_USER_AGENT = "nina/0.1 (+https://github.com/anomalyco/codex)"

DEFAULT_TIMEOUT_SECONDS = 20.0


def _default_client_factory(**kwargs: Any) -> httpx.Client:
    return httpx.Client(**kwargs)


_client_factory: Callable[..., httpx.Client] = _default_client_factory


def fetch_html(url: str, *, source_override: str | None = None) -> str:
    """Fetch the pricing page as HTML.

    If ``source_override`` is provided, read from that local file path
    instead of hitting the network. The override is mainly useful for
    testing and for environments where the live page is unreachable.
    """

    if source_override:
        return Path(source_override).read_text(encoding="utf-8")

    with _client_factory(
        follow_redirects=True,
        timeout=DEFAULT_TIMEOUT_SECONDS,
        headers={"User-Agent": _USER_AGENT, "Accept": "text/html,*/*"},
    ) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.text
