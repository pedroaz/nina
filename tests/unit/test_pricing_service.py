from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from nina_core.pricing import PricingService

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "pricing"
CLAUDE_URL = "https://platform.claude.com/docs/en/about-claude/pricing"
OPENAI_URL = "https://platform.openai.com/docs/pricing"


def _fixture_response(request: httpx.Request) -> httpx.Response:
    if str(request.url) == CLAUDE_URL:
        return httpx.Response(200, text=(FIXTURES / "claude.html").read_text())
    if str(request.url) == OPENAI_URL:
        return httpx.Response(200, text=(FIXTURES / "openai.html").read_text())
    return httpx.Response(404, text="not found")


def test_refresh_fetches_and_writes_cache(tmp_path: Path) -> None:
    service = PricingService(tmp_path)
    transport = httpx.MockTransport(_fixture_response)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "nina_core.pricing.fetcher._client_factory",
            _patched_client_factory(transport),
        )
        refreshed = service.refresh()

    assert [p.provider for p in refreshed] == ["claude", "openai"]
    cache = json.loads((tmp_path / "provider_pricing.json").read_text())
    assert set(cache["providers"].keys()) == {"claude", "openai"}


def test_get_returns_none_for_missing_provider(tmp_path: Path) -> None:
    service = PricingService(tmp_path)
    assert service.get("claude") is None


def test_get_all_returns_empty_when_cache_missing(tmp_path: Path) -> None:
    service = PricingService(tmp_path)
    assert service.get_all() == []


def test_refresh_unknown_provider_raises(tmp_path: Path) -> None:
    service = PricingService(tmp_path)
    with pytest.raises(KeyError):
        service.refresh("bogus")


def test_default_config_dir_when_unset(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NINA_CONFIG_DIR", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    service = PricingService()
    assert service.config_dir == tmp_path / ".nina" / "default"


def test_source_override_skips_network(tmp_path: Path) -> None:
    service = PricingService(tmp_path)
    refreshed = service.refresh(
        "claude",
        source=f"claude:{FIXTURES / 'claude.html'}",
    )
    assert refreshed[0].provider == "claude"
    assert refreshed[0].models


def test_source_override_for_wrong_provider_is_ignored(tmp_path: Path) -> None:
    service = PricingService(tmp_path)
    transport = httpx.MockTransport(_fixture_response)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "nina_core.pricing.fetcher._client_factory",
            _patched_client_factory(transport),
        )
        refreshed = service.refresh("openai", source=f"claude:{FIXTURES / 'claude.html'}")
    assert refreshed[0].provider == "openai"
    assert any(m.model.startswith("gpt-") for m in refreshed[0].models)


def _patched_client_factory(transport: httpx.MockTransport):
    def _factory(**kwargs: object) -> httpx.Client:
        kwargs.pop("transport", None)
        return httpx.Client(transport=transport, **kwargs)

    return _factory
