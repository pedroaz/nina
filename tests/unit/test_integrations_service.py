from __future__ import annotations

import asyncio
from collections.abc import Iterator
from pathlib import Path

import pytest
from nina_core.db import create_database
from nina_core.integrations import (
    IntegrationService,
    register_integration,
    save_credentials,
)
from nina_core.integrations import registry as _registry
from nina_core.integrations.base import (
    IdentityResult,
    IntegrationInfo,
    IntegrationStatus,
    TestResult,
)
from nina_core.models.models import IntegrationTest  # type: ignore[reportMissingTypeStubs]


class _StaticIntegration:
    def __init__(self, name: str, *, configured: bool, result: TestResult | None) -> None:
        self.info = IntegrationInfo(
            name=name,
            display_name=name.title(),
            description="test",
            docs_url="",
            auth_style="bearer_bot",
        )
        self._configured = configured
        self._result = result

    def is_configured(self) -> bool:
        return self._configured

    async def test(self) -> TestResult:
        if self._result is None:
            raise RuntimeError("boom")
        return self._result


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "nina.db"
    create_database(str(path))
    return path


@pytest.fixture
def isolated_registry() -> Iterator[None]:
    snapshot = dict(_registry._INTEGRATIONS)
    _registry._INTEGRATIONS.clear()
    # Re-register the built-ins so service.list() still works for them.
    from nina_core.integrations import (
        ConfluenceIntegration,
        JiraIntegration,
        SlackIntegration,
        TeamsIntegration,
    )

    for integration in (
        ConfluenceIntegration(),
        JiraIntegration(),
        SlackIntegration(),
        TeamsIntegration(),
    ):
        register_integration(integration)
    yield
    _registry._INTEGRATIONS.clear()
    _registry._INTEGRATIONS.update(snapshot)


def test_service_lists_known_integrations(db_path: Path, isolated_registry: None) -> None:
    service = IntegrationService(str(db_path))
    names = {item["name"] for item in service.list()}
    assert {"confluence", "jira", "slack", "teams"}.issubset(names)


def test_service_marks_unconfigured_integrations(db_path: Path, isolated_registry: None) -> None:
    service = IntegrationService(str(db_path))
    for item in service.list():
        assert item["configured"] is False
        assert item["status"] == "not_configured"
        assert item["last_test"] is None


def test_service_persists_test_result(db_path: Path, isolated_registry: None) -> None:
    register_integration(
        _StaticIntegration(
            "acme",
            configured=True,
            result=TestResult(
                status=IntegrationStatus.OK,
                latency_ms=42,
                identity=IdentityResult(
                    account_id="acc-1",
                    display_name="Ada",
                    email="ada@example.com",
                    workspace="acme",
                ),
                error=None,
                tested_at="2026-01-01T00:00:00+00:00",
            ),
        )
    )
    service = IntegrationService(str(db_path))
    result = asyncio.run(service.test("acme"))
    assert result["status"] == "ok"
    listing = service.get("acme")
    assert listing is not None
    assert listing["status"] == "ok"
    assert listing["last_test"]["latency_ms"] == 42
    assert listing["last_test"]["identity"]["display_name"] == "Ada"


def test_service_records_not_configured_when_credentials_missing(
    db_path: Path, isolated_registry: None
) -> None:
    service = IntegrationService(str(db_path))
    result = asyncio.run(service.test("confluence"))
    assert result["status"] == "not_configured"
    history = service.list_tests("confluence", limit=5)
    assert len(history) == 1
    assert history[0]["status"] == "not_configured"


def test_service_captures_exceptions_in_test(db_path: Path, isolated_registry: None) -> None:
    register_integration(_StaticIntegration("flaky", configured=True, result=None))
    service = IntegrationService(str(db_path))
    result = asyncio.run(service.test("flaky"))
    assert result["status"] == "failed"
    assert "RuntimeError" in (result["error"] or "")


def test_service_returns_history_in_descending_order(
    db_path: Path, isolated_registry: None
) -> None:
    register_integration(
        _StaticIntegration(
            "acme",
            configured=True,
            result=TestResult(
                status=IntegrationStatus.OK,
                latency_ms=10,
                identity=IdentityResult(account_id="x", display_name="X"),
                error=None,
                tested_at="2026-01-01T00:00:00+00:00",
            ),
        )
    )
    service = IntegrationService(str(db_path))
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    session_local = sessionmaker(bind=engine)
    for offset in range(3):
        db = session_local()
        try:
            db.add(
                IntegrationTest(
                    id=f"it_{offset:08d}",
                    integration_name="acme",
                    status="ok",
                    latency_ms=offset,
                    identity_json=None,
                    error=None,
                    created_at=f"2026-01-0{offset + 1}T00:00:00+00:00",
                )
            )
            db.commit()
        finally:
            db.close()
    history = service.list_tests("acme", limit=10)
    assert [row["latency_ms"] for row in history] == [2, 1, 0]


def test_service_get_unknown_returns_none(db_path: Path, isolated_registry: None) -> None:
    service = IntegrationService(str(db_path))
    assert service.get("does-not-exist") is None


def test_configured_field_reflects_saved_credentials(
    tmp_path: Path, db_path: Path, isolated_registry: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    save_credentials(
        "confluence",
        {
            "base_url": "https://example.atlassian.net",
            "email": "a@b",
            "api_token": "tok",
        },
        config_dir=tmp_path,
    )
    # The integration class calls `load_credentials` from inside `_load_creds`
    # via a deferred import. Patch the canonical function in the credentials
    # module so the call dispatches against the temporary config dir.
    import nina_core.integrations.credentials as creds_mod

    real_loader = creds_mod.load_credentials

    def loader(name, config_dir=None):  # type: ignore[no-untyped-def]
        return real_loader(name, config_dir=tmp_path)

    monkeypatch.setattr(creds_mod, "load_credentials", loader)
    service = IntegrationService(str(db_path))
    item = service.get("confluence")
    assert item is not None
    assert item["configured"] is True
