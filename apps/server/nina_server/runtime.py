from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import FastAPI

from nina_core.config import (
    ensure_vault_structure,
    NinaConfig,
    get_config_path,
    get_codex_log_path,
    get_runtime_path,
    get_token_path,
    read_token,
)
from nina_core.db import create_database
from nina_core.codex import CodexSupervisor
from nina_core.scheduler.service import SchedulerService
from nina_core.search.indexer import create_fts_table
from nina_core.search.watcher import make_watcher_if_enabled

from .db import DaemonDatabase

_ACTIVE_APP: FastAPI | None = None


def set_active_app(app: FastAPI | None) -> None:
    global _ACTIVE_APP
    _ACTIVE_APP = app


def get_active_app() -> FastAPI | None:
    return _ACTIVE_APP


@dataclass(slots=True)
class DaemonRuntime:
    app: FastAPI
    config_dir: Path
    config: NinaConfig
    scheduler: SchedulerService | None = None
    watcher: Any | None = None
    codex: CodexSupervisor | None = None
    meeting_recorder: Any | None = None
    voice_recorder: Any | None = None
    database: DaemonDatabase | None = None

    def attach(self) -> None:
        self.app.state.runtime = self
        self.app.state.profile = self.config.profile
        self.app.state.config_dir = self.config_dir
        self.app.state.config_path = get_config_path(self.config_dir)
        self.app.state.config = self.config
        self.app.state.scheduler = self.scheduler
        self.app.state.watcher = self.watcher
        self.app.state.codex = self.codex
        self.app.state.meeting_recorder = self.meeting_recorder
        self.app.state.voice_recorder = self.voice_recorder
        self.app.state.database = self.database
        try:
            self.app.state.token = read_token(get_token_path(self.config_dir))
        except Exception:  # noqa: BLE001
            self.app.state.token = None

    def configure(self, config_dir: Path, config: NinaConfig) -> NinaConfig:
        self.config_dir = config_dir
        self.config = config.with_resolved_paths(config_dir)
        self._ensure_database()
        self.attach()
        return self.config

    def reconfigure(self, config_dir: Path, config: NinaConfig) -> NinaConfig:
        previous = self.config
        self.config_dir = config_dir
        self.config = config.with_resolved_paths(config_dir)

        vault_changed = previous.vault_path != self.config.vault_path
        database_changed = previous.database_path != self.config.database_path
        watcher_changed = (
            vault_changed or previous.search.live_indexing != self.config.search.live_indexing
        )

        if vault_changed:
            ensure_vault_structure(Path(self.config.vault_path))

        if database_changed:
            self._prepare_database()
            self._ensure_database()
            self._restart_scheduler()
        else:
            self._ensure_database()

        if watcher_changed:
            self._restart_watcher()

        self.attach()
        return self.config

    def _prepare_database(self) -> None:
        create_database(self.config.database_path)
        create_fts_table(self.config.database_path)

    def _ensure_database(self) -> None:
        if self.database is None:
            self.database = DaemonDatabase(self.config.database_path)
        else:
            self.database.rebind(self.config.database_path)

    def _restart_scheduler(self) -> None:
        if self.scheduler is None:
            return
        self.scheduler.shutdown()
        self.scheduler = SchedulerService(self.config.database_path)
        self.scheduler.start()

    def _restart_watcher(self) -> None:
        if self.watcher is not None:
            try:
                self.watcher.stop()
            except Exception:  # noqa: BLE001
                pass
        self.watcher = make_watcher_if_enabled(
            self.config.database_path,
            self.config.vault_path,
            enabled=self.config.search.live_indexing,
        )
        if self.watcher is not None:
            self.watcher.start()

    def write_runtime_state(self) -> Path:
        runtime_path = get_runtime_path(self.config_dir)
        runtime_path.parent.mkdir(parents=True, exist_ok=True)
        runtime_path.write_text(
            json.dumps(
                {
                    "profile": self.config.profile,
                    "config_dir": str(self.config_dir),
                    "daemon_host": self.config.daemon_host,
                    "daemon_port": self.config.daemon_port,
                },
                indent=2,
            )
        )
        return runtime_path

    def start_services(self) -> None:
        ensure_vault_structure(Path(self.config.vault_path))
        self._prepare_database()
        self._ensure_database()

        self.scheduler = SchedulerService(self.config.database_path)
        self.scheduler.start()

        self.watcher = make_watcher_if_enabled(
            self.config.database_path,
            self.config.vault_path,
            enabled=self.config.search.live_indexing,
        )
        if self.watcher is not None:
            self.watcher.start()

        self.codex = CodexSupervisor(
            self.config_dir,
            self.config,
            get_codex_log_path(self.config_dir),
        )
        self.codex.start()
        self.attach()

    def shutdown_services(self) -> None:
        if self.codex is not None:
            try:
                self.codex.stop()
            except Exception:  # noqa: BLE001
                pass
        if self.scheduler is not None:
            self.scheduler.shutdown()
        if self.watcher is not None:
            try:
                self.watcher.stop()
            except Exception:  # noqa: BLE001
                pass
        if self.database is not None:
            self.database.dispose()


def apply_runtime_config(app: FastAPI, config_dir: Path, config: NinaConfig) -> NinaConfig:
    resolved = config.with_resolved_paths(config_dir)
    runtime = getattr(app.state, "runtime", None)
    if not isinstance(runtime, DaemonRuntime):
        runtime = DaemonRuntime(app=app, config_dir=config_dir, config=resolved)
    else:
        runtime.app = app
    resolved = runtime.configure(config_dir, resolved)
    app.state.runtime = runtime
    set_active_app(app)
    return resolved


def _changed_config_fields(previous: NinaConfig, updated: NinaConfig) -> list[str]:
    changed: list[str] = []
    if previous.vault_path != updated.vault_path:
        changed.append("vault_path")
    if previous.database_path != updated.database_path:
        changed.append("database_path")
    if previous.daemon_host != updated.daemon_host:
        changed.append("daemon_host")
    if previous.daemon_port != updated.daemon_port:
        changed.append("daemon_port")
    if previous.llm.provider != updated.llm.provider:
        changed.append("llm.provider")
    if previous.llm.model != updated.llm.model:
        changed.append("llm.model")
    if previous.llm.base_url != updated.llm.base_url:
        changed.append("llm.base_url")
    if previous.scheduler.daily_summary_time != updated.scheduler.daily_summary_time:
        changed.append("scheduler.daily_summary_time")
    if previous.log_level != updated.log_level:
        changed.append("log_level")
    if previous.transcription.backend != updated.transcription.backend:
        changed.append("transcription.backend")
    if previous.transcription.model != updated.transcription.model:
        changed.append("transcription.model")
    if previous.transcription.device != updated.transcription.device:
        changed.append("transcription.device")
    if previous.transcription.compute_type != updated.transcription.compute_type:
        changed.append("transcription.compute_type")
    if previous.transcription.language != updated.transcription.language:
        changed.append("transcription.language")
    if previous.meetings.default_source != updated.meetings.default_source:
        changed.append("meetings.default_source")
    if previous.meetings.auto_summarize != updated.meetings.auto_summarize:
        changed.append("meetings.auto_summarize")
    if previous.meetings.sample_rate != updated.meetings.sample_rate:
        changed.append("meetings.sample_rate")
    if previous.meetings.channels != updated.meetings.channels:
        changed.append("meetings.channels")
    if previous.meetings.open_command != updated.meetings.open_command:
        changed.append("meetings.open_command")
    if previous.meetings.play_command != updated.meetings.play_command:
        changed.append("meetings.play_command")
    if previous.meetings.auto_normalize != updated.meetings.auto_normalize:
        changed.append("meetings.auto_normalize")
    if previous.meetings.normalize_target_dbfs != updated.meetings.normalize_target_dbfs:
        changed.append("meetings.normalize_target_dbfs")
    if previous.meetings.noise_reduction != updated.meetings.noise_reduction:
        changed.append("meetings.noise_reduction")
    if previous.voice.global_hotkey_enabled != updated.voice.global_hotkey_enabled:
        changed.append("voice.global_hotkey_enabled")
    if previous.voice.global_hotkey != updated.voice.global_hotkey:
        changed.append("voice.global_hotkey")
    if previous.voice.insert_mode != updated.voice.insert_mode:
        changed.append("voice.insert_mode")
    if previous.voice.preserve_clipboard != updated.voice.preserve_clipboard:
        changed.append("voice.preserve_clipboard")
    if previous.codex.enabled != updated.codex.enabled:
        changed.append("codex.enabled")
    if previous.codex.binary_path != updated.codex.binary_path:
        changed.append("codex.binary_path")
    if previous.codex.host != updated.codex.host:
        changed.append("codex.host")
    if previous.codex.port != updated.codex.port:
        changed.append("codex.port")
    if previous.codex.username != updated.codex.username:
        changed.append("codex.username")
    if previous.codex.password_ref != updated.codex.password_ref:
        changed.append("codex.password_ref")
    if previous.codex.startup_timeout_seconds != updated.codex.startup_timeout_seconds:
        changed.append("codex.startup_timeout_seconds")
    if previous.codex.shutdown_timeout_seconds != updated.codex.shutdown_timeout_seconds:
        changed.append("codex.shutdown_timeout_seconds")
    return changed
