from __future__ import annotations

import json
from pathlib import Path

import pytest
from nina_core.pricing import ModelPricing, ProviderPricing, load_cache, save_cache

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "pricing"


def test_model_pricing_defaults() -> None:
    model = ModelPricing(model="gpt-test")
    assert model.input_per_1m_tokens is None
    assert model.output_per_1m_tokens is None
    assert model.notes == ""
    assert model.raw == {}


def test_model_pricing_round_trip() -> None:
    model = ModelPricing(
        model="gpt-test",
        input_per_1m_tokens=1.25,
        output_per_1m_tokens=10.0,
        cache_read_per_1m_tokens=0.125,
    )
    blob = model.model_dump()
    again = ModelPricing.model_validate(blob)
    assert again == model


def test_provider_pricing_default_currency() -> None:
    pricing = ProviderPricing(
        provider="claude",
        label="Anthropic",
        source_url="https://example.com",
        fetched_at="2026-06-14T00:00:00+00:00",
        models=[
            ModelPricing(
                model="Claude Sonnet 4", input_per_1m_tokens=3.0, output_per_1m_tokens=15.0
            )
        ],
    )
    assert pricing.currency == "USD"
    assert pricing.models[0].input_per_1m_tokens == 3.0


def test_load_cache_missing_file(tmp_path: Path) -> None:
    payload = load_cache(tmp_path)
    assert payload == {"version": 1, "providers": {}}


def test_load_cache_corrupt_file(tmp_path: Path) -> None:
    (tmp_path / "provider_pricing.json").write_text("not-json")
    payload = load_cache(tmp_path)
    assert payload["providers"] == {}


def test_save_and_load_cache_round_trip(tmp_path: Path) -> None:
    pricing = ProviderPricing(
        provider="claude",
        label="Anthropic",
        source_url="https://example.com",
        fetched_at="2026-06-14T00:00:00+00:00",
        models=[ModelPricing(model="Claude Sonnet 4", input_per_1m_tokens=3.0)],
    )
    payload = {
        "version": 1,
        "providers": {"claude": pricing.model_dump()},
    }
    target = save_cache(payload, tmp_path)
    assert target.exists()
    loaded = load_cache(tmp_path)
    assert loaded["providers"]["claude"]["models"][0]["model"] == "Claude Sonnet 4"
    assert json.loads(target.read_text()) == payload


def test_save_cache_uses_nina_config_dir_when_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NINA_CONFIG_DIR", str(tmp_path))
    pricing = ProviderPricing(
        provider="openai",
        label="OpenAI",
        source_url="https://example.com",
        fetched_at="2026-06-14T00:00:00+00:00",
        models=[ModelPricing(model="gpt-5", input_per_1m_tokens=1.25, output_per_1m_tokens=10.0)],
    )
    save_cache({"version": 1, "providers": {"openai": pricing.model_dump()}})
    assert (tmp_path / "provider_pricing.json").exists()
