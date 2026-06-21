from __future__ import annotations

import json
from types import SimpleNamespace

from nina_core.config.settings import ResearchConfig
from nina_core.research.service import CodexCliResearchProvider, ResearchService


def test_codex_research_provider_parses_report(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    async def fake_exec(self, prompt: str, **kwargs: object) -> object:
        assert "local Codex CLI" in prompt
        payload = {
            "summary": "Codex summary.",
            "sources": [{"title": "Docs", "url": "https://example.com/docs"}],
        }
        return SimpleNamespace(stdout=json.dumps(payload), last_message=json.dumps(payload))

    monkeypatch.setattr("nina_core.codex.client.CodexClient.exec", fake_exec)

    report = CodexCliResearchProvider().research("Codex tasks")

    assert report.topic == "Codex tasks"
    assert report.summary == "Codex summary."
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
