from __future__ import annotations

import re
from typing import Any, Iterable

from selectolax.parser import HTMLParser, Node

from .models import ModelPricing


class PricingParseError(RuntimeError):
    """Raised when a pricing page cannot be parsed."""


_DOLLARS_RE = re.compile(
    r"\$\s*(?P<value>\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:/\s*(?:MTok|M\s*tokens?|1M|million))?",
    re.IGNORECASE,
)


def _clean_text(node: Node | None) -> str:
    if node is None:
        return ""
    text = node.text(separator=" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()


def _clean_model_name(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    cleaned = re.sub(r"\s*\(.*?\)\s*$", "", cleaned)
    return cleaned.strip()


def _parse_dollars(cell_text: str) -> float | None:
    if not cell_text:
        return None
    match = _DOLLARS_RE.search(cell_text)
    if not match:
        return None
    try:
        return float(match.group("value").replace(",", ""))
    except ValueError:
        return None


def _table_headers(table: Any) -> list[str]:
    headers: list[str] = []
    for th in table.css("thead th"):
        headers.append(_clean_text(th).lower())
    return headers


def _row_cells(row: Any) -> list[str]:
    return [_clean_text(td) for td in row.css("td")]


def _find_header_index(headers: list[str], candidates: Iterable[str]) -> int | None:
    for i, header in enumerate(headers):
        for candidate in candidates:
            if candidate in header:
                return i
    return None


def parse_claude(html: str) -> list[ModelPricing]:
    """Parse Anthropic's pricing page.

    Looks for the main pricing table with columns
    ``Model | Base Input Tokens | ... | Output Tokens`` and extracts
    input/output plus cache read prices when available.
    """

    tree = HTMLParser(html)
    models: list[ModelPricing] = []
    seen: set[str] = set()

    for table in tree.css("table"):
        headers = _table_headers(table)
        if not headers or "model" not in headers[0]:
            continue
        joined = " ".join(headers)
        if "output" not in joined and "cost" not in joined:
            continue

        model_idx = 0
        input_idx = _find_header_index(headers, ["base input", "input"])
        output_idx = _find_header_index(headers, ["output"])
        cache_read_idx = _find_header_index(headers, ["cache hits", "cache read", "cached input"])
        cache_write_idx = _find_header_index(headers, ["5m cache write", "cache write"])

        for row in table.css("tbody tr"):
            cells = _row_cells(row)
            if len(cells) <= model_idx:
                continue
            name = _clean_model_name(cells[model_idx])
            if not name:
                continue
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            models.append(
                ModelPricing(
                    model=name,
                    input_per_1m_tokens=_value_at(cells, input_idx),
                    output_per_1m_tokens=_value_at(cells, output_idx),
                    cache_read_per_1m_tokens=_value_at(cells, cache_read_idx),
                    cache_write_per_1m_tokens=_value_at(cells, cache_write_idx),
                    raw={"headers": headers, "cells": cells},
                )
            )

    if not models:
        raise PricingParseError("Could not find any Claude pricing tables")
    return models


def _value_at(cells: list[str], index: int | None) -> float | None:
    if index is None or index >= len(cells):
        return None
    return _parse_dollars(cells[index])


def parse_openai(html: str) -> list[ModelPricing]:
    """Parse OpenAI's platform pricing page.

    Prefers the embedded ``TextTokenPricingTables`` Flight payload, which
    ships structured ``[model, input, cached_input, output]`` rows. Falls
    back to walking the rendered tables when the payload is missing.
    """

    models = _parse_openai_flight_payload(html)
    if not models:
        models = _parse_openai_tables(html)
    if not models:
        raise PricingParseError("Could not find any OpenAI pricing data")
    return models


def _parse_openai_flight_payload(html: str) -> list[ModelPricing]:
    """Extract rows of the form ``[1,[[0,"name"],[0,input],[0,cache|null],[0,output]]]``."""

    pattern = re.compile(
        r"\[1,\[\[0,&quot;(?P<name>[^&]+?)&quot;\]"
        r",\[0,(?P<input>\d+(?:\.\d+)?|null)\]"
        r",\[0,(?P<cache>\d+(?:\.\d+)?|null)\]"
        r",\[0,(?P<output>\d+(?:\.\d+)?|null)\]\]"
    )
    out: list[ModelPricing] = []
    seen: set[str] = set()
    for m in pattern.finditer(html):
        name = m.group("name").strip()
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        out.append(
            ModelPricing(
                model=name,
                input_per_1m_tokens=_maybe_float(m.group("input")),
                output_per_1m_tokens=_maybe_float(m.group("output")),
                cache_read_per_1m_tokens=_maybe_float(m.group("cache")),
            )
        )
    return out


def _parse_openai_tables(html: str) -> list[ModelPricing]:
    tree = HTMLParser(html)
    out: list[ModelPricing] = []
    seen: set[str] = set()
    for table in tree.css("table"):
        headers_raw = [_clean_text(th) for th in table.css("thead th")]
        if not headers_raw:
            continue
        headers = [h.lower() for h in headers_raw]
        if "model" not in headers[0]:
            continue
        model_idx = 0
        input_idx = _find_header_index(headers, ["input"])
        output_idx = _find_header_index(headers, ["output"])
        cache_idx = _find_header_index(headers, ["cached input", "cache read"])

        for row in table.css("tbody tr"):
            cells = _row_cells(row)
            if len(cells) <= model_idx:
                continue
            name = _clean_model_name(cells[model_idx])
            if not name or name.lower() in seen:
                continue
            seen.add(name.lower())
            notes = cells[1] if len(cells) > 1 else ""
            out.append(
                ModelPricing(
                    model=name,
                    input_per_1m_tokens=_value_at(cells, input_idx),
                    output_per_1m_tokens=_value_at(cells, output_idx),
                    cache_read_per_1m_tokens=_value_at(cells, cache_idx),
                    notes=notes if notes and notes.lower() != name.lower() else "",
                    raw={"headers": headers_raw, "cells": cells},
                )
            )
    return out


def _maybe_float(value: str) -> float | None:
    if value == "null":
        return None
    try:
        return float(value)
    except ValueError:
        return None
