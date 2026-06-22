from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from nina_core.models.models import IntegrationTest  # type: ignore[reportMissingTypeStubs]

from .base import IdentityResult, Integration, IntegrationStatus, TestResult
from .credentials import load_credentials
from .registry import list_integrations


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _test_id() -> str:
    return "it_" + uuid.uuid4().hex[:24]


def _configured_fields_for(integration: Integration, config_dir: Path | None) -> dict[str, bool]:
    credentials_key = str(getattr(integration, "credentials_key", "") or "")
    if not credentials_key:
        return {}
    creds = load_credentials(credentials_key, config_dir=config_dir) or {}
    return {str(key): bool(value) for key, value in creds.items()}


def _is_configured_for(integration: Integration, config_dir: Path | None) -> bool:
    checker = getattr(integration, "is_configured_for", None)
    if callable(checker):
        return bool(checker(config_dir))
    return integration.is_configured()


async def _test_for(integration: Integration, config_dir: Path | None) -> TestResult:
    tester = getattr(integration, "test_with_config_dir", None)
    if callable(tester):
        return await tester(config_dir)
    return await integration.test()


def _integration_to_dict(
    integration: Integration, last: TestResult | None, config_dir: Path | None = None
) -> dict[str, Any]:
    info = integration.info
    configured = _is_configured_for(integration, config_dir)
    payload: dict[str, Any] = {
        "name": info.name,
        "display_name": info.display_name,
        "description": info.description,
        "docs_url": info.docs_url,
        "auth_style": info.auth_style,
        "credential_fields": [field.to_dict() for field in info.credential_fields],
        "configured_fields": _configured_fields_for(integration, config_dir),
        "configured": configured,
        "status": (
            IntegrationStatus.NOT_CONFIGURED.value
            if not configured
            else (last.status.value if last else IntegrationStatus.NOT_CONFIGURED.value)
        ),
    }
    if last is not None:
        payload["last_test"] = last.to_dict()
    else:
        payload["last_test"] = None
    return payload


class IntegrationService:
    """Service layer for integration lifecycle: list/get/test/persist.

    Construct one per request inside the daemon (or reuse for the lifetime of
    a CLI command). The service is intentionally thin: registry iteration +
    SQLite persistence. The HTTP shape is owned by `nina_server.app`.
    """

    def __init__(self, db_path: str | Path, config_dir: Path | None = None) -> None:
        self.db_path = str(db_path)
        self.config_dir = Path(config_dir) if config_dir is not None else None
        self.engine = create_engine(f"sqlite:///{self.db_path}", echo=False)
        self.SessionLocal = sessionmaker(bind=self.engine)

    def _session(self):
        return self.SessionLocal()

    def list(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for integration in list_integrations():
            last = self._latest_test(integration.info.name)
            result.append(_integration_to_dict(integration, last, self.config_dir))
        return result

    def get(self, name: str) -> dict[str, Any] | None:
        for integration in list_integrations():
            if integration.info.name == name:
                return _integration_to_dict(integration, self._latest_test(name), self.config_dir)
        return None

    async def test(self, name: str) -> dict[str, Any]:
        from .registry import get_integration

        integration = get_integration(name)
        if integration is None:
            raise KeyError(name)
        if not _is_configured_for(integration, self.config_dir):
            result = TestResult(
                status=IntegrationStatus.NOT_CONFIGURED,
                latency_ms=0,
                identity=None,
                error="integration is not configured",
                tested_at=_now(),
            )
        else:
            try:
                result = await _test_for(integration, self.config_dir)
            except Exception as exc:  # noqa: BLE001 - we want any error captured here
                result = TestResult(
                    status=IntegrationStatus.FAILED,
                    latency_ms=0,
                    identity=None,
                    error=f"{type(exc).__name__}: {exc}",
                    tested_at=_now(),
                )
        self._persist_test(name, result)
        return result.to_dict()

    def list_tests(self, name: str, limit: int = 10) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 100))
        db = self._session()
        try:
            rows = (
                db.query(IntegrationTest)
                .filter(IntegrationTest.integration_name == name)
                .order_by(IntegrationTest.created_at.desc())
                .limit(limit)
                .all()
            )
        finally:
            db.close()
        return [self._row_to_dict(row) for row in rows]

    def _latest_test(self, name: str) -> TestResult | None:
        db = self._session()
        try:
            row = (
                db.query(IntegrationTest)
                .filter(IntegrationTest.integration_name == name)
                .order_by(IntegrationTest.created_at.desc())
                .first()
            )
        finally:
            db.close()
        if row is None:
            return None
        return self._row_to_result(row)

    def _persist_test(self, name: str, result: TestResult) -> None:
        db = self._session()
        try:
            row = IntegrationTest(
                id=_test_id(),
                integration_name=name,
                status=result.status.value,
                latency_ms=int(result.latency_ms),
                identity_json=(json.dumps(result.identity.to_dict()) if result.identity else None),
                error=result.error,
                created_at=result.tested_at,
            )
            db.add(row)
            db.commit()
        finally:
            db.close()

    def _row_to_result(self, row: IntegrationTest) -> TestResult:
        identity: IdentityResult | None = None
        if row.identity_json:
            try:
                data = json.loads(str(row.identity_json))
                identity = IdentityResult(
                    account_id=str(data.get("account_id", "")),
                    display_name=str(data.get("display_name", "")),
                    email=data.get("email"),
                    workspace=data.get("workspace"),
                )
            except (TypeError, ValueError):
                identity = None
        return TestResult(
            status=IntegrationStatus(str(row.status)),
            latency_ms=int(row.latency_ms or 0),  # type: ignore[arg-type]
            identity=identity,
            error=str(row.error) if bool(row.error) else None,  # type: ignore[arg-type]
            tested_at=str(row.created_at),
        )

    def _row_to_dict(self, row: IntegrationTest) -> dict[str, Any]:
        result = self._row_to_result(row)
        payload = result.to_dict()
        payload["id"] = row.id
        return payload
