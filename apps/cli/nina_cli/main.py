import json
import os
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import typer
from rich.console import Console

from nina_core.config import (
    NinaConfig,
    get_config_dir,
    get_config_path,
    get_log_path,
    get_pid_path,
    get_runtime_path,
    get_token_path,
    get_vault_path,
    initialize,
    load_effective_config,
    read_token,
)
from nina_core.llm.provider import check_provider_status, codex_auth_status
from nina_core.llm.transcription import check_transcription_status

from .api import api_base, headers, request
from .chat_commands import chat_app
from .config_commands import config_app
from .integrations_commands import integrations_app
from .job_commands import job_app
from .setup_commands import setup_app
from .llm_commands import llm_app
from .meeting_commands import meeting_app, record_meeting
from .notes_commands import note_app
from .opencode_commands import opencode_app
from .providers_commands import providers_app
from .research_commands import research_app
from .search_commands import search_app
from .task_commands import task_app
from .ticket_commands import ticket_app

console = Console()


def _print_short_help() -> None:
    """Compact help for the top-level `nina` command."""

    console.print(
        "[bold]Nina[/bold] - local-first personal operations platform\n"
        "\n"
        "[bold]Most common[/bold]\n"
        '  [cyan]nina r  "title"[/cyan]      record a meeting (alias for `meeting record`)\n'
        "  [cyan]nina mt list[/cyan]         list meetings (alias for `meeting list`)\n"
        "  [cyan]nina mt stop[/cyan]         stop the active recording\n"
        "  [cyan]nina mt e <id>[/cyan]       transcribe + summarize a meeting (Ctrl+E in TUI)\n"
        "  [cyan]nina t[/cyan]               launch the TUI\n"
        '  [cyan]nina ask "q?"[/cyan]        ask a question over the vault\n'
        '  [cyan]nina search "q"[/cyan]      full-text search the vault\n'
        "  [cyan]nina config show[/cyan]     inspect settings\n"
        "\n"
        "[bold]Compact aliases[/bold]\n"
        "  r = meeting record       mt = meeting sub-app   h = compact help\n"
        "  help = compact help (alias for `h`)\n"
        "  t = tui                  d = daemon              -h = --help\n"
        "  n = note                 p = project             tk = ticket\n"
        "  j = job                  c = config\n"
        "  rch = research           s = search              ll = llm\n"
        "  int = integrations\n"
        "\n"
        "[bold]Meeting subcommands[/bold] (via `nina mt ...`):\n"
        "  ls = list    e = pipeline (transcribe + summarize)    s = stop\n"
        "  o = open     p = play          rm = delete      x = show\n"
        "\n"
        "[bold]Task subcommands[/bold] (via `nina task ...` or `nina tk ...`):\n"
        "  list / ls       create         show          type <id> <t>\n"
        "  classify <id>   run <id>       archive       unarchive     delete\n"
        "  board                                          (type-grouped view)\n"
        "\n"
        "[bold]Run[/bold] [cyan]nina <command> --help[/cyan] [bold]for options.[/bold]"
    )


app = typer.Typer(
    help="Nina CLI - local-first personal operations platform. Try `nina r` to record a meeting.",
    no_args_is_help=False,
    add_completion=False,
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


daemon_app = typer.Typer(help="Daemon commands")
app.add_typer(daemon_app, name="daemon")
_add_alias(app, daemon_app, "d")
app.add_typer(chat_app, name="chat")
app.add_typer(config_app, name="config")
_add_alias(app, config_app, "c")
app.add_typer(note_app, name="note")
_add_alias(app, note_app, "n")
app.add_typer(opencode_app, name="opencode")
_add_alias(app, opencode_app, "oc")
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
app.add_typer(research_app, name="research")
_add_alias(app, research_app, "rch")
app.add_typer(search_app, name="search")
_add_alias(app, search_app, "s")
app.add_typer(setup_app, name="setup")
app.add_typer(integrations_app, name="integrations")
_add_alias(app, integrations_app, "int")


def _resolve_tui_binary() -> Path | None:
    env_bin = os.environ.get("NINA_TUI_BIN")
    candidates: list[Path] = []
    if env_bin:
        candidates.append(Path(env_bin).expanduser())
    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            candidates.append(Path(local_app_data) / "Programs" / "Nina" / "bin" / "nina-tui.exe")
        candidates.append(Path.home() / ".nina" / "bin" / "nina-tui.exe")
    else:
        candidates.append(Path.home() / ".nina" / "bin" / "nina-tui")
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


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


def _server_command() -> list[str]:
    server = shutil.which("nina-server")
    if server:
        return [server]
    return [sys.executable, "-m", "nina_server.main"]


def _daemon_popen_kwargs() -> dict[str, Any]:
    if os.name == "nt":
        return {"creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)}
    return {"start_new_session": True}


def _process_exists(pid: int) -> bool:
    if os.name == "nt":
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}"],
            capture_output=True,
            text=True,
            check=False,
        )
        return str(pid) in result.stdout and "No tasks" not in result.stdout
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


def _terminate_process(pid: int) -> None:
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            check=False,
        )
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if not _process_exists(pid):
            return
        time.sleep(0.2)
    if _process_exists(pid):
        os.kill(pid, signal.SIGKILL)


def _read_pid(pid_path: Path) -> int | None:
    try:
        pid = int(pid_path.read_text().strip())
    except (OSError, ValueError):
        return None
    return pid if pid > 0 else None


def _daemon_status(profile: str) -> tuple[str, bool]:
    pid_path = _resolve_pid_path(profile)
    if not pid_path.exists():
        return "Daemon not running", False
    pid = _read_pid(pid_path)
    if pid is None:
        pid_path.unlink(missing_ok=True)
        return "Daemon not running (stale pid)", False
    if _process_exists(pid):
        return f"Daemon running (pid {pid})", True
    pid_path.unlink(missing_ok=True)
    return "Daemon not running (stale pid)", False


def _write_runtime_state(config_dir: Path, config: NinaConfig) -> None:
    runtime_path = get_runtime_path(config_dir)
    runtime_path.parent.mkdir(parents=True, exist_ok=True)
    runtime_path.write_text(
        json.dumps(
            {
                "profile": config.profile,
                "config_dir": str(config_dir),
                "daemon_host": config.daemon_host,
                "daemon_port": config.daemon_port,
            },
            indent=2,
        )
    )


def _daemon_health() -> str:
    try:
        resp = httpx.get(f"{api_base()}/health", timeout=2)
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, ValueError, TypeError):
        return "offline"
    status = data.get("status", "unknown")
    return str(status) if status is not None else "unknown"


def _configuration_entries(config_dir: Path, config: NinaConfig) -> list[tuple[str, str]]:
    return [
        ("Config dir", str(config_dir)),
        ("Config file", str(get_config_path(config_dir))),
        ("Token", str(get_token_path(config_dir))),
        ("Database", config.database_path),
        ("Vault", config.vault_path),
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
        parts = ["Codex OAuth connected"]
        if status.account_id:
            parts.append(f"account {status.account_id}")
        if status.expires_at:
            expires = datetime.fromtimestamp(status.expires_at / 1000, tz=timezone.utc).astimezone()
            parts.append(f"expires {expires.isoformat(timespec='seconds')}")
        return "LLM auth: " + ", ".join(parts)
    detail = status.detail or "unknown error"
    return f"LLM auth: disconnected ({detail})"


def _format_provider_auth_status(config: NinaConfig) -> str:
    provider = (config.llm.provider or "").lower()
    if provider == "openai":
        has_key = bool(config.llm.api_key or os.environ.get("OPENAI_API_KEY"))
        if has_key:
            return "LLM auth: OpenAI API key configured"
        return "LLM auth: disconnected (OPENAI_API_KEY is not set in the environment)"
    if provider == "codex":
        return _format_codex_auth_status()
    if provider in {"ollama", "openai_compatible", "llamacpp", "vllm", "lmstudio"}:
        return f"LLM auth: not required for {provider}"
    return f"LLM auth: provider {provider or 'unknown'}"


def _format_llm_status(config: NinaConfig) -> str:
    """Show the LLM provider's reachability, used by `nina status`.

    For local runtimes (Ollama, llama.cpp) it pings the server. For Codex
    and OpenAI it just reports whether credentials are configured. Never
    burns a real LLM request.
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
    elif status.provider in {"openai", "codex"}:
        bits.append("disconnected")
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
    user can tell at a glance whether `Ctrl+E` / `nina meeting pipeline` will
    work end-to-end.
    """
    try:
        llm = check_provider_status(config.llm, timeout=1.0)
        tr = check_transcription_status(config.transcription)
    except Exception as exc:  # noqa: BLE001
        return f"Meeting pipeline: error ({exc})"
    if tr.available and llm.reachable and (llm.model_present or not llm.model):
        return "Meeting pipeline: ready (Ctrl+E / nina meeting pipeline <id>)"
    issues: list[str] = []
    if not tr.available:
        issues.append(f"transcription ({tr.backend}) not ready")
    if not llm.reachable:
        issues.append(f"LLM ({llm.provider}) not reachable")
    elif llm.model and not llm.model_present:
        issues.append(f"LLM model {llm.model!r} not present")
    return f"Meeting pipeline: degraded ({'; '.join(issues)})"


def _format_opencode_status() -> str:
    """Surface the supervised opencode server state in `nina status`.

    Goes through the daemon's `/opencode/status` endpoint so we don't need
    to know whether the daemon was started in this process. Falls back to
    a clean "not running" line if the daemon is offline.
    """
    try:
        resp = httpx.get(f"{api_base()}/opencode/status", headers=headers(), timeout=2)
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, ValueError, TypeError):
        return "OpenCode: (unknown — daemon offline)"
    state = data.get("state", "unknown")
    if state == "running":
        version = data.get("version") or "?"
        host = data.get("host", "?")
        port = data.get("port", "?")
        return f"OpenCode: {version} (running) @ http://{host}:{port}"
    if state == "disabled":
        return "OpenCode: disabled (set `opencode.enabled: true` in config)"
    if state == "not_installed":
        return "OpenCode: not installed (binary not on PATH)"
    detail = data.get("last_error") or ""
    if detail:
        return f"OpenCode: {state} — {detail}"
    return f"OpenCode: {state}"


def _format_config_warnings(config: NinaConfig) -> list[str]:
    warnings: list[str] = []
    provider = (config.llm.provider or "").lower()
    llm_status = check_provider_status(config.llm, timeout=1.0)
    transcription = check_transcription_status(config.transcription)

    if provider == "openai" and not (config.llm.api_key or os.environ.get("OPENAI_API_KEY")):
        warnings.append("OpenAI provider selected but OPENAI_API_KEY is not set")
    elif provider == "codex" and not llm_status.reachable:
        warnings.append(f"Codex auth disconnected ({llm_status.detail or 'unknown error'})")
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


@app.command("t", help="Launch the OpenTUI terminal UI.")
@app.command("tui", help="Launch the OpenTUI terminal UI.")
def tui() -> None:
    tui_bin = _resolve_tui_binary()
    if tui_bin:
        os.execv(str(tui_bin), [str(tui_bin)])

    cli_dir = os.path.dirname(os.path.abspath(__file__))
    tui_dir = os.path.join(cli_dir, "../../tui")
    if os.path.exists(os.path.join(tui_dir, "src", "main.ts")):
        os.chdir(tui_dir)
        os.execvp("bun", ["bun", "run", "src/main.ts"])

    console.print("Nina TUI is not installed. Re-run the installer or set NINA_TUI_BIN.")
    raise typer.Exit(1)


@app.command("r", help="Record a meeting. Alias for `nina meeting record`.")
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


@app.command("h", help="Show compact help.")
@app.command("help", help="Show compact help. Alias for `nina h`.")
def nina_h() -> None:
    """Compact help. Use `nina <command> --help` for command-specific options."""
    _print_short_help()


@app.command("init", help="Initialize a Nina profile (config dir, token, vault, database).")
def init(
    profile: str = typer.Option("default", help="Profile name"),
    force: bool = typer.Option(False, help="Overwrite existing config"),
) -> None:
    config_dir = get_config_dir(profile)
    initialize(profile=profile, force=force)
    console.print(f"Initialized Nina profile '{profile}' at {config_dir}")
    console.print(f"  Vault: {get_vault_path(config_dir)}")


def _print_version() -> None:
    from nina_core import __version__

    console.print(f"Nina {__version__}")


@app.command("v", help="Print the Nina version. Alias for `nina version`.")
def nina_v() -> None:
    _print_version()


@app.command("version", help="Print the Nina version.")
def version() -> None:
    _print_version()


@app.command("status", help="Show daemon health, LLM status, and config paths.")
def status(
    profile: str = typer.Option("default", help="Profile name"),
) -> None:
    config_dir = get_config_dir(profile)
    config = load_effective_config(config_dir)

    daemon_state, running = _daemon_status(profile)
    console.print(daemon_state)
    console.print(f"Health: {_daemon_health() if running else 'offline'}")
    console.print(_format_provider_auth_status(config))
    console.print()
    console.print(_format_llm_status(config))
    console.print(_format_transcription_status(config))
    console.print(_format_meeting_pipeline_status(config))
    if running:
        console.print(_format_opencode_status())
    warnings = _format_config_warnings(config)
    if warnings:
        console.print()
        console.print("Warnings:")
        for warning in warnings:
            console.print(f"  - {warning}")
    console.print()
    console.print("Configuration paths:")
    for name, value in _configuration_entries(config_dir, config):
        console.print(f"  {name}: {value}")


@app.command("logs", help="Print the daemon log file (use --tail N for the last N lines).")
def logs(
    profile: str = typer.Option("default", help="Profile name"),
    tail: int | None = typer.Option(None, "--tail", help="Show only the last N lines"),
) -> None:
    config_dir = get_config_dir(profile)
    log_path = get_log_path(config_dir)
    if not log_path.exists():
        console.print(f"Log file not found: {log_path}")
        raise typer.Exit(1)

    lines = log_path.read_text().splitlines()
    if tail is not None and tail >= 0:
        lines = lines[-tail:]

    console.print(f"Log file: {log_path}", soft_wrap=True)
    if lines:
        console.print("\n".join(lines))


def _get_env(profile: str) -> tuple[dict[str, str], NinaConfig]:
    config_dir = get_config_dir(profile)
    token_path = get_token_path(config_dir)
    config_path = get_config_path(config_dir)
    if not config_path.exists():
        console.print("Run 'nina init' first.")
        raise typer.Exit(1)
    config = load_effective_config(config_dir)
    env = os.environ.copy()
    # Bootstrap-only env vars. All other settings live in `config.yaml` and
    # are read by the daemon via `load_effective_config`. Keep this list
    # minimal: profile + config dir + auth token.
    env["NINA_PROFILE"] = profile
    env["NINA_CONFIG_DIR"] = str(config_dir)
    env["NINA_TOKEN"] = read_token(token_path)
    return env, config


def _resolve_pid_path(profile: str) -> Path:
    return get_pid_path(get_config_dir(profile))


@daemon_app.command("start", help="Start the local Nina daemon.")
def daemon_start(
    profile: str = typer.Option("default", help="Profile name"),
) -> None:
    pid_path = _resolve_pid_path(profile)
    if pid_path.exists():
        pid = _read_pid(pid_path)
        if pid is not None and _process_exists(pid):
            console.print(f"Daemon already running (pid {pid})")
            return
        pid_path.unlink(missing_ok=True)
    env, config = _get_env(profile)
    _write_runtime_state(get_config_dir(profile), config)
    log_path = get_log_path(get_config_dir(profile))
    log_path.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(
        _server_command(),
        env=env,
        stdout=log_path.open("a"),
        stderr=subprocess.STDOUT,
        **_daemon_popen_kwargs(),
    )
    pid_path.write_text(str(proc.pid))
    console.print(f"Daemon started (pid {proc.pid})")


@daemon_app.command("stop", help="Stop the local Nina daemon.")
def daemon_stop(
    profile: str = typer.Option("default", help="Profile name"),
) -> None:
    pid_path = _resolve_pid_path(profile)
    if not pid_path.exists():
        console.print("Daemon not running")
        return
    pid = _read_pid(pid_path)
    if pid is None:
        pid_path.unlink(missing_ok=True)
        console.print("Daemon not running")
        return
    _terminate_process(pid)
    pid_path.unlink(missing_ok=True)
    console.print("Daemon stopped")


@daemon_app.command("r", help="Restart the local Nina daemon.")
@app.command("restart", help="Restart the local Nina daemon.")
def daemon_restart(
    profile: str = typer.Option("default", help="Profile name"),
) -> None:
    pid_path = _resolve_pid_path(profile)
    if pid_path.exists():
        pid = _read_pid(pid_path)
        if pid is not None and _process_exists(pid):
            _terminate_process(pid)
            pid_path.unlink(missing_ok=True)
            console.print("Daemon stopped")
        else:
            pid_path.unlink(missing_ok=True)
    env, config = _get_env(profile)
    _write_runtime_state(get_config_dir(profile), config)
    log_path = get_log_path(get_config_dir(profile))
    log_path.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(
        _server_command(),
        env=env,
        stdout=log_path.open("a"),
        stderr=subprocess.STDOUT,
        **_daemon_popen_kwargs(),
    )
    pid_path.write_text(str(proc.pid))
    console.print(f"Daemon restarted (pid {proc.pid})")


@daemon_app.command("status", help="Print whether the local Nina daemon is running.")
def daemon_status(
    profile: str = typer.Option("default", help="Profile name"),
) -> None:
    daemon_state, _ = _daemon_status(profile)
    console.print(daemon_state)


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
    if sys.argv[1] in {"-h", "--help"}:
        # Translate short/full help flags to the full typer help.
        sys.argv[1] = "--help"
    app()


if __name__ == "__main__":
    main()
