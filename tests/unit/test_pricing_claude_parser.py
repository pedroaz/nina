from __future__ import annotations

from pathlib import Path

import pytest
from nina_core.pricing.parsers import PricingParseError, parse_claude

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "pricing"


@pytest.fixture
def claude_html() -> str:
    return (FIXTURES / "claude.html").read_text(encoding="utf-8")


def test_parse_claude_extracts_main_table(claude_html: str) -> None:
    models = parse_claude(claude_html)
    names = [m.model for m in models]
    assert "Claude Sonnet 4" in names
    assert "Claude Opus 4.8" in names
    assert "Claude Haiku 4.5" in names


def test_parse_claude_parses_dollar_values(claude_html: str) -> None:
    models = {m.model: m for m in parse_claude(claude_html)}
    sonnet = models["Claude Sonnet 4"]
    assert sonnet.input_per_1m_tokens == 3.0
    assert sonnet.output_per_1m_tokens == 15.0
    assert sonnet.cache_read_per_1m_tokens == 0.3


def test_parse_claude_extracts_cache_write_column(claude_html: str) -> None:
    models = {m.model: m for m in parse_claude(claude_html)}
    opus = models["Claude Opus 4.8"]
    assert opus.cache_write_per_1m_tokens == 6.25


def test_parse_claude_raises_on_empty() -> None:
    with pytest.raises(PricingParseError):
        parse_claude("<html><body>no tables here</body></html>")
