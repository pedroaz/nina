from __future__ import annotations

import math
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

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

from .api import try_request
from .output import print_json

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
            "base_url": config.llm.base_url,
        },
        "research": {
            "provider": config.research.provider,
            "model": config.research.model,
            "search_mode": config.research.search_mode,
            "timeout_seconds": config.research.timeout_seconds,
        },
        "scheduler": {
            "daily_summary_time": config.scheduler.daily_summary_time,
        },
        "transcription": {
            "backend": config.transcription.backend,
            "model": config.transcription.model,
            "device": config.transcription.device,
            "compute_type": config.transcription.compute_type,
            "language": config.transcription.language,
        },
        "meetings": {
            "default_source": config.meetings.default_source,
            "auto_summarize": config.meetings.auto_summarize,
            "sample_rate": config.meetings.sample_rate,
            "channels": config.meetings.channels,
            "open_command": config.meetings.open_command,
            "play_command": config.meetings.play_command,
            "default_gain": config.meetings.default_gain,
            "auto_normalize": config.meetings.auto_normalize,
            "normalize_target_dbfs": config.meetings.normalize_target_dbfs,
            "noise_reduction": config.meetings.noise_reduction,
        },
        "voice": {
            "global_hotkey_enabled": config.voice.global_hotkey_enabled,
            "global_hotkey": config.voice.global_hotkey,
            "insert_mode": config.voice.insert_mode,
            "preserve_clipboard": config.voice.preserve_clipboard,
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
    table.add_row("LLM base URL", str(snapshot["llm"]["base_url"] or ""))
    table.add_row("Research provider", str(snapshot["research"]["provider"]))
    table.add_row("Research model", str(snapshot["research"]["model"]))
    table.add_row("Research search", str(snapshot["research"]["search_mode"]))
    table.add_row("Research timeout", f"{snapshot['research']['timeout_seconds']}s")
    table.add_row("Daily summary", str(snapshot["scheduler"]["daily_summary_time"]))
    table.add_row("Transcription backend", str(snapshot["transcription"]["backend"]))
    table.add_row("Transcription model", str(snapshot["transcription"]["model"]))
    table.add_row("Transcription device", str(snapshot["transcription"]["device"]))
    table.add_row("Transcription compute", str(snapshot["transcription"]["compute_type"]))
    table.add_row("Transcription language", str(snapshot["transcription"]["language"] or "auto"))
    table.add_row("Meetings default source", str(snapshot["meetings"]["default_source"]))
    table.add_row("Meetings auto-summarize", str(snapshot["meetings"]["auto_summarize"]))
    table.add_row("Meetings sample rate", str(snapshot["meetings"]["sample_rate"]))
    table.add_row("Meetings channels", str(snapshot["meetings"]["channels"]))
    gain = snapshot["meetings"]["default_gain"]
    gain_db = 0.0 if gain == 1.0 else 20.0 * math.log10(gain)
    table.add_row("Meetings default gain", f"{gain}x ({gain_db:+.1f} dB)")
    table.add_row("Meetings auto-normalize", str(snapshot["meetings"]["auto_normalize"]))
    table.add_row("Meetings normalize target", str(snapshot["meetings"]["normalize_target_dbfs"]))
    table.add_row("Meetings noise reduction", str(snapshot["meetings"]["noise_reduction"]))
    table.add_row("Meetings play command", str(snapshot["meetings"]["play_command"]))
    table.add_row("Voice global hotkey", str(snapshot["voice"]["global_hotkey"]))
    table.add_row("Voice hotkey enabled", str(snapshot["voice"]["global_hotkey_enabled"]))
    table.add_row("Voice insert mode", str(snapshot["voice"]["insert_mode"]))
    table.add_row("Voice preserve clipboard", str(snapshot["voice"]["preserve_clipboard"]))
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
    return try_request("PATCH", "/config", json=patch, timeout=10) is not None


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
        print_json(snapshot)
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


@config_app.command("research-provider")
def research_provider(
    provider: str,
    profile: str = typer.Option("default", help="Profile name"),
) -> None:
    updated, synced = _apply_update(profile, {"research": {"provider": provider}})
    console.print(f"Research provider: {updated.research.provider}")
    console.print("Applied to the running daemon." if synced else "Saved on disk.")


@config_app.command("research-model")
def research_model(
    model: str,
    profile: str = typer.Option("default", help="Profile name"),
) -> None:
    updated, synced = _apply_update(profile, {"research": {"model": model}})
    console.print(f"Research model: {updated.research.model}")
    console.print("Applied to the running daemon." if synced else "Saved on disk.")


@config_app.command("research-search-mode")
def research_search_mode(
    mode: str,
    profile: str = typer.Option("default", help="Profile name"),
) -> None:
    updated, synced = _apply_update(profile, {"research": {"search_mode": mode}})
    console.print(f"Research search mode: {updated.research.search_mode}")
    console.print("Applied to the running daemon." if synced else "Saved on disk.")


@config_app.command("research-timeout")
def research_timeout(
    seconds: float,
    profile: str = typer.Option("default", help="Profile name"),
) -> None:
    updated, synced = _apply_update(profile, {"research": {"timeout_seconds": seconds}})
    console.print(f"Research timeout: {updated.research.timeout_seconds}s")
    console.print("Applied to the running daemon." if synced else "Saved on disk.")


@config_app.command("llm-model")
def llm_model(
    model: str,
    profile: str = typer.Option("default", help="Profile name"),
) -> None:
    updated, synced = _apply_update(profile, {"llm": {"model": model}})
    console.print(f"LLM model: {updated.llm.model}")
    console.print("Applied to the running daemon." if synced else "Saved on disk.")


@config_app.command(
    "llm-base-url",
    help=(
        "Set the OpenAI-compatible base URL for `llm.provider = ollama` or "
        "`openai_compatible`. Pass an empty string to clear it."
    ),
)
def llm_base_url(
    base_url: str,
    profile: str = typer.Option("default", help="Profile name"),
) -> None:
    normalized = base_url.strip() or None
    updated, synced = _apply_update(profile, {"llm": {"base_url": normalized}})
    console.print(f"LLM base URL: {updated.llm.base_url or '(unset)'}")
    console.print("Applied to the running daemon." if synced else "Saved on disk.")


@config_app.command("daily-summary-time")
def daily_summary_time(
    time_value: str,
    profile: str = typer.Option("default", help="Profile name"),
) -> None:
    updated, synced = _apply_update(profile, {"scheduler": {"daily_summary_time": time_value}})
    console.print(f"Daily summary time: {updated.scheduler.daily_summary_time}")
    console.print("Applied to the running daemon." if synced else "Saved on disk.")


@config_app.command("transcription-backend")
def transcription_backend(
    backend: str,
    profile: str = typer.Option("default", help="Profile name"),
) -> None:
    updated, synced = _apply_update(profile, {"transcription": {"backend": backend}})
    console.print(f"Transcription backend: {updated.transcription.backend}")
    console.print("Applied to the running daemon." if synced else "Saved on disk.")


@config_app.command("transcription-model")
def transcription_model(
    model: str,
    profile: str = typer.Option("default", help="Profile name"),
) -> None:
    updated, synced = _apply_update(profile, {"transcription": {"model": model}})
    console.print(f"Transcription model: {updated.transcription.model}")
    console.print("Applied to the running daemon." if synced else "Saved on disk.")


@config_app.command("transcription-device")
def transcription_device(
    device: str,
    profile: str = typer.Option("default", help="Profile name"),
) -> None:
    updated, synced = _apply_update(profile, {"transcription": {"device": device}})
    console.print(f"Transcription device: {updated.transcription.device}")
    console.print("Applied to the running daemon." if synced else "Saved on disk.")


@config_app.command("meetings-default-device")
def meetings_default_device(
    device: str | None = typer.Argument(
        None,
        help="Audio device name (substring). Pass an empty string or omit to clear.",
    ),
    profile: str = typer.Option("default", help="Profile name"),
) -> None:
    """Set the default mic device used by `nina r` when `--device` is omitted."""
    new_value = device or None
    updated, synced = _apply_update(profile, {"meetings": {"default_device": new_value}})
    shown = updated.meetings.default_device or "(cleared)"
    console.print(f"Meetings default device: {shown}")
    console.print("Applied to the running daemon." if synced else "Saved on disk.")


@config_app.command("transcription-compute-type")
def transcription_compute_type(
    compute_type: str,
    profile: str = typer.Option("default", help="Profile name"),
) -> None:
    updated, synced = _apply_update(profile, {"transcription": {"compute_type": compute_type}})
    console.print(f"Transcription compute type: {updated.transcription.compute_type}")
    console.print("Applied to the running daemon." if synced else "Saved on disk.")


@config_app.command("transcription-language")
def transcription_language(
    language: str,
    profile: str = typer.Option("default", help="Profile name"),
) -> None:
    normalized = language.strip() or "auto"
    updated, synced = _apply_update(
        profile, {"transcription": {"language": None if normalized == "auto" else normalized}}
    )
    console.print(f"Transcription language: {updated.transcription.language or 'auto'}")
    console.print("Applied to the running daemon." if synced else "Saved on disk.")


@config_app.command(
    "edit",
    help=(
        "Open the config file in VS Code. Uses the `code` binary from PATH; "
        "falls back to `$EDITOR` if set, then to the OS default opener. "
        "Pass `--editor <name>` to force a different editor (e.g. `code --wait`, "
        "`nvim`, `nano`). The file is created with the current effective "
        "config if it doesn't exist yet."
    ),
)
def edit(
    profile: str = typer.Option("default", help="Profile name"),
    editor: str = typer.Option(
        None,
        "--editor",
        "-e",
        help=(
            "Editor command to launch. Use `{path}` as a placeholder for the "
            "config file path (e.g. `--editor 'code --wait'`). Defaults to "
            "`code` (VS Code), then `$EDITOR`, then the OS opener."
        ),
    ),
    wait: bool = typer.Option(
        False,
        "--wait",
        "-w",
        help="Block until the editor closes (passes `--wait` to VS Code).",
    ),
) -> None:
    config_dir, config = _load_config(profile)
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = get_config_path(config_dir)
    if not config_path.exists():
        # First run: write the current effective config so the editor
        # opens a real, schema-valid file. Uses the same serializer as
        # `_apply_update` so it's byte-for-byte consistent.
        config.save(config_path)
        console.print(f"Created {config_path} with current effective config.")
    if not config_path.exists():
        console.print(f"[red]Config file not found at {config_path}[/red]")
        raise typer.Exit(1) from None

    cmd = _resolve_editor_command(editor=editor, wait=wait, path=config_path)
    if cmd is None:
        console.print(
            "[red]No editor found. Set $EDITOR, install VS Code (`code` on "
            "PATH), or pass --editor '<command> {path}'.[/red]"
        )
        raise typer.Exit(1) from None
    try:
        subprocess.Popen(cmd)
    except FileNotFoundError as exc:
        console.print(f"[red]Failed to launch editor: {exc}[/red]")
        raise typer.Exit(1) from None
    console.print(f"Opening {config_path} in {cmd[0]}...")


@config_app.command(
    "open",
    help="Open the active profile config folder in VS Code.",
)
def open_config_folder(
    profile: str = typer.Option("default", help="Profile name"),
    wait: bool = typer.Option(False, "--wait", "-w", help="Block until VS Code closes."),
) -> None:
    config_dir, _ = _load_config(profile)
    config_dir.mkdir(parents=True, exist_ok=True)
    vscode_cmd = ["code"]
    if wait:
        vscode_cmd.append("--wait")
    if shutil.which("code"):
        subprocess.Popen([*vscode_cmd, str(config_dir)])
        console.print(f"Opening {config_dir} in VS Code...")
        return
    if os.name == "darwin":
        subprocess.Popen(["open", "-a", "Visual Studio Code", str(config_dir)])
        console.print(f"Opening {config_dir} in VS Code...")
        return
    console.print("[red]VS Code (`code`) is not on PATH.[/red]")
    raise typer.Exit(1) from None


def _resolve_editor_command(editor: str | None, wait: bool, path: Path) -> list[str] | None:
    """Pick the editor command. Returns the argv list, or None if nothing found.

    Resolution order:
    1. `--editor "<cmd> {path}"` (explicit user override)
    2. `--editor "<cmd>"` (placeholder-less override; we append `{path}`)
    3. `code` (VS Code) — `--wait` if user asked
    4. `$EDITOR` env var
    5. `xdg-open` (Linux) / `open` (macOS) / `start` (Windows)
    """
    path_str = str(path)
    if editor:
        if "{path}" in editor:
            return editor.format(path=path_str).split()
        return [*editor.split(), path_str]
    if shutil.which("code"):
        cmd = ["code"]
        if wait:
            cmd.append("--wait")
        return [*cmd, path_str]
    env_editor = os.environ.get("EDITOR", "").strip()
    if env_editor:
        return [*env_editor.split(), path_str]
    if os.name == "nt":
        return ["start", "", path_str]
    if shutil.which("xdg-open"):
        return ["xdg-open", path_str]
    if shutil.which("open"):
        return ["open", path_str]
    return None


@config_app.command("meetings-source")
def meetings_source(
    source: str,
    profile: str = typer.Option("default", help="Profile name"),
) -> None:
    updated, synced = _apply_update(profile, {"meetings": {"default_source": source}})
    console.print(f"Meetings default source: {updated.meetings.default_source}")
    console.print("Applied to the running daemon." if synced else "Saved on disk.")


@config_app.command("meetings-sample-rate")
def meetings_sample_rate(
    value: int,
    profile: str = typer.Option("default", help="Profile name"),
) -> None:
    if value <= 0:
        console.print("[red]Sample rate must be > 0.[/red]")
        raise typer.Exit(1) from None
    updated, synced = _apply_update(profile, {"meetings": {"sample_rate": value}})
    console.print(f"Meetings sample rate: {updated.meetings.sample_rate}")
    console.print("Applied to the running daemon." if synced else "Saved on disk.")


@config_app.command("meetings-channels")
def meetings_channels(
    value: int,
    profile: str = typer.Option("default", help="Profile name"),
) -> None:
    if value <= 0:
        console.print("[red]Channels must be > 0.[/red]")
        raise typer.Exit(1) from None
    updated, synced = _apply_update(profile, {"meetings": {"channels": value}})
    console.print(f"Meetings channels: {updated.meetings.channels}")
    console.print("Applied to the running daemon." if synced else "Saved on disk.")


@config_app.command("meetings-auto-normalize")
def meetings_auto_normalize(
    value: bool,
    profile: str = typer.Option("default", help="Profile name"),
) -> None:
    updated, synced = _apply_update(profile, {"meetings": {"auto_normalize": value}})
    console.print(f"Meetings auto-normalize: {updated.meetings.auto_normalize}")
    console.print("Applied to the running daemon." if synced else "Saved on disk.")


@config_app.command("meetings-normalize-target-dbfs")
def meetings_normalize_target_dbfs(
    value: float,
    profile: str = typer.Option("default", help="Profile name"),
) -> None:
    updated, synced = _apply_update(profile, {"meetings": {"normalize_target_dbfs": value}})
    console.print(f"Meetings normalize target dBFS: {updated.meetings.normalize_target_dbfs}")
    console.print("Applied to the running daemon." if synced else "Saved on disk.")


@config_app.command("meetings-noise-reduction")
def meetings_noise_reduction(
    value: str,
    profile: str = typer.Option("default", help="Profile name"),
) -> None:
    normalized = value.strip().lower() or "off"
    if normalized not in {"off", "ffmpeg"}:
        console.print("[red]Noise reduction must be 'off' or 'ffmpeg'.[/red]")
        raise typer.Exit(1) from None
    updated, synced = _apply_update(profile, {"meetings": {"noise_reduction": normalized}})
    console.print(f"Meetings noise reduction: {updated.meetings.noise_reduction}")
    console.print("Applied to the running daemon." if synced else "Saved on disk.")


@config_app.command("voice-global-hotkey-enabled")
def voice_global_hotkey_enabled(
    value: bool,
    profile: str = typer.Option("default", help="Profile name"),
) -> None:
    updated, synced = _apply_update(profile, {"voice": {"global_hotkey_enabled": value}})
    console.print(f"Voice global hotkey enabled: {updated.voice.global_hotkey_enabled}")
    console.print("Applied to the running daemon." if synced else "Saved on disk.")


@config_app.command("voice-global-hotkey")
def voice_global_hotkey(
    value: str,
    profile: str = typer.Option("default", help="Profile name"),
) -> None:
    updated, synced = _apply_update(profile, {"voice": {"global_hotkey": value}})
    console.print(f"Voice global hotkey: {updated.voice.global_hotkey}")
    console.print("Applied to the running daemon." if synced else "Saved on disk.")


@config_app.command("voice-preserve-clipboard")
def voice_preserve_clipboard(
    value: bool,
    profile: str = typer.Option("default", help="Profile name"),
) -> None:
    updated, synced = _apply_update(profile, {"voice": {"preserve_clipboard": value}})
    console.print(f"Voice preserve clipboard: {updated.voice.preserve_clipboard}")
    console.print("Applied to the running daemon." if synced else "Saved on disk.")


@config_app.command("voice-insert-mode")
def voice_insert_mode(
    value: str,
    profile: str = typer.Option("default", help="Profile name"),
) -> None:
    normalized = value.strip().lower()
    if normalized != "clipboard_paste":
        console.print("[red]Voice insert mode must be 'clipboard_paste'.[/red]")
        raise typer.Exit(1) from None
    updated, synced = _apply_update(profile, {"voice": {"insert_mode": normalized}})
    console.print(f"Voice insert mode: {updated.voice.insert_mode}")
    console.print("Applied to the running daemon." if synced else "Saved on disk.")


@config_app.command("auto-summarize")
def auto_summarize(
    value: bool,
    profile: str = typer.Option("default", help="Profile name"),
) -> None:
    updated, synced = _apply_update(profile, {"meetings": {"auto_summarize": value}})
    console.print(f"Auto-summarize after recording: {updated.meetings.auto_summarize}")
    console.print("Applied to the running daemon." if synced else "Saved on disk.")


@config_app.command(
    "meetings-gain",
    help=(
        "Default linear gain applied to every recording. Use this when your "
        "system source volume is low (e.g. 2.0 = +6 dB, 4.0 = +12 dB). "
        "Per-call `--gain` on `nina r` still overrides."
    ),
)
def meetings_gain(
    value: float = typer.Argument(..., help="Linear gain factor (e.g. 2.0 = +6 dB, 4.0 = +12 dB)"),
    profile: str = typer.Option("default", help="Profile name"),
) -> None:
    if value <= 0:
        console.print("[red]Gain must be > 0 (use 1.0 for no change).[/red]")
        raise typer.Exit(1) from None
    updated, synced = _apply_update(profile, {"meetings": {"default_gain": value}})
    actual = updated.meetings.default_gain
    if abs(actual - 1.0) < 1e-9:
        db = 0.0
    else:
        import math

        db = 20.0 * math.log10(actual)
    console.print(f"Meetings default gain: {actual}x ({db:+.1f} dB).")
    console.print("Applied to the running daemon." if synced else "Saved on disk.")
