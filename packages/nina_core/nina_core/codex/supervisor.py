"""Codex CLI supervisor.

This tracks only binary availability and liveness; no separate local process is
kept running for Codex.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .client import CodexClient, CodexError
from .models import (
    STATE_DISABLED,
    STATE_FAILED,
    STATE_NOT_INSTALLED,
    STATE_RUNNING,
    STATE_STARTING,
    STATE_STOPPED,
    CodexStatus,
)

logger = logging.getLogger(__name__)


@dataclass
class CodexConfig:
    """Subset of config used by the Codex-oriented supervisor."""

    enabled: bool
    binary_path: str
    host: str
    port: int
    username: str
    password_ref: str
    startup_timeout_seconds: float
    shutdown_timeout_seconds: float

    @classmethod
    def from_settings(cls, settings: Any) -> "CodexConfig":
        oc = settings.codex
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


class CodexSupervisor:
    """Compatibility layer for the Codex CLI supervisor API."""

    def __init__(self, config_dir: Path, settings: Any, log_path: Path) -> None:
        del log_path
        self.config_dir = config_dir
        self.config = CodexConfig.from_settings(settings)
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
        return None

    def start(self) -> None:
        with self._lock:
            if not self.config.enabled:
                self._state = STATE_DISABLED
                return

            binary = self._resolve_binary()
            if binary is None:
                self._state = STATE_NOT_INSTALLED
                self._last_error = (
                    "codex binary not found on PATH; install codex from openai.com/codex "
                    "or set codex.binary_path"
                )
                logger.warning(self._last_error)
                return

            self._state = STATE_STARTING
            self._last_error = None

            if not self._probe_binary(binary):
                return

            self._started_at = time.monotonic()
            self._state = STATE_RUNNING

    def stop(self) -> None:
        with self._lock:
            self._state = STATE_STOPPED
            self._version = None
            self._started_at = None

    def status(self) -> CodexStatus:
        binary = self._resolve_binary() if self.config.enabled else None
        return CodexStatus(
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

    def client(self) -> CodexClient:
        return CodexClient(
            host=self.config.host,
            port=self.config.port,
            username=self.config.username,
            password="",
            timeout=5.0,
            binary_path=self._resolve_binary() or self.config.binary_path,
        )

    def _resolve_binary(self) -> str | None:
        candidate = self.config.binary_path.strip()
        if candidate:
            return candidate if os.path.isfile(candidate) else None
        return shutil.which("codex")

    def _probe_binary(self, binary: str) -> bool:
        client = CodexClient(
            host=self.config.host,
            port=self.config.port,
            username=self.config.username,
            password="",
            timeout=5.0,
            binary_path=binary,
        )
        try:
            health = await_syncio(client.health())
            self._version = health.version
            return True
        except CodexError as exc:
            self._state = STATE_FAILED
            self._last_error = str(exc)
            logger.error(self._last_error)
            return False
        except Exception as exc:  # noqa: BLE001
            self._state = STATE_FAILED
            self._last_error = f"codex probe failed: {exc}"
            logger.error(self._last_error)
            return False


def await_syncio(coro: Any) -> Any:
    """Synchronous bridge used by the startup codepath."""

    return asyncio.run(coro)
