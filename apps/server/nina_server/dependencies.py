from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
from typing import Iterator

from fastapi import Request
from sqlalchemy.orm import Session

from nina_core.config import NinaConfig, get_config_dir, load_effective_config
from nina_core.db.engine import make_engine, make_session
from nina_core.integrations.service import IntegrationService
from nina_core.notes.service import NoteService
from nina_core.obsidian.service import ObsidianService
from nina_core.scheduler.service import SchedulerService
from nina_core.sessions.service import SessionService
from nina_core.meetings.manager import MeetingRecordingManager
from nina_core.meetings.service import MeetingService

from .runtime import DaemonRuntime, get_active_app


def _request_config_dir(request: Request) -> Path:
    config_dir = getattr(request.app.state, "config_dir", None)
    if config_dir is not None:
        return Path(config_dir)
    profile = getattr(request.app.state, "profile", os.environ.get("NINA_PROFILE", "default"))
    return get_config_dir(str(profile))


def _request_config(request: Request) -> NinaConfig:
    config = getattr(request.app.state, "config", None)
    if isinstance(config, NinaConfig):
        return config
    config_dir = _request_config_dir(request)
    return load_effective_config(config_dir)


def _active_config() -> NinaConfig | None:
    app = get_active_app()
    if app is None:
        return None
    config = getattr(app.state, "config", None)
    if isinstance(config, NinaConfig):
        return config
    return None


def _active_config_path() -> str:
    config = _active_config()
    if config is not None:
        return str(config.database_path)
    return os.environ.get("NINA_DATABASE_PATH", "")


def _active_vault_path() -> str:
    config = _active_config()
    if config is not None:
        return str(config.vault_path)
    return os.environ.get("NINA_VAULT_PATH", "")


def get_db() -> Session:
    app = get_active_app()
    if app is not None:
        runtime = getattr(app.state, "runtime", None)
        if isinstance(runtime, DaemonRuntime) and runtime.database is not None:
            return runtime.database.session()
        database = getattr(app.state, "database", None)
        if database is not None and hasattr(database, "session"):
            return database.session()

    db_path = _active_config_path()
    engine = make_engine(db_path)
    SessionLocal = make_session(engine)
    return SessionLocal()


@contextmanager
def get_db_session() -> Iterator[Session]:
    """Create and automatically close a temporary SQLAlchemy session."""

    db = get_db()
    try:
        yield db
    finally:
        db.close()


def get_obsidian() -> ObsidianService:
    return ObsidianService(_active_vault_path())


def get_scheduler(request: Request) -> SchedulerService:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is not None and getattr(runtime, "scheduler", None) is not None:
        return runtime.scheduler
    scheduler = getattr(request.app.state, "scheduler", None)
    if scheduler is not None:
        return scheduler
    return SchedulerService(_active_config_path())


def get_session_service(request: Request) -> SessionService:
    config = _request_config(request)
    return SessionService(
        _active_config_path(),
        _active_vault_path(),
        llm_config=config.llm,
        codex_binary_path=config.codex.binary_path,
        search_config=config.search,
    )


def get_note_service(request: Request) -> NoteService:
    return NoteService(
        _active_config_path(),
        _active_vault_path(),
    )


def get_meeting_service(request: Request) -> MeetingService:
    config = _request_config(request)
    config_dir = _request_config_dir(request)
    return MeetingService(
        config.database_path,
        config_dir / "recordings",
        str(config.vault_path),
    )


def get_meeting_recorder(request: Request) -> MeetingRecordingManager:
    recorder = getattr(request.app.state, "meeting_recorder", None)
    if recorder is None:
        runtime = getattr(request.app.state, "runtime", None)
        if runtime is not None and getattr(runtime, "meeting_recorder", None) is not None:
            recorder = runtime.meeting_recorder
        else:
            recorder = MeetingRecordingManager()
        request.app.state.meeting_recorder = recorder
        if runtime is not None:
            runtime.meeting_recorder = recorder
    return recorder


def get_integration_service(request: Request) -> IntegrationService:
    config = _request_config(request)
    return IntegrationService(config.database_path, config_dir=_request_config_dir(request))
