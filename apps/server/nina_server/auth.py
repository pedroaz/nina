from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from nina_core.config import get_token_path, read_token


def _expected_token(request: Request) -> str:
    token = getattr(request.app.state, "token", None)
    if isinstance(token, str) and token:
        return token

    config_dir = getattr(request.app.state, "config_dir", None)
    if config_dir is not None:
        token_path = get_token_path(Path(config_dir))
        if token_path.exists():
            try:
                return read_token(token_path)
            except Exception:  # noqa: BLE001
                pass

    return os.environ.get("NINA_TOKEN", "")


class TokenAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Any) -> Any:
        if request.url.path == "/health":
            return await call_next(request)
        auth = request.headers.get("Authorization", "")
        expected = f"Bearer {_expected_token(request)}"
        if auth != expected:
            return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
        return await call_next(request)
