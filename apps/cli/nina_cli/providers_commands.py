from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import typer
from rich.table import Table

from nina_core.config import get_config_dir
from nina_core.pricing import PricingService
from nina_core.pricing.providers import available_providers, normalize_provider_name

from .output import console, print_json

providers_app = typer.Typer(help="Look up model pricing for supported LLM providers")


def _service() -> PricingService:
    # Always pass the config dir explicitly so this command works even when
    # `NINA_CONFIG_DIR` is not exported (e.g. when launched from a bare shell
    # or by another tool). `get_config_dir` already falls back to
    # `~/.nina/default` if the env var is missing.
    config_dir = os.environ.get("NINA_CONFIG_DIR") or get_config_dir()
    return PricingService(Path(config_dir))


def _format_price(value: float | None) -> str:
    if value is None:
        return "-"
    if value == 0:
        return "0"
    if value < 0.01:
        return f"{value:.4f}"
    if value < 1:
        return f"{value:.3f}"
    return f"{value:.2f}"


def _format_timestamp(value: str) -> str:
    try:
        dt = datetime.fromisoformat(value)
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except ValueError:
        return value


def _resolve_configured_model() -> str | None:
    from nina_core.config import get_config_dir, load_effective_config

    config_dir = get_config_dir()
    if not config_dir.exists():
        return None
    try:
        return load_effective_config(Path(config_dir)).llm.model
    except Exception:
        return None


def _build_table(
    providers: list,
    *,
    highlight_model: str | None,
) -> Table:
    table = Table(
        "Provider",
        "Model",
        "Input $/1M",
        "Output $/1M",
        "Cache Read",
        "Cache Write",
        "Fetched",
        title="Provider pricing (USD per 1M tokens)",
        show_lines=False,
    )
    highlighted: set[tuple[str, str]] = set()
    if highlight_model:
        target = highlight_model.lower()
        for provider in providers:
            for model in provider.models:
                if model.model.lower() == target:
                    highlighted.add((provider.provider, model.model))

    for provider in providers:
        first = True
        for model in provider.models:
            is_match = (provider.provider, model.model) in highlighted
            style = "bold magenta" if is_match else None
            table.add_row(
                provider.label if first else "",
                model.model,
                _format_price(model.input_per_1m_tokens),
                _format_price(model.output_per_1m_tokens),
                _format_price(model.cache_read_per_1m_tokens),
                _format_price(model.cache_write_per_1m_tokens),
                _format_timestamp(provider.fetched_at) if first else "",
                style=style,
            )
            first = False
    return table


def _print_empty_hint() -> None:
    console.print("No cached pricing data.")
    console.print("Run `nina providers refresh` to fetch the latest prices.")
    raise typer.Exit(0)


def _filter(
    providers: list,
    *,
    provider: str | None,
    model: str | None,
) -> list:
    out: list = []
    for entry in providers:
        if provider and normalize_provider_name(provider) != entry.provider:
            continue
        if model:
            needle = model.lower()
            filtered = [m for m in entry.models if needle in m.model.lower()]
            if not filtered:
                continue
            out.append(entry.model_copy(update={"models": filtered}))
        else:
            out.append(entry)
    return out


@providers_app.callback(invoke_without_command=True)
def providers_main(
    ctx: typer.Context,
    provider: str | None = typer.Option(None, "--provider", "-p", help="Filter by provider name"),
    model: str | None = typer.Option(
        None, "--model", "-m", help="Substring filter on the model name"
    ),
    json_output: bool = typer.Option(False, "--json", help="Print JSON"),
) -> None:
    if ctx.invoked_subcommand is not None:
        return
    service = _service()
    providers = _filter(service.get_all(), provider=provider, model=model)
    if not providers:
        _print_empty_hint()
        return
    if json_output:
        print_json([p.model_dump() for p in providers])
        return
    table = _build_table(providers, highlight_model=_resolve_configured_model())
    console.print(table)
    sources = sorted({p.source_url for p in providers})
    console.print(f"\nSources: {', '.join(sources)}")


@providers_app.command("list")
def providers_list(
    provider: str | None = typer.Option(None, "--provider", "-p"),
    model: str | None = typer.Option(None, "--model", "-m"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    service = _service()
    providers = _filter(service.get_all(), provider=provider, model=model)
    if not providers:
        _print_empty_hint()
        return
    if json_output:
        print_json([p.model_dump() for p in providers])
        return
    table = _build_table(providers, highlight_model=_resolve_configured_model())
    console.print(table)


@providers_app.command("show")
def providers_show(
    model: str = typer.Argument(..., help="Substring to match against model names"),
    provider: str | None = typer.Option(None, "--provider", "-p"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    service = _service()
    providers = _filter(service.get_all(), provider=provider, model=model)
    if not providers:
        console.print(f"No models match '{model}'.")
        raise typer.Exit(1)
    if json_output:
        print_json([p.model_dump() for p in providers])
        return
    table = _build_table(providers, highlight_model=_resolve_configured_model())
    console.print(table)


@providers_app.command("refresh")
def providers_refresh(
    provider: list[str] | None = typer.Option(
        None, "--provider", "-p", help="Provider to refresh (repeatable)"
    ),
    source: list[str] | None = typer.Option(
        None,
        "--source",
        help="Read a saved HTML page instead of fetching, e.g. claude:./claude.html",
    ),
) -> None:
    service = _service()
    selected = [normalize_provider_name(p) for p in provider] if provider else None
    sources: dict[str, str] = {}
    if source:
        for item in source:
            if ":" not in item:
                console.print(f"--source must be 'provider:path', got '{item}'")
                raise typer.Exit(2)
            key, _, path = item.partition(":")
            sources[normalize_provider_name(key)] = path

    targets = selected or available_providers()
    summary: list[tuple[str, int, str]] = []
    try:
        if selected:
            for key in selected:
                refreshed = service.refresh(key, source=sources.get(key))
                for p in refreshed:
                    summary.append((p.label, len(p.models), p.fetched_at))
        else:
            for key in targets:
                refreshed = service.refresh(key, source=sources.get(key))
                for p in refreshed:
                    summary.append((p.label, len(p.models), p.fetched_at))
    except Exception as exc:
        console.print(f"Refresh failed: {exc}")
        raise typer.Exit(2) from None

    for label, count, fetched_at in summary:
        console.print(f"{label}: {count} models, fetched {_format_timestamp(fetched_at)}")
