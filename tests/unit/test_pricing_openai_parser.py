from __future__ import annotations

from pathlib import Path

import pytest
from nina_core.pricing.parsers import PricingParseError, parse_openai

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "pricing"


@pytest.fixture
def openai_html() -> str:
    return (FIXTURES / "openai.html").read_text(encoding="utf-8")


def test_parse_openai_extracts_flight_payload(openai_html: str) -> None:
    models = parse_openai(openai_html)
    by_name = {m.model: m for m in models}
    assert "gpt-5" in by_name
    gpt5 = by_name["gpt-5"]
    assert gpt5.input_per_1m_tokens == 1.25
    assert gpt5.output_per_1m_tokens == 10.0
    assert gpt5.cache_read_per_1m_tokens == 0.125


def test_parse_openai_includes_mini_variants(openai_html: str) -> None:
    names = {m.model for m in parse_openai(openai_html)}
    assert "gpt-5-mini" in names
    assert "gpt-4.1" in names
    assert "o3" in names


def test_parse_openai_falls_back_to_table_dom() -> None:
    # Page without the Flight payload, but with a recognizable pricing table.
    html = """
    <html><body>
      <table>
        <thead><tr><th>Model</th><th>Input</th><th>Cached input</th><th>Output</th></tr></thead>
        <tbody>
          <tr><td>fine-tune-gpt-4o</td><td>$3.75</td><td>$0.375</td><td>$15.00</td></tr>
        </tbody>
      </table>
    </body></html>
    """
    models = parse_openai(html)
    assert len(models) == 1
    assert models[0].model == "fine-tune-gpt-4o"
    assert models[0].input_per_1m_tokens == 3.75
    assert models[0].output_per_1m_tokens == 15.0
    assert models[0].cache_read_per_1m_tokens == 0.375


def test_parse_openai_raises_on_unrecognized_structure() -> None:
    with pytest.raises(PricingParseError):
        parse_openai("<html><body>nothing recognizable</body></html>")


def test_parse_openai_dedupes_models(openai_html: str) -> None:
    models = parse_openai(openai_html)
    names = [m.model for m in models]
    assert len(names) == len(set(names))
