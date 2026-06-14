from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ModelPricing(BaseModel):
    model: str
    input_per_1m_tokens: float | None = None
    output_per_1m_tokens: float | None = None
    cache_read_per_1m_tokens: float | None = None
    cache_write_per_1m_tokens: float | None = None
    notes: str = ""
    raw: dict[str, Any] = Field(default_factory=dict)


class ProviderPricing(BaseModel):
    provider: str
    label: str
    source_url: str
    fetched_at: str
    currency: str = "USD"
    models: list[ModelPricing] = Field(default_factory=list[ModelPricing])
