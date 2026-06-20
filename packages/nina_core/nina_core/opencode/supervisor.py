"""Supervise an `opencode serve` child process.

The Nina daemon owns a single opencode server for its lifetime. The
supervisor:

  * resolves the binary (configured path or `shutil.which("opencode")`)
  * spawns it with `OPENCODE_SERVER_PASSWORD`/`OPENCODE_SERVER_USERNAME`
    in the env and stdout/stderr redirected to `logs/opencode.log`
  * polls `GET /global/health` until the server is responsive, up to
    `startup_timeout_seconds`
  * tracks the child pid in `opencode.pid` and live config in
    `opencode.json` so CLI/TUI can read it without re-parsing
    `config.yaml`
  * on stop, SIGTERMs the child and falls back to SIGKILL after
    `shutdown_timeout_seconds`
  * on failure to start (missing binary, unhealthy, timeout), sets
    `state` accordingly and **does not raise** — the Nina daemon keeps
    serving, the TUI just shows "opencode: not installed" / "stopped".
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import signal
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .client import OpencodeClient, OpencodeError
from .models import (
    STATE_DISABLED,
    STATE_FAILED,
    STATE_NOT_INSTALLED,
    STATE_RUNNING,
    STATE_STARTING,
    STATE_STOPPED,
    Health,
    OpencodeStatus,
)
from .password import password_path

logger = logging.getLogger(__name__)


@dataclass
class OpencodeConfig:
    """The bits of `NinaConfig.opencode` the supervisor actually uses."""

    enabled: bool
    binary_path: str
    host: str
    port: int
    username: str
    password_ref: str
    startup_timeout_seconds: float
    shutdown_timeout_seconds: float

    @classmethod
    def from_settings(cls, settings: Any) -> "OpencodeConfig":
        oc = settings.opencode
        return cls(
            enabled=bool(oc.enabled),
            binary_path=str(oc.binary_path or ""),
            host=str(oc.host),
            port=int(oc.port),
            username=str(oc.username),
            password_ref=str(oc.password_ref),
            startup_timeout_seconds=float(oc.startup_timeout_seconds),
            shutdown_timeout_seconds=float(oc.shutdown_timeout_seconds),
        )


class OpencodeSupervisor:
    """Owns the `opencode serve` child for the lifetime of the daemon."""

    def __init__(self, config_dir: Path, settings: Any, log_path: Path) -> None:
        self.config_dir = config_dir
        self.config = OpencodeConfig.from_settings(settings)
        self.log_path = log_path
        self._proc: subprocess.Popen[bytes] | None = None
        self._state: str = STATE_STOPPED
        self._version: str | None = None
        self._last_error: str | None = None
        self._started_at: float | None = None
        self._lock = threading.Lock()

    @property
    def state(self) -> str:
        return self._state

    @property
    def pid(self) -> int | None:
        return self._proc.pid if self._proc is not None else None

    # --- lifecycle -----------------------------------------------------

    def start(self) -> None:
        with self._lock:
            if not self.config.enabled:
                self._state = STATE_DISABLED
                return

            binary = self._resolve_binary()
            if binary is None:
                self._state = STATE_NOT_INSTALLED
                self._last_error = (
                    "opencode binary not found on PATH; "
                    "install from https://opencode.ai or set opencode.binary_path"
                )
                logger.warning(self._last_error)
                return

            password = self._read_password()
            if password is None:
                self._state = STATE_FAILED
                self._last_error = f"opencode password file missing: {self.config.password_ref}"
                logger.error(self._last_error)
                return

            self._state = STATE_STARTING
            self._last_error = None
            try:
                self._spawn(binary, password)
                self._write_pid()
                self._write_runtime()
            except OSError as exc:
                self._state = STATE_FAILED
                self._last_error = f"failed to spawn opencode: {exc}"
                logger.error(self._last_error)
                return

            if not self._wait_healthy():
                self._cleanup_after_failed_start()
                return

            self._state = STATE_RUNNING
            self._started_at = time.monotonic()
            logger.info("opencode server is healthy (pid %s)", self.pid)

    def stop(self) -> None:
        with self._lock:
            self._terminate()
            if self._state not in (STATE_DISABLED, STATE_NOT_INSTALLED):
                self._state = STATE_STOPPED
            self._proc = None
            self._version = None
            self._started_at = None
            self._unlink_pid()
            self._unlink_runtime()

    # --- public API for /opencode/* -----------------------------------

    def status(self) -> OpencodeStatus:
        binary = self._resolve_binary() if self.config.enabled else None
        return OpencodeStatus(
            enabled=self.config.enabled,
            binary_installed=binary is not None,
            binary_path=binary or self.config.binary_path or "",
            state=self._state,
            version=self._version,
            host=self.config.host,
            port=self.config.port,
            uptime_seconds=(
                time.monotonic() - self._started_at
                if self._started_at and self._state == STATE_RUNNING
                else None
            ),
            pid=self.pid,
            last_error=self._last_error,
        )

    def client(self) -> OpencodeClient:
        """Build a fresh short-lived client. The caller closes it."""

        password = self._read_password() or ""
        return OpencodeClient(
            host=self.config.host,
            port=self.config.port,
            username=self.config.username,
            password=password,
        )

    # --- internals -----------------------------------------------------

    def _resolve_binary(self) -> str | None:
        candidate = self.config.binary_path.strip()
        if candidate:
            return candidate if os.path.isfile(candidate) else None
        return shutil.which("opencode")

    def _read_password(self) -> str | None:
        path = password_path(self.config_dir, self.config.password_ref)
        if not path.exists():
            return None
        return path.read_text().strip()

    def _spawn(self, binary: str, password: str) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        log_file = self.log_path.open("ab", buffering=0)
        env = os.environ.copy()
        env["OPENCODE_SERVER_USERNAME"] = self.config.username
        env["OPENCODE_SERVER_PASSWORD"] = password
        self._proc = subprocess.Popen(  # noqa: S603 - controlled input
            [
                binary,
                "serve",
                "--port",
                str(self.config.port),
                "--hostname",
                self.config.host,
            ],
            env=env,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )

    def _write_pid(self) -> None:
        if self._proc is None:
            return
        pid_path = self.config_dir / "opencode.pid"
        pid_path.parent.mkdir(parents=True, exist_ok=True)
        pid_path.write_text(str(self._proc.pid))

    def _unlink_pid(self) -> None:
        path = self.config_dir / "opencode.pid"
        path.unlink(missing_ok=True)

    def _write_runtime(self) -> None:
        path = self.config_dir / "opencode.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "host": self.config.host,
                    "port": self.config.port,
                    "username": self.config.username,
                    "pid": self.pid,
                }
            )
        )

    def _unlink_runtime(self) -> None:
        path = self.config_dir / "opencode.json"
        path.unlink(missing_ok=True)

    def _wait_healthy(self) -> bool:
        deadline = time.monotonic() + self.config.startup_timeout_seconds
        client = self.client()
        last_exc: str | None = None
        try:
            while time.monotonic() < deadline:
                if self._proc is not None and self._proc.poll() is not None:
                    last_exc = f"opencode exited early with code {self._proc.returncode}"
                    break
                try:
                    health = await_syncio(client.health())
                except OpencodeError as exc:
                    last_exc = str(exc)
                    time.sleep(0.2)
                    continue
                except Exception as exc:  # noqa: BLE001
                    last_exc = str(exc)
                    time.sleep(0.2)
                    continue
                if isinstance(health, Health) and health.healthy:
                    self._version = health.version
                    return True
                last_exc = f"unhealthy response: {health!r}"
                time.sleep(0.2)
        finally:
            # The startup-poll client is throwaway; close it cleanly.
            try:
                import asyncio

                asyncio.get_event_loop().run_until_complete(client.aclose())
            except Exception:  # noqa: BLE001
                pass

        self._state = STATE_FAILED
        self._last_error = (
            f"opencode did not become healthy within "
            f"{self.config.startup_timeout_seconds:.0f}s: {last_exc}"
        )
        logger.error(self._last_error)
        return False

    def _cleanup_after_failed_start(self) -> None:
        self._terminate()
        self._proc = None
        self._unlink_pid()
        self._unlink_runtime()

    def _terminate(self) -> None:
        if self._proc is None:
            return
        if self._proc.poll() is not None:
            return
        try:
            self._proc.send_signal(signal.SIGTERM)
        except ProcessLookupError:
            return
        try:
            self._proc.wait(timeout=self.config.shutdown_timeout_seconds)
        except subprocess.TimeoutExpired:
            try:
                self._proc.kill()
            except ProcessLookupError:
                pass


# `httpx.AsyncClient.health` is a coroutine; the supervisor polls in a
# sync thread. Bridge by running the coroutine on a fresh event loop
# each time. Using `asyncio.run` keeps the loop short-lived so the
# httpx connection pool is closed cleanly between polls.
def await_syncio(coro: Any) -> Any:
    import asyncio

    return asyncio.run(coro)
