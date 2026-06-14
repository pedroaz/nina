from __future__ import annotations

import pytest
from nina_core.research.service import OpenAIWebResearchProvider


def test_openai_web_research_provider_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY is required"):
        OpenAIWebResearchProvider()
