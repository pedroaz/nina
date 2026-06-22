from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from .base import IdentityResult, IntegrationInfo, IntegrationStatus, TestResult


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class NotConfiguredIntegration:
    """Base class for integrations that require credentials.

    Subclasses implement `_resolve_identity(creds)` and override
    `auth_style`. The shared `test()` flow measures latency, calls
    `_resolve_identity`, and packages the result.
    """

    info: IntegrationInfo
    credentials_key: str = ""

    def _load_creds(self, config_dir: Path | None = None) -> dict[str, Any] | None:
        from .credentials import load_credentials

        if not self.credentials_key:
            return None
        return load_credentials(self.credentials_key, config_dir=config_dir)

    def is_configured(self) -> bool:
        return self.is_configured_for()

    def is_configured_for(self, config_dir: Path | None = None) -> bool:
        creds = self._load_creds(config_dir)
        if not creds:
            return False
        return all(bool(creds.get(field)) for field in self._required_fields())

    def _required_fields(self) -> tuple[str, ...]:
        return ()

    async def test(self) -> TestResult:
        return await self.test_with_config_dir()

    async def test_with_config_dir(self, config_dir: Path | None = None) -> TestResult:
        creds = self._load_creds(config_dir) or {}
        if not self.is_configured_for(config_dir):
            return TestResult(
                status=IntegrationStatus.NOT_CONFIGURED,
                latency_ms=0,
                identity=None,
                error="integration is not configured",
                tested_at=_now(),
            )
        start = datetime.now(timezone.utc)
        try:
            identity = await self._resolve_identity(creds)
        except httpx.HTTPStatusError as exc:
            latency = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
            return TestResult(
                status=IntegrationStatus.FAILED,
                latency_ms=latency,
                identity=None,
                error=f"HTTP {exc.response.status_code}: {exc.response.text[:200]}",
                tested_at=_now(),
            )
        except httpx.HTTPError as exc:
            latency = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
            return TestResult(
                status=IntegrationStatus.FAILED,
                latency_ms=latency,
                identity=None,
                error=f"transport error: {exc}",
                tested_at=_now(),
            )
        latency = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
        return TestResult(
            status=IntegrationStatus.OK,
            latency_ms=latency,
            identity=identity,
            error=None,
            tested_at=_now(),
        )

    async def _resolve_identity(self, creds: dict[str, Any]) -> IdentityResult:
        raise NotImplementedError
