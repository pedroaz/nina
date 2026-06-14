import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import typer
from rich.console import Console

from nina_core.config import (
    get_config_dir,
    get_config_path,
    get_database_path,
    get_log_path,
    get_pid_path,
    get_token_path,
    get_vault_path,
    initialize,
    read_token,
)

from .api import request
from .job_commands import job_app
from .kanban_commands import kanban_app
from .project_commands import project_app
from .research_commands import research_app
from .task_commands import task_app
from .ticket_commands import ticket_app

console = Console()

app = typer.Typer(help="Nina CLI - local-first personal operations platform")


daemon_app = typer.Typer(help="Daemon commands")
app.add_typer(daemon_app, name="daemon")
app.add_typer(project_app, name="project")
app.add_typer(task_app, name="task")
app.add_typer(ticket_app, name="ticket")
app.add_typer(kanban_app, name="kanban")
app.add_typer(job_app, name="job")
app.add_typer(research_app, name="research")


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


@app.command("ask")
def ask(
    question: str,
    limit: int = typer.Option(5, help="Maximum source notes to use"),
) -> None:
    resp = request("POST", "/ask", json={"question": question, "limit": limit})
    data = resp.json()
    console.print(data["answer"])
    sources = data.get("sources", [])
    if sources:
        console.print("\nSources:")
        for source in sources:
            console.print("- {}".format(source["path"]))


@app.command()
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


@app.command()
def init(
    profile: str = typer.Option("default", help="Profile name"),
    force: bool = typer.Option(False, help="Overwrite existing config"),
) -> None:
    config_dir = get_config_dir(profile)
    initialize(profile=profile, force=force)
    console.print(f"Initialized Nina profile '{profile}' at {config_dir}")
    console.print(f"  Vault: {get_vault_path(config_dir)}")


@app.command()
def version() -> None:
    from nina_core import __version__

    console.print(f"Nina {__version__}")


def _get_env(profile: str) -> dict[str, str]:
    config_dir = get_config_dir(profile)
    token_path = get_token_path(config_dir)
    config_path = get_config_path(config_dir)
    if not config_path.exists():
        console.print("Run 'nina init' first.")
        raise typer.Exit(1)
    env = os.environ.copy()
    env["NINA_PROFILE"] = profile
    env["NINA_CONFIG_DIR"] = str(config_dir)
    env["NINA_TOKEN"] = read_token(token_path)
    env["NINA_VAULT_PATH"] = str(get_vault_path(config_dir))
    env["NINA_DATABASE_PATH"] = str(get_database_path(config_dir))
    return env


def _resolve_pid_path(profile: str) -> Path:
    return get_pid_path(get_config_dir(profile))


@daemon_app.command("start")
def daemon_start(
    profile: str = typer.Option("default", help="Profile name"),
) -> None:
    pid_path = _resolve_pid_path(profile)
    if pid_path.exists():
        pid = int(pid_path.read_text())
        if _process_exists(pid):
            console.print(f"Daemon already running (pid {pid})")
            return
        pid_path.unlink()
    env = _get_env(profile)
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


@daemon_app.command("stop")
def daemon_stop(
    profile: str = typer.Option("default", help="Profile name"),
) -> None:
    pid_path = _resolve_pid_path(profile)
    if not pid_path.exists():
        console.print("Daemon not running")
        return
    pid = int(pid_path.read_text())
    _terminate_process(pid)
    pid_path.unlink()
    console.print("Daemon stopped")


@daemon_app.command("status")
def daemon_status(
    profile: str = typer.Option("default", help="Profile name"),
) -> None:
    pid_path = _resolve_pid_path(profile)
    if not pid_path.exists():
        console.print("Daemon not running")
        return
    pid = int(pid_path.read_text())
    if _process_exists(pid):
        console.print(f"Daemon running (pid {pid})")
    else:
        pid_path.unlink()
        console.print("Daemon not running (stale pid)")


def main() -> None:
    app()
