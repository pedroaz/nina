from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .models import ModelPricing
from .parsers import parse_claude, parse_openai


@dataclass(frozen=True)
class ProviderSpec:
    key: str
    label: str
    url: str
    parser: Callable[[str], list[ModelPricing]]


PROVIDERS: dict[str, ProviderSpec] = {
    "claude": ProviderSpec(
        key="claude",
        label="Anthropic",
        url="https://platform.claude.com/docs/en/about-claude/pricing",
        parser=parse_claude,
    ),
    "openai": ProviderSpec(
        key="openai",
        label="OpenAI",
        url="https://platform.openai.com/docs/pricing",
        parser=parse_openai,
    ),
}


def available_providers() -> list[str]:
    return list(PROVIDERS.keys())


def normalize_provider_name(name: str) -> str:
    cleaned = name.strip().lower()
    if cleaned in {"claude", "anthropic"}:
        return "claude"
    if cleaned in {"openai", "chatgpt"}:
        return "openai"
    return cleaned


def get_provider(name: str) -> ProviderSpec:
    key = normalize_provider_name(name)
    if key not in PROVIDERS:
        raise KeyError(f"Unknown provider '{name}'. Available: {', '.join(available_providers())}")
    return PROVIDERS[key]
