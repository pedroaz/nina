from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import typer
from rich.console import Console
from rich.table import Table

from nina_core.config import (
    NinaConfig,
    ensure_vault_structure,
    get_config_dir,
    get_config_path,
    get_token_path,
    load_effective_config,
    merge_config,
)
from nina_core.db import create_database
from nina_core.search.indexer import create_fts_table

from .api import api_base, headers

console = Console()
config_app = typer.Typer(help="Configuration commands")


def _load_config(profile: str) -> tuple[Path, NinaConfig]:
    config_dir = get_config_dir(profile)
    config = load_effective_config(config_dir)
    return config_dir, config


def _public_snapshot(config_dir: Path, config: NinaConfig) -> dict[str, Any]:
    return {
        "profile": config.profile,
        "config_dir": str(config_dir),
        "config_path": str(get_config_path(config_dir)),
        "vault_path": config.vault_path,
        "database_path": config.database_path,
        "daemon_host": config.daemon_host,
        "daemon_port": config.daemon_port,
        "llm": {
            "provider": config.llm.provider,
            "model": config.llm.model,
        },
        "scheduler": {
            "daily_summary_time": config.scheduler.daily_summary_time,
        },
        "log_level": config.log_level,
    }


def _print_snapshot(snapshot: dict[str, Any]) -> None:
    table = Table("Setting", "Value", show_lines=False)
    table.add_row("Profile", str(snapshot["profile"]))
    table.add_row("Config dir", str(snapshot["config_dir"]))
    table.add_row("Config file", str(snapshot["config_path"]))
    table.add_row("Vault path", str(snapshot["vault_path"]))
    table.add_row("Database path", str(snapshot["database_path"]))
    table.add_row("Daemon host", str(snapshot["daemon_host"]))
    table.add_row("Daemon port", str(snapshot["daemon_port"]))
    table.add_row("LLM provider", str(snapshot["llm"]["provider"]))
    table.add_row("LLM model", str(snapshot["llm"]["model"]))
    table.add_row("Daily summary", str(snapshot["scheduler"]["daily_summary_time"]))
    table.add_row("Log level", str(snapshot["log_level"]))
    console.print(table)


def _ensure_storage(previous: NinaConfig, updated: NinaConfig) -> None:
    updated_vault = Path(updated.vault_path)
    if previous.vault_path != updated.vault_path or not updated_vault.exists():
        ensure_vault_structure(updated_vault)

    updated_db = Path(updated.database_path)
    if previous.database_path != updated.database_path or not updated_db.exists():
        create_database(str(updated_db))
        create_fts_table(str(updated_db))


def _sync_daemon(profile: str, patch: dict[str, Any]) -> bool:
    token_path = get_token_path(get_config_dir(profile))
    if not token_path.exists():
        return False
    try:
        response = httpx.patch(
            f"{api_base()}/config",
            headers=headers(),
            json=patch,
            timeout=10,
        )
        response.raise_for_status()
    except Exception:
        return False
    return True


def _apply_update(profile: str, patch: dict[str, Any]) -> tuple[NinaConfig, bool]:
    config_dir, previous = _load_config(profile)
    config_dir.mkdir(parents=True, exist_ok=True)
    updated = merge_config(previous, patch, config_dir)
    updated.save(get_config_path(config_dir))
    _ensure_storage(previous, updated)
    synced = _sync_daemon(profile, patch)
    return updated, synced


@config_app.command("show")
def show(
    profile: str = typer.Option("default", help="Profile name"),
    json_output: bool = typer.Option(False, "--json", help="Print JSON"),
) -> None:
    config_dir, config = _load_config(profile)
    snapshot = _public_snapshot(config_dir, config)
    if json_output:
        typer.echo(json.dumps(snapshot, indent=2, sort_keys=False))
        return
    _print_snapshot(snapshot)


@config_app.command("vault")
def vault(
    path: str,
    profile: str = typer.Option("default", help="Profile name"),
) -> None:
    updated, synced = _apply_update(profile, {"vault_path": path})
    console.print(f"Vault path: {updated.vault_path}")
    console.print("Applied to the running daemon." if synced else "Saved on disk.")


@config_app.command("database")
def database(
    path: str,
    profile: str = typer.Option("default", help="Profile name"),
) -> None:
    updated, synced = _apply_update(profile, {"database_path": path})
    console.print(f"Database path: {updated.database_path}")
    console.print("Applied to the running daemon." if synced else "Saved on disk.")


@config_app.command("daemon-host")
def daemon_host(
    host: str,
    profile: str = typer.Option("default", help="Profile name"),
) -> None:
    updated, synced = _apply_update(profile, {"daemon_host": host})
    console.print(f"Daemon host: {updated.daemon_host}")
    console.print("Applied to the running daemon." if synced else "Saved on disk.")
    console.print("Restart Nina daemon to apply the new host.")


@config_app.command("daemon-port")
def daemon_port(
    port: int,
    profile: str = typer.Option("default", help="Profile name"),
) -> None:
    updated, synced = _apply_update(profile, {"daemon_port": port})
    console.print(f"Daemon port: {updated.daemon_port}")
    console.print("Applied to the running daemon." if synced else "Saved on disk.")
    console.print("Restart Nina daemon to apply the new port.")


@config_app.command("log-level")
def log_level(
    level: str,
    profile: str = typer.Option("default", help="Profile name"),
) -> None:
    updated, synced = _apply_update(profile, {"log_level": level})
    console.print(f"Log level: {updated.log_level}")
    console.print("Applied to the running daemon." if synced else "Saved on disk.")
    console.print("Restart Nina daemon to apply the new log level.")


@config_app.command("llm-provider")
def llm_provider(
    provider: str,
    profile: str = typer.Option("default", help="Profile name"),
) -> None:
    updated, synced = _apply_update(profile, {"llm": {"provider": provider}})
    console.print(f"LLM provider: {updated.llm.provider}")
    console.print("Applied to the running daemon." if synced else "Saved on disk.")


@config_app.command("llm-model")
def llm_model(
    model: str,
    profile: str = typer.Option("default", help="Profile name"),
) -> None:
    updated, synced = _apply_update(profile, {"llm": {"model": model}})
    console.print(f"LLM model: {updated.llm.model}")
    console.print("Applied to the running daemon." if synced else "Saved on disk.")


@config_app.command("daily-summary-time")
def daily_summary_time(
    time_value: str,
    profile: str = typer.Option("default", help="Profile name"),
) -> None:
    updated, synced = _apply_update(profile, {"scheduler": {"daily_summary_time": time_value}})
    console.print(f"Daily summary time: {updated.scheduler.daily_summary_time}")
    console.print("Applied to the running daemon." if synced else "Saved on disk.")
