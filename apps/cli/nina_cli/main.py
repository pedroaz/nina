import json
import os
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

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
from nina_core.llm.provider import codex_auth_status

from .api import api_base, request
from .chat_commands import chat_app
from .config_commands import config_app
from .job_commands import job_app
from .kanban_commands import kanban_app
from .llm_commands import llm_app
from .meeting_commands import meeting_app, record_meeting
from .notes_commands import note_app
from .project_commands import project_app
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
        "  [cyan]nina mt t <id>[/cyan]       transcribe a meeting (local faster-whisper)\n"
        "  [cyan]nina mt m <id>[/cyan]       summarize a meeting (LLM)\n"
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
        "  k = kanban               j = job                 c = config\n"
        "  rch = research           s = search              ll = llm\n"
        "\n"
        "[bold]Meeting subcommands[/bold] (via `nina mt ...`):\n"
        "  ls = list    t = transcribe    m = summarize    s = stop\n"
        "  o = open     p = play          rm = delete      x = show\n"
        "\n"
        "[bold]Run[/bold] [cyan]nina <command> --help[/cyan] [bold]for options.[/bold]"
    )


app = typer.Typer(
    help="Nina CLI - local-first personal operations platform. Try `nina r` to record a meeting.",
    no_args_is_help=False,
    add_completion=False,
)


def _add_alias(parent: typer.Typer, sub_app: typer.Typer, alias: str) -> None:
    """Register a hidden sub-app alias so `nina <alias>` works but doesn't clutter help."""
    parent.add_typer(sub_app, name=alias, hidden=True)


daemon_app = typer.Typer(help="Daemon commands")
app.add_typer(daemon_app, name="daemon")
_add_alias(app, daemon_app, "d")
app.add_typer(chat_app, name="chat")
app.add_typer(config_app, name="config")
_add_alias(app, config_app, "c")
app.add_typer(note_app, name="note")
_add_alias(app, note_app, "n")
app.add_typer(project_app, name="project")
_add_alias(app, project_app, "p")
app.add_typer(providers_app, name="providers")
app.add_typer(task_app, name="task")
app.add_typer(ticket_app, name="ticket")
_add_alias(app, ticket_app, "tk")
app.add_typer(kanban_app, name="kanban")
_add_alias(app, kanban_app, "k")
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


def _server_command() -> list[str]:
    server = shutil.which("nina-server")
    if server:
        return [server]
    return [sys.executable, "-m", "nina_server.main"]


def _daemon_popen_kwargs() -> dict[str, int | bool]:
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
            "Audio source: mic (default), system (sink monitor), or parec "
            "(explicit PulseAudio/PipeWire source via `--device`)"
        ),
    ),
    device: str | None = typer.Option(
        None, "-d", "--device", help="Audio device name or index (see `nina mt devices`)"
    ),
    sample_rate: int = typer.Option(
        0, "-r", "--sample-rate", help="Sample rate in Hz (default from config, usually 16000)"
    ),
    channels: int = typer.Option(
        0, "-c", "--channels", help="Channel count (default from config, usually 1)"
    ),
    duration: int | None = typer.Option(
        None, "-D", "--duration", help="Auto-stop after this many seconds"
    ),
    gain: float | None = typer.Option(
        None,
        "--gain",
        help=(
            "Linear gain applied after recording (e.g. 4.0 = +12 dB). "
            "Defaults to `meetings.default_gain` in config.yaml."
        ),
    ),
    auto_normalize: bool = typer.Option(
        False,
        "--auto-normalize",
        help="Auto-gain the WAV so its peak hits -3 dBFS.",
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
        sample_rate=sample_rate,
        channels=channels,
        duration=duration,
        gain=gain,
        auto_normalize=auto_normalize,
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


@app.command("version", help="Print the Nina version.")
def version() -> None:
    from nina_core import __version__

    console.print(f"Nina {__version__}")


@app.command("status", help="Show daemon health, Codex auth, and config paths.")
def status(
    profile: str = typer.Option("default", help="Profile name"),
) -> None:
    config_dir = get_config_dir(profile)
    config = load_effective_config(config_dir)

    daemon_state, running = _daemon_status(profile)
    console.print(daemon_state)
    console.print(f"Health: {_daemon_health() if running else 'offline'}")
    console.print(_format_codex_auth_status())
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
    if sys.argv[1] in {"-h", "--help"}:
        # Translate short/full help flags to the full typer help.
        sys.argv[1] = "--help"
    app()


if __name__ == "__main__":
    main()
