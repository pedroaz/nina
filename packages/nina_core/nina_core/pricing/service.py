from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from nina_core.config import get_config_dir  # type: ignore[import-untyped]

from .cache import CACHE_VERSION, load_cache, save_cache
from .fetcher import fetch_html
from .models import ModelPricing, ProviderPricing
from .providers import PROVIDERS, available_providers, get_provider, normalize_provider_name


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class PricingService:
    """High-level entry point for the ``nina providers`` command."""

    def __init__(self, config_dir: Path | str | None = None) -> None:
        if config_dir is None:
            config_dir = get_config_dir()
        self.config_dir = Path(config_dir)

    def available(self) -> list[str]:
        return available_providers()

    def get(self, provider: str) -> ProviderPricing | None:
        cache = load_cache(self.config_dir)
        raw = cache.get("providers", {}).get(normalize_provider_name(provider))
        if not raw:
            return None
        return _provider_pricing_from_cache(raw)

    def get_all(self) -> list[ProviderPricing]:
        cache = load_cache(self.config_dir)
        out: list[ProviderPricing] = []
        for key in sorted(cache.get("providers", {}).keys()):
            out.append(_provider_pricing_from_cache(cache["providers"][key]))
        return out

    def refresh(
        self,
        provider: str | None = None,
        *,
        source: str | None = None,
    ) -> list[ProviderPricing]:
        keys = [normalize_provider_name(provider)] if provider else list(PROVIDERS.keys())
        refreshed: list[ProviderPricing] = []
        for key in keys:
            if key not in PROVIDERS:
                raise KeyError(
                    f"Unknown provider '{provider}'. Available: {', '.join(available_providers())}"
                )
            refreshed.append(self._refresh_one(key, source=source))
        return refreshed

    def _refresh_one(self, key: str, *, source: str | None) -> ProviderPricing:
        spec = get_provider(key)
        source_path = _resolve_source_override(source, key)
        html = fetch_html(spec.url, source_override=source_path)
        try:
            rows = spec.parser(html)
        except Exception as exc:
            raise RuntimeError(f"Failed to parse {spec.label} pricing page: {exc}") from exc
        pricing = ProviderPricing(
            provider=spec.key,
            label=spec.label,
            source_url=spec.url,
            fetched_at=_now(),
            models=rows,
        )
        cache = load_cache(self.config_dir)
        cache.setdefault("providers", {})[spec.key] = pricing.model_dump()
        save_cache(cache, self.config_dir)
        return pricing


def _resolve_source_override(source: str | None, key: str) -> str | None:
    if not source:
        return None
    if ":" in source:
        prefix, _, path = source.partition(":")
        if normalize_provider_name(prefix) == key:
            return path
        return None
    return source


def _provider_pricing_from_cache(raw: dict[str, Any]) -> ProviderPricing:
    models_raw = raw.get("models", [])
    models = [ModelPricing.model_validate(m) for m in models_raw]
    return ProviderPricing(
        provider=raw["provider"],
        label=raw.get("label", raw["provider"]),
        source_url=raw["source_url"],
        fetched_at=raw["fetched_at"],
        currency=raw.get("currency", "USD"),
        models=models,
    )


__all__ = ["PricingService", "CACHE_VERSION"]
