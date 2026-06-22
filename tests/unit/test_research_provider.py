from __future__ import annotations

import json
from types import SimpleNamespace

from nina_core.config.settings import ResearchConfig
from nina_core.research.service import CodexCliResearchProvider, ResearchService


def test_codex_research_provider_parses_report(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    async def fake_exec(self, prompt: str, **kwargs: object) -> object:
        assert "local Codex CLI" in prompt
        assert kwargs["web_search"] == "live"
        assert kwargs["model"] is None
        assert kwargs["timeout"] == 240.0
        output_schema = kwargs["output_schema"]
        assert output_schema is not None
        assert output_schema.exists()  # type: ignore[attr-defined]
        payload = {
            "summary": "Codex summary.",
            "sources": [
                {"title": "Docs", "url": "https://example.com/docs"},
                {"title": "Duplicate", "url": "https://example.com/docs"},
                {"title": "Bad", "url": "ftp://example.com/file"},
                {"title": "No host", "url": "https:///missing"},
            ],
        }
        return SimpleNamespace(stdout=json.dumps(payload), last_message=json.dumps(payload))

    monkeypatch.setattr("nina_core.codex.client.CodexClient.exec", fake_exec)

    report = CodexCliResearchProvider().research("Codex tasks")

    assert report.topic == "Codex tasks"
    assert report.summary == "Codex summary."
    assert report.provider == "codex"
    assert report.model == "codex-cli"
    assert report.search_mode == "live"
    assert len(report.sources) == 1
    assert report.sources[0].title == "Docs"
    assert report.sources[0].url == "https://example.com/docs"


def test_research_service_passes_configured_codex_binary_path(tmp_path) -> None:  # type: ignore[no-untyped-def]
    service = ResearchService(
        str(tmp_path / "nina.db"),
        str(tmp_path / "vault"),
        config=ResearchConfig(provider="codex"),
        codex_binary_path="/opt/codex",
    )

    assert isinstance(service.provider, CodexCliResearchProvider)
    assert service.provider.client.binary_path == "/opt/codex"


def test_research_service_passes_configured_codex_options(tmp_path) -> None:  # type: ignore[no-untyped-def]
    service = ResearchService(
        str(tmp_path / "nina.db"),
        str(tmp_path / "vault"),
        config=ResearchConfig(
            provider="codex",
            model="gpt-5.5",
            search_mode="cached",
            timeout_seconds=42.0,
        ),
        codex_binary_path="/opt/codex",
    )

    assert isinstance(service.provider, CodexCliResearchProvider)
    assert service.provider.model == "gpt-5.5"
    assert service.provider.search_mode == "cached"
    assert service.provider.timeout == 42.0
