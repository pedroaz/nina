from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from nina_cli.main import app
from nina_core.pricing import PricingService
from typer.testing import CliRunner

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "pricing"
CLAUDE_URL = "https://platform.claude.com/docs/en/about-claude/pricing"
OPENAI_URL = "https://platform.openai.com/docs/pricing"


runner = CliRunner()


def _mock_transport(request: httpx.Request) -> httpx.Response:
    if str(request.url) == CLAUDE_URL:
        return httpx.Response(200, text=(FIXTURES / "claude.html").read_text())
    if str(request.url) == OPENAI_URL:
        return httpx.Response(200, text=(FIXTURES / "openai.html").read_text())
    return httpx.Response(404, text="not found")


def _patched_client_factory(transport: httpx.MockTransport):
    def _factory(**kwargs: object) -> httpx.Client:
        kwargs.pop("transport", None)
        return httpx.Client(transport=transport, **kwargs)

    return _factory


@pytest.fixture
def primed_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> PricingService:
    service = PricingService(tmp_path)
    transport = httpx.MockTransport(_mock_transport)
    with monkeypatch.context() as mp:
        mp.setattr(
            "nina_core.pricing.fetcher._client_factory",
            _patched_client_factory(transport),
        )
        service.refresh()
    return service


def test_providers_lists_cached_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, primed_config: PricingService
) -> None:
    monkeypatch.setenv("NINA_CONFIG_DIR", str(tmp_path))
    result = runner.invoke(app, ["providers", "--json"])
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    providers = {entry["provider"]: entry for entry in payload}
    assert "claude" in providers
    assert "openai" in providers
    assert any(m["model"] == "gpt-5" for m in providers["openai"]["models"])


def test_providers_filters_by_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, primed_config: PricingService
) -> None:
    monkeypatch.setenv("NINA_CONFIG_DIR", str(tmp_path))
    result = runner.invoke(app, ["providers", "show", "gpt-5", "--json"])
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert len(payload) == 1
    assert payload[0]["provider"] == "openai"
    models = [m["model"] for m in payload[0]["models"]]
    assert any("gpt-5" in m for m in models)


def test_providers_show_unknown_exits_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, primed_config: PricingService
) -> None:
    monkeypatch.setenv("NINA_CONFIG_DIR", str(tmp_path))
    result = runner.invoke(app, ["providers", "show", "no-such-model"])
    assert result.exit_code == 1
    assert "No models match" in result.stdout


def test_providers_empty_cache_hint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NINA_CONFIG_DIR", str(tmp_path))
    result = runner.invoke(app, ["providers"])
    assert result.exit_code == 0
    assert "nina providers refresh" in result.stdout


def test_providers_refresh_writes_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NINA_CONFIG_DIR", str(tmp_path))
    transport = httpx.MockTransport(_mock_transport)
    with monkeypatch.context() as mp:
        mp.setattr(
            "nina_core.pricing.fetcher._client_factory",
            _patched_client_factory(transport),
        )
        result = runner.invoke(app, ["providers", "refresh"])
    assert result.exit_code == 0, result.stdout
    assert (tmp_path / "provider_pricing.json").exists()
    assert "Anthropic" in result.stdout
    assert "OpenAI" in result.stdout


def test_providers_refresh_with_source_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NINA_CONFIG_DIR", str(tmp_path))
    result = runner.invoke(
        app,
        [
            "providers",
            "refresh",
            "--provider",
            "claude",
            "--source",
            f"claude:{FIXTURES / 'claude.html'}",
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert (tmp_path / "provider_pricing.json").exists()


def test_providers_filters_by_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, primed_config: PricingService
) -> None:
    monkeypatch.setenv("NINA_CONFIG_DIR", str(tmp_path))
    result = runner.invoke(app, ["providers", "--provider", "claude", "--json"])
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert len(payload) == 1
    assert payload[0]["provider"] == "claude"


def test_providers_highlights_configured_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, primed_config: PricingService
) -> None:
    from nina_core.config import NinaConfig

    config_path = tmp_path / "config.yaml"
    config = NinaConfig(llm={"provider": "openai", "model": "gpt-5"})
    config.save(config_path)
    monkeypatch.setenv("NINA_CONFIG_DIR", str(tmp_path))
    result = runner.invoke(app, ["providers", "--provider", "openai", "--model", "gpt-5"])
    assert result.exit_code == 0, result.stdout
    # Highlight is rendered via Rich style tags; ensure the table rendered and shows the model.
    assert "gpt-5" in result.stdout


def test_providers_runs_without_nina_config_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`nina providers` should work when NINA_CONFIG_DIR is not exported."""

    monkeypatch.delenv("NINA_CONFIG_DIR", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    default_dir = tmp_path / ".nina" / "default"
    default_dir.mkdir(parents=True)

    service = PricingService()  # resolves to the default config dir
    transport = httpx.MockTransport(_mock_transport)
    with monkeypatch.context() as mp:
        mp.setattr(
            "nina_core.pricing.fetcher._client_factory",
            _patched_client_factory(transport),
        )
        service.refresh()
    assert (default_dir / "provider_pricing.json").exists()

    # And the CLI should resolve the same default path and read the cache.
    result = runner.invoke(app, ["providers", "--json"])
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert {entry["provider"] for entry in payload} == {"claude", "openai"}
