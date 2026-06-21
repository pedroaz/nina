from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import typer

from nina_core.config import (
    NinaConfig,
    get_config_dir,
    get_config_path,
    get_log_path,
    get_pid_path,
    get_runtime_path,
    get_token_path,
    load_effective_config,
    read_token,
)

from .output import console

daemon_app = typer.Typer(help="Daemon commands")


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


def _resolve_pid_path(profile: str) -> Path:
    return get_pid_path(get_config_dir(profile))


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


def _get_env(profile: str) -> tuple[dict[str, str], NinaConfig]:
    config_dir = get_config_dir(profile)
    token_path = get_token_path(config_dir)
    config_path = get_config_path(config_dir)
    if not config_path.exists():
        console.print("Run 'nina init' first.")
        raise typer.Exit(1)
    config = load_effective_config(config_dir)
    env = os.environ.copy()
    env["NINA_PROFILE"] = profile
    env["NINA_CONFIG_DIR"] = str(config_dir)
    env["NINA_TOKEN"] = read_token(token_path)
    return env, config


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
    with log_path.open("a") as log_file:
        proc = subprocess.Popen(
            _server_command(),
            env=env,
            stdout=log_file,
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
    with log_path.open("a") as log_file:
        proc = subprocess.Popen(
            _server_command(),
            env=env,
            stdout=log_file,
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
