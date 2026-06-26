import os
import shutil
import sys
import subprocess
import time
from pathlib import Path
from typing import Any

import typer

from nina_core.config import (
    NinaConfig,
    get_config_dir,
    get_config_path,
    get_database_path,
    get_log_path,
    get_pid_path,
    get_token_path,
    initialize,
    load_effective_config,
)
from nina_core.llm.provider import check_provider_status, codex_auth_status
from nina_core.llm.transcription import check_transcription_status

from .api import api_base, request, try_request_json
from .chat_commands import chat_app
from .config_commands import config_app
from .daemon_commands import (
    _daemon_status,
    _process_exists,
    _read_pid,
    _terminate_process,
    daemon_app,
    daemon_restart,
)
from .integrations_commands import integrations_app
from .job_commands import job_app
from .setup_commands import setup_app
from .llm_commands import llm_app
from .meeting_commands import meeting_app, record_meeting
from .notes_commands import note_app
from .codex_commands import codex_app
from .output import console, print_json
from .providers_commands import providers_app
from .repo_commands import repo_app
from .research_commands import research_app
from .search_commands import search_app
from .task_commands import task_app
from .ticket_commands import ticket_app
from .voice_commands import voice_app
from .workflow_commands import workflow_app


def _print_short_help() -> None:
    """Compact help for the top-level `nina` command."""

    console.print(
        "[bold]Nina[/bold] - local-first personal operations platform\n"
        "\n"
        "[bold]Most common[/bold]\n"
        '  [cyan]nina r  "title"[/cyan]      record a meeting (alias for `meeting record`)\n'
        "  [cyan]nina mt list[/cyan]         list meetings (alias for `meeting list`)\n"
        "  [cyan]nina mt stop[/cyan]         stop the active recording\n"
        "  [cyan]nina mt e <id>[/cyan]       transcribe + summarize a meeting\n"
        "  [cyan]nina vc r --copy[/cyan]      record, transcribe, and copy a voice clip\n"
        '  [cyan]nina ask "q?"[/cyan]        ask a question over the vault\n'
        '  [cyan]nina search "q"[/cyan]      full-text search the vault\n'
        "  [cyan]nina config show[/cyan]     inspect settings\n"
        "\n"
        "[bold]Compact aliases[/bold]\n"
        "  r = meeting record       mt = meeting sub-app   h = compact help\n"
        "  help = compact help (alias for `h`)\n"
        "  d = daemon              o = open                 n = note\n"
        "  tk = ticket             --h = -h = --help\n"
        "  j = job                  c = config\n"
        "  vc = voice               rch = research           s = search              ll = llm\n"
        "  int = integrations       wf = workflow\n"
        "\n"
        "[bold]Meeting subcommands[/bold] (via `nina mt ...`):\n"
        "  ls = list    e = pipeline (transcribe + summarize)    s = stop\n"
        "  o = open     p = play          rm = delete      x = show\n"
        "\n"
        "[bold]Voice subcommands[/bold] (via `nina vc ...`):\n"
        "  r = record   t = transcribe    ls = list       x = show\n"
        "\n"
        "[bold]Task subcommands[/bold] (via `nina task ...` or `nina tk ...`):\n"
        "  list / ls       create         show          type <id> <t>\n"
        "  classify <id>   run <id>       archive       unarchive     delete\n"
        "  board                                          (type-grouped view)\n"
        "\n"
        "[bold]New quality helpers[/bold]\n"
        "  nina doctor         check local health and configuration\n"
        "  nina recent [--json] quick activity summary across tasks, tickets, notes, and jobs\n"
        "\n"
        "[bold]Run[/bold] [cyan]nina <command> --help[/cyan] [bold]for options.[/bold]"
    )


app = typer.Typer(
    help="Nina CLI - local-first personal operations platform. Try `nina r` to record a meeting.",
    no_args_is_help=False,
    add_completion=False,
    context_settings={"help_option_names": ["--h", "-h", "--help"]},
)


@app.callback(invoke_without_command=True)
def _main_callback(
    version: bool = typer.Option(
        False,
        "-v",
        "--version",
        help="Print the Nina version and exit.",
        is_eager=True,
    ),
) -> None:
    if version:
        _print_version()
        raise typer.Exit()


def _add_alias(parent: typer.Typer, sub_app: typer.Typer, alias: str) -> None:
    """Register a hidden sub-app alias so `nina <alias>` works but doesn't clutter help."""
    parent.add_typer(sub_app, name=alias, hidden=True)


def _default_launcher_dir() -> Path:
    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "Programs" / "Nina" / "bin"
        return Path.home() / "AppData" / "Local" / "Programs" / "Nina" / "bin"
    return Path.home() / ".local" / "bin"


def _launcher_path(launcher_dir: Path) -> Path:
    return launcher_dir / ("nina.cmd" if os.name == "nt" else "nina")


def _remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
    elif path.is_dir():
        shutil.rmtree(path, ignore_errors=True)


def _config_root_for_uninstall(config_dir: Path) -> Path:
    if config_dir.parent.name == ".nina":
        return config_dir.parent
    return config_dir


app.add_typer(daemon_app, name="daemon")
_add_alias(app, daemon_app, "d")
app.command("restart", hidden=True, help="Restart the local Nina daemon.")(daemon_restart)
app.add_typer(chat_app, name="chat")
app.add_typer(config_app, name="config")
_add_alias(app, config_app, "c")
app.add_typer(note_app, name="note")
_add_alias(app, note_app, "n")
app.add_typer(codex_app, name="codex")
app.add_typer(providers_app, name="providers")
app.add_typer(task_app, name="task")
app.add_typer(ticket_app, name="ticket")
_add_alias(app, ticket_app, "tk")
app.add_typer(job_app, name="job")
_add_alias(app, job_app, "j")
app.add_typer(llm_app, name="llm")
_add_alias(app, llm_app, "ll")
app.add_typer(meeting_app, name="meeting")
_add_alias(app, meeting_app, "mt")
app.add_typer(repo_app, name="repo")
app.add_typer(research_app, name="research")
_add_alias(app, research_app, "rch")
app.add_typer(search_app, name="search")
_add_alias(app, search_app, "s")
app.add_typer(setup_app, name="setup")
app.add_typer(integrations_app, name="integrations")
_add_alias(app, integrations_app, "int")
app.add_typer(voice_app, name="voice")
_add_alias(app, voice_app, "vc")
app.add_typer(workflow_app, name="workflow")
_add_alias(app, workflow_app, "wf")


@app.command(
    "uninstall",
    help="Remove the launcher, install root, and all Nina config/data.",
)
def uninstall() -> None:
    config_dir = get_config_dir()
    install_root = Path(
        os.environ.get("NINA_INSTALL_ROOT", str(Path.home() / ".nina"))
    ).expanduser()
    launcher_dir = Path(
        os.environ.get("NINA_LAUNCHER_DIR", str(_default_launcher_dir()))
    ).expanduser()
    launcher = _launcher_path(launcher_dir)
    config_root = _config_root_for_uninstall(config_dir)

    pid_path = get_pid_path(config_dir)
    pid = _read_pid(pid_path) if pid_path.exists() else None
    if pid is not None and _process_exists(pid):
        _terminate_process(pid)

    targets: list[Path] = []
    for candidate in [launcher, install_root, config_root]:
        if candidate not in targets:
            targets.append(candidate)

    for target in targets:
        _remove_path(target)

    console.print("Removed Nina launcher, install root, and config data.")


def _daemon_health() -> str:
    data = try_request_json("GET", "/health", timeout=2)
    if not isinstance(data, dict):
        return "offline"
    status = data.get("status", "unknown")
    return str(status) if status is not None else "unknown"


def _configuration_entries(config_dir: Path, config: NinaConfig) -> list[tuple[str, str]]:
    return [
        ("Config dir", str(config_dir)),
        ("Config file", str(get_config_path(config_dir))),
        ("Token", str(get_token_path(config_dir))),
        ("Database", config.database_path),
        ("Vault", config.vault_path or "(not configured)"),
        ("Daemon host", config.daemon_host),
        ("Daemon port", str(config.daemon_port)),
        ("Daemon URL", api_base()),
        ("LLM provider", config.llm.provider),
        ("LLM model", config.llm.model),
        ("LLM base URL", config.llm.base_url or ""),
        ("Daily summary", config.scheduler.daily_summary_time),
        ("Log level", config.log_level),
        ("Log", str(get_log_path(config_dir))),
        ("PID", str(get_pid_path(config_dir))),
    ]


def _format_codex_auth_status() -> str:
    status = codex_auth_status()
    if status.connected:
        detail = f" ({status.detail})" if status.detail else ""
        return f"LLM auth: handled by Codex CLI{detail}"
    detail = status.detail or "unknown error"
    return f"LLM auth: Codex CLI unavailable ({detail})"


def _format_provider_auth_status(config: NinaConfig) -> str:
    provider = (config.llm.provider or "").lower()
    if provider in {"codex", "openai", "openai_web", "web"}:
        return _format_codex_auth_status()
    if provider in {"ollama", "openai_compatible", "llamacpp", "vllm", "lmstudio"}:
        return f"LLM auth: not required for local provider {provider}"
    return f"LLM auth: provider {provider or 'unknown'}"


def _format_llm_status(config: NinaConfig) -> str:
    """Show the LLM provider's reachability, used by `nina status`.

    For local runtimes (Ollama, llama.cpp) it pings the server. For Codex
    it checks the local CLI binary without sending a prompt.
    """
    try:
        status = check_provider_status(config.llm, timeout=2.0)
    except Exception as exc:  # noqa: BLE001
        return f"LLM provider: error ({exc})"
    head = f"LLM provider: {status.provider}"
    if status.base_url:
        head += f" @ {status.base_url}"
    if status.reachable and status.model_present:
        return f"{head} -> ready (model {status.model!r})"
    bits: list[str] = []
    if status.reachable:
        bits.append("reachable")
    elif status.provider == "codex":
        bits.append("unavailable")
    else:
        bits.append("unreachable")
    if status.model:
        bits.append(f"model {'present' if status.model_present else 'missing'}")
    line = f"{head} -> {', '.join(bits)}"
    if status.detail:
        line += f" ({status.detail})"
    return line


def _format_transcription_status(config: NinaConfig) -> str:
    """Show the transcription backend's install state, used by `nina status`.

    For `local_whisper`/`faster_whisper` it reports whether the package is
    installed. For `whisper_cli` it checks the `whisper` binary on PATH.
    """
    try:
        status = check_transcription_status(config.transcription)
    except Exception as exc:  # noqa: BLE001
        return f"Transcription: error ({exc})"
    if status.available:
        return (
            f"Transcription: {status.backend} -> ready "
            f"(model {status.model!r}, {status.device}/{status.compute_type})"
        )
    return f"Transcription: {status.backend} -> not available ({status.detail})"


def _format_meeting_pipeline_status(config: NinaConfig) -> str:
    """Show whether the full transcribe + summarize pipeline is wired up.

    Combines the LLM and transcription checks into a single yes/no so the
    user can tell at a glance whether `nina meeting pipeline` will
    work end-to-end.
    """
    try:
        llm = check_provider_status(config.llm, timeout=1.0)
        tr = check_transcription_status(config.transcription)
    except Exception as exc:  # noqa: BLE001
        return f"Meeting pipeline: error ({exc})"
    if tr.available and llm.reachable and (llm.model_present or not llm.model):
        return "Meeting pipeline: ready (nina meeting pipeline <id>)"
    issues: list[str] = []
    if not tr.available:
        issues.append(f"transcription ({tr.backend}) not ready")
    if not llm.reachable:
        issues.append(f"LLM ({llm.provider}) not reachable")
    elif llm.model and not llm.model_present:
        issues.append(f"LLM model {llm.model!r} not present")
    return f"Meeting pipeline: degraded ({'; '.join(issues)})"


def _format_codex_status() -> str:
    """Surface the supervised codex server state in `nina status`.

    Goes through the daemon's `/codex/status` endpoint so we don't need
    to know whether the daemon was started in this process. Falls back to
    a clean "not running" line if the daemon is offline.
    """
    data = try_request_json("GET", "/codex/status", timeout=2)
    if not isinstance(data, dict):
        return "Codex: (unknown — daemon offline)"
    state = data.get("state", "unknown")
    if state == "running":
        version = data.get("version") or "?"
        host = data.get("host", "?")
        port = data.get("port", "?")
        return f"Codex: {version} (running) @ http://{host}:{port}"
    if state == "disabled":
        return "Codex: disabled (set `codex.enabled: true` in config)"
    if state == "not_installed":
        return "Codex: not installed (binary not on PATH)"
    detail = data.get("last_error") or ""
    if detail:
        return f"Codex: {state} — {detail}"
    return f"Codex: {state}"


def _format_config_warnings(config: NinaConfig) -> list[str]:
    warnings: list[str] = []
    if not config.vault_path:
        warnings.append("Obsidian vault path is not configured. Run `nina config vault <path>`.")
    provider = (config.llm.provider or "").lower()
    llm_status = check_provider_status(config.llm, timeout=1.0)
    transcription = check_transcription_status(config.transcription)

    if provider in {"codex", "openai", "openai_web", "web"} and not llm_status.reachable:
        warnings.append(f"Codex CLI unavailable ({llm_status.detail or 'unknown error'})")
    elif (
        provider in {"openai_compatible", "llamacpp", "vllm", "lmstudio"}
        and not config.llm.base_url
    ):
        warnings.append(f"{provider} provider selected but llm.base_url is not set")

    if llm_status.reachable and llm_status.model and not llm_status.model_present:
        warnings.append(f"LLM model {llm_status.model!r} is not present")
    if not transcription.available:
        warnings.append(
            f"Transcription backend unavailable ({transcription.detail or 'unknown error'})"
        )
    return warnings


def _open_target(path: Path, wait: bool) -> None:
    if not path.exists():
        console.print(f"[red]Path not found: {path}[/red]")
        raise typer.Exit(1) from None

    if os.name == "nt":
        try:
            os.startfile(str(path))
            console.print(f"Opened {path}")
            return
        except OSError as exc:  # noqa: BLE001
            console.print(f"[red]Failed to open {path}: {exc}[/red]")
            raise typer.Exit(1) from None

    opener = shutil.which("xdg-open") or shutil.which("open")
    if not opener:
        console.print("[red]No supported file opener found. Install `xdg-open` or `open`.[/red]")
        raise typer.Exit(1) from None

    command = [opener, str(path)]
    if wait:
        subprocess.run(command, check=False)
    else:
        subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    console.print(f"Opened {path}")


@app.command("ask", help="Ask a question over the local Obsidian vault.")
def ask(
    question: str = typer.Argument(..., help="Question in natural language"),
    limit: int = typer.Option(5, "-n", "--limit", help="Maximum source notes to use"),
) -> None:
    resp = request("POST", "/ask", json={"question": question, "limit": limit})
    data = resp.json()
    console.print(data["answer"])
    sources = data.get("sources", [])
    if sources:
        console.print("\nSources:")
        for source in sources:
            console.print("- {}".format(source["path"]))


@app.command("open", help="Open Nina profile files and directories.")
def open_path(
    target: str = typer.Argument(
        "config",
        help="One of: config, config-folder, config-file, token, vault, db, logs, daemon-pid, all",
    ),
    profile: str = typer.Option("default", help="Profile name"),
    wait: bool = typer.Option(
        False,
        "-w",
        "--wait",
        help="Wait for the viewer to close (best effort).",
    ),
) -> None:
    config_dir = get_config_dir(profile)
    config = load_effective_config(config_dir)
    if target == "vault" and not config.vault_path:
        console.print(
            "[red]Obsidian vault path is not configured. Run `nina config vault <path>`.[/red]"
        )
        raise typer.Exit(1) from None
    targets: dict[str, Path] = {
        "config": config_dir,
        "all": config_dir,
        "config-folder": config_dir,
        "config-file": get_config_path(config_dir),
        "token": get_token_path(config_dir),
        "vault": Path(config.vault_path),
        "db": get_database_path(config_dir),
        "logs": get_log_path(config_dir),
        "daemon-pid": get_pid_path(config_dir),
    }

    path = targets.get(target)
    if path is None:
        console.print(f"Unknown target: {target}")
        console.print("Valid targets: " + ", ".join(sorted(targets)))
        raise typer.Exit(1)

    _open_target(path, wait=wait)


@app.command("r", help="Record a meeting. Alias for `nina meeting record`.", hidden=True)
def nina_r(
    title: str = typer.Argument("Untitled", help='Meeting title (or "Untitled" to use the date)'),
    source: str | None = typer.Option(
        None,
        "-s",
        "--source",
        help=(
            "Audio source: mic, system, mixed, or parec (explicit PulseAudio/PipeWire source via `--device`)"
        ),
    ),
    device: str | None = typer.Option(
        None, "-d", "--device", help="Fallback audio device name or index"
    ),
    mic_device: str | None = typer.Option(None, "--mic-device", help="Mic device name or index"),
    system_device: str | None = typer.Option(
        None, "--system-device", help="System/loopback device name or index"
    ),
    sample_rate: int = typer.Option(
        0, "-r", "--sample-rate", help="Sample rate in Hz (default from config)"
    ),
    channels: int = typer.Option(0, "-c", "--channels", help="Channel count (default from config)"),
    duration: int | None = typer.Option(
        None, "-D", "--duration", help="Auto-stop after this many seconds"
    ),
    gain: float | None = typer.Option(
        None,
        "--gain",
        help=(
            "Linear gain applied after recording (e.g. 4.0 = +12 dB). "
            "Defaults to the daemon config if omitted."
        ),
    ),
    auto_normalize: bool | None = typer.Option(
        None,
        "--auto-normalize/--no-auto-normalize",
        help="Auto-gain the WAV so its peak hits the configured dBFS target.",
    ),
    normalize_target_dbfs: float | None = typer.Option(
        None,
        "--normalize-target-dbfs",
        help="Peak dBFS target used when auto-normalizing.",
    ),
    noise_reduction: str | None = typer.Option(
        None,
        "--noise-reduction",
        help="Optional noise reduction mode: off or ffmpeg.",
    ),
) -> None:
    """Quick alias for `nina meeting record`. Stops on Ctrl+C.

    Examples:

        nina r "Quarterly planning"

        nina r "Standup" -s system

        nina r --duration 1800

        nina r "Quiet room" --gain 4.0

        nina r "Whatever volume" --auto-normalize
    """
    record_meeting(
        title=title,
        source=source,
        device=device,
        mic_device=mic_device,
        system_device=system_device,
        sample_rate=sample_rate,
        channels=channels,
        duration=duration,
        gain=gain,
        auto_normalize=auto_normalize,
        normalize_target_dbfs=normalize_target_dbfs,
        noise_reduction=noise_reduction,
    )


@app.command("h", help="Show compact help.", hidden=True)
@app.command("help", help="Show compact help. Alias for `nina h`.", hidden=True)
def nina_h() -> None:
    """Compact help. Use `nina <command> --help` for command-specific options."""
    _print_short_help()


def _prompt_init_vault_path(config_dir: Path, force: bool, vault_path: str | None) -> str | None:
    if vault_path is None:
        should_prompt = force or not get_config_path(config_dir).exists()
        if not should_prompt:
            config = load_effective_config(config_dir)
            should_prompt = not config.vault_path
        if should_prompt:
            vault_path = typer.prompt("Obsidian vault path")
    if vault_path is not None:
        vault_path = vault_path.strip()
        if not vault_path:
            console.print("[red]Vault path cannot be empty.[/red]")
            raise typer.Exit(1) from None
    return vault_path


@app.command("init", help="Initialize a Nina profile (config dir, token, vault, database).")
def init(
    profile: str = typer.Option("default", help="Profile name"),
    force: bool = typer.Option(False, help="Overwrite existing config"),
    vault_path: str | None = typer.Option(None, "--vault", help="Obsidian vault path to use."),
) -> None:
    config_dir = get_config_dir(profile)
    vault_path = _prompt_init_vault_path(config_dir, force, vault_path)
    initialize(profile=profile, config_dir=config_dir, force=force, vault_path=vault_path)
    config = load_effective_config(config_dir)
    console.print(f"Initialized Nina profile '{profile}' at {config_dir}")
    if config.vault_path:
        console.print(f"  Vault: {config.vault_path}")
    else:
        console.print("  Vault: not configured (run `nina config vault <path>`)")


def _print_version() -> None:
    from nina_core import __version__

    console.print(f"Nina {__version__}")


@app.command("v", help="Print the Nina version. Alias for `nina version`.", hidden=True)
def nina_v() -> None:
    _print_version()


@app.command("version", help="Print the Nina version.")
def version() -> None:
    _print_version()


@app.command("status", help="Show daemon health, LLM status, and config paths.")
def status(
    profile: str = typer.Option("default", help="Profile name"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Emit JSON output."),
) -> None:
    config_dir = get_config_dir(profile)
    config = load_effective_config(config_dir)

    daemon_state, running = _daemon_status(profile)
    warnings = _format_config_warnings(config)
    status_report = {
        "daemon": {
            "status": daemon_state,
            "running": running,
            "health": _daemon_health() if running else "offline",
        },
        "provider": _format_provider_auth_status(config),
        "llm": _format_llm_status(config),
        "transcription": _format_transcription_status(config),
        "meeting_pipeline": _format_meeting_pipeline_status(config),
        "codex": _format_codex_status() if running else "Codex: (unknown — daemon offline)",
        "warnings": warnings,
        "paths": {name: value for name, value in _configuration_entries(config_dir, config)},
    }

    if json_output:
        print_json(status_report)
        return

    console.print(status_report["daemon"]["status"])
    console.print(f"Health: {status_report['daemon']['health']}")
    console.print(status_report["provider"])
    console.print()
    console.print(status_report["llm"])
    console.print(status_report["transcription"])
    console.print(status_report["meeting_pipeline"])
    if running:
        console.print(status_report["codex"])
    if warnings:
        console.print()
        console.print("Warnings:")
        for warning in warnings:
            console.print(f"  - {warning}")
    console.print()
    console.print("Configuration paths:")
    for name, value in status_report["paths"].items():
        console.print(f"  {name}: {value}")


@app.command("doctor", help="Run a full health and configuration check.")
def doctor(
    profile: str = typer.Option("default", help="Profile name"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Emit JSON output."),
) -> None:
    config_dir = get_config_dir(profile)
    config = load_effective_config(config_dir)
    daemon_state, running = _daemon_status(profile)

    checks: dict[str, bool | str] = {
        "config_dir_exists": config_dir.exists(),
        "config_file_exists": (get_config_path(config_dir)).exists(),
        "token_exists": (get_token_path(config_dir)).exists(),
        "daemon_running": running,
        "database_exists": (get_database_path(config_dir)).exists(),
        "vault_configured": bool(config.vault_path),
        "vault_exists": Path(config.vault_path).exists() if config.vault_path else False,
        "daemon_health": _daemon_health() if running else "offline",
    }

    report = {
        "daemon": {"state": daemon_state, "running": running},
        "config": {"profile": profile, "config_dir": str(config_dir)},
        "checks": checks,
        "provider": {
            "auth": _format_provider_auth_status(config),
            "status": _format_llm_status(config),
        },
        "transcription": _format_transcription_status(config),
        "pipeline": _format_meeting_pipeline_status(config),
        "warnings": _format_config_warnings(config),
    }

    if json_output:
        print_json(report)
        return

    console.print("Checks:")
    for key, value in checks.items():
        if value is True or value in {"healthy", "ok"}:
            console.print(f"  OK   {key}: {value}")
        else:
            console.print(f"  WARN {key}: {value}")
    if report["warnings"]:
        console.print("\nWarnings:")
        for warning in report["warnings"]:
            console.print(f"  - {warning}")


@app.command("recent", help="Show a recent activity summary.")
def recent(
    limit: int = typer.Option(10, "--limit", "-n", help="Maximum records per section"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Emit JSON output."),
) -> None:
    def _safe_request(path: str) -> list[dict[str, Any]]:
        payload = try_request_json("GET", path, params={"limit": str(limit)}, timeout=2)
        if isinstance(payload, dict):
            return (
                payload.get("tasks", [])
                or payload.get("tickets", [])
                or payload.get("notes", [])
                or payload.get("runs", [])
                or payload.get("items", [])
                or payload.get("meetings", [])
                or []
            )
        if isinstance(payload, list):
            return payload
        return []

    recent_data: dict[str, list[dict[str, Any]]] = {
        "tasks": _safe_request("/tasks"),
        "tickets": _safe_request("/tickets"),
        "notes": _safe_request("/notes"),
        "job_runs": _safe_request("/job-runs"),
        "workflow_runs": _safe_request("/workflow-runs"),
        "meetings": _safe_request("/meetings"),
    }

    if json_output:
        print_json(recent_data)
        return

    if not any(recent_data.values()):
        console.print("No recent activity found.")
        return

    for section, rows in recent_data.items():
        if not rows:
            continue
        console.print(f"[bold]{section.title()}[/bold]")
        for row in rows:
            if section in {"tasks", "tickets"}:
                console.print(f"- {row.get('id')}: {row.get('title') or row.get('status')}")
            elif section == "notes":
                title = row.get("title") or row.get("path", "")
                console.print(f"- {row.get('path', '')}: {title}")
            else:
                console.print(f"- {row.get('id')}: {row.get('status', '')}")
        console.print()


@app.command("logs", help="Print the daemon log file (use --tail N for the last N lines).")
def logs(
    profile: str = typer.Option("default", help="Profile name"),
    tail: int | None = typer.Option(None, "--tail", help="Show only the last N lines"),
    task_id: str | None = typer.Option(None, "--task-id", help="Only show lines for a task id"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Continue printing new log lines"),
) -> None:
    config_dir = get_config_dir(profile)
    log_path = get_log_path(config_dir)
    if not log_path.exists():
        console.print(f"Log file not found: {log_path}")
        raise typer.Exit(1)

    def selected(lines: list[str]) -> list[str]:
        if not task_id:
            return lines
        task_token = f"task={task_id}"
        return [line for line in lines if task_token in line or task_id in line]

    lines = selected(log_path.read_text(errors="replace").splitlines())
    if tail is not None and tail >= 0:
        lines = lines[-tail:]

    console.print(f"Log file: {log_path}", soft_wrap=True)
    if lines:
        console.print("\n".join(lines))
    if not follow:
        return

    offset = log_path.stat().st_size
    try:
        while True:
            time.sleep(1.0)
            size = log_path.stat().st_size
            if size < offset:
                offset = 0
            if size == offset:
                continue
            with log_path.open("r", errors="replace") as handle:
                handle.seek(offset)
                chunk = handle.read()
                offset = handle.tell()
            new_lines = selected(chunk.splitlines())
            if new_lines:
                console.print("\n".join(new_lines))
    except KeyboardInterrupt:
        return


def main() -> None:
    if len(sys.argv) == 1:
        _print_short_help()
        return
    if sys.argv[1] == "h":
        _print_short_help()
        return
    if sys.argv[1] in {"v", "-v", "--version"}:
        _print_version()
        return
    app()


if __name__ == "__main__":
    main()
