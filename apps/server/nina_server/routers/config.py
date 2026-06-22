from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request

from nina_core.config import ensure_vault_structure, get_config_path, merge_config
from nina_core.db import create_database
from nina_core.search.indexer import create_fts_table

from ..dependencies import _request_config, _request_config_dir
from ..runtime import DaemonRuntime, _changed_config_fields, apply_runtime_config
from ..schemas import (
    ConfigResponse,
    ConfigUpdate,
    LLMConfigResponse,
    MeetingsConfigResponse,
    CodexConfigResponse,
    ResearchConfigResponse,
    SchedulerConfigResponse,
    TranscriptionConfigResponse,
)


router = APIRouter()


def _config_response(config_dir: Path, config: Any) -> ConfigResponse:
    return ConfigResponse(
        profile=config.profile,
        config_dir=str(config_dir),
        config_path=str(get_config_path(config_dir)),
        vault_path=config.vault_path,
        database_path=config.database_path,
        daemon_host=config.daemon_host,
        daemon_port=config.daemon_port,
        llm=LLMConfigResponse(
            provider=config.llm.provider,
            model=config.llm.model,
            base_url=config.llm.base_url,
        ),
        research=ResearchConfigResponse(
            provider=config.research.provider,
            model=config.research.model,
            search_mode=config.research.search_mode,
            timeout_seconds=config.research.timeout_seconds,
        ),
        scheduler=SchedulerConfigResponse(daily_summary_time=config.scheduler.daily_summary_time),
        transcription=TranscriptionConfigResponse(
            backend=config.transcription.backend,
            model=config.transcription.model,
            device=config.transcription.device,
            compute_type=config.transcription.compute_type,
            language=config.transcription.language,
        ),
        meetings=MeetingsConfigResponse(
            default_source=config.meetings.default_source,
            auto_summarize=config.meetings.auto_summarize,
            sample_rate=config.meetings.sample_rate,
            channels=config.meetings.channels,
            open_command=config.meetings.open_command,
            play_command=config.meetings.play_command,
            default_gain=config.meetings.default_gain,
            auto_normalize=config.meetings.auto_normalize,
            normalize_target_dbfs=config.meetings.normalize_target_dbfs,
            noise_reduction=config.meetings.noise_reduction,
        ),
        codex=CodexConfigResponse(
            enabled=config.codex.enabled,
            binary_path=config.codex.binary_path,
            host=config.codex.host,
            port=config.codex.port,
            username=config.codex.username,
            password_ref=config.codex.password_ref,
            startup_timeout_seconds=config.codex.startup_timeout_seconds,
            shutdown_timeout_seconds=config.codex.shutdown_timeout_seconds,
        ),
        log_level=config.log_level,
    )


@router.get("/config", response_model=ConfigResponse)
async def get_config(request: Request) -> ConfigResponse:
    config_dir = _request_config_dir(request)
    config = _request_config(request)
    return _config_response(config_dir, config)


@router.patch("/config")
async def update_config(request: Request, data: ConfigUpdate) -> dict[str, Any]:
    config_dir = _request_config_dir(request)
    current = _request_config(request)
    patch = data.model_dump(exclude_unset=True, exclude_none=False)
    if not patch:
        return {
            "config": _config_response(config_dir, current).model_dump(),
            "changed_fields": [],
            "restart_required": False,
        }

    updated = merge_config(current, patch, config_dir)
    updated.save(get_config_path(config_dir))
    changed_fields = _changed_config_fields(current, updated)
    runtime = getattr(request.app.state, "runtime", None)
    if isinstance(runtime, DaemonRuntime):
        updated = runtime.reconfigure(config_dir, updated)
    else:
        updated = apply_runtime_config(request.app, config_dir, updated)
        ensure_vault_structure(Path(updated.vault_path))
        create_database(updated.database_path)
        create_fts_table(updated.database_path)

    restart_required = any(
        field
        in {
            "daemon_host",
            "daemon_port",
            "log_level",
            "codex.enabled",
            "codex.binary_path",
            "codex.host",
            "codex.port",
            "codex.username",
            "codex.password_ref",
            "codex.startup_timeout_seconds",
            "codex.shutdown_timeout_seconds",
        }
        for field in changed_fields
    )

    return {
        "config": _config_response(config_dir, updated).model_dump(),
        "changed_fields": changed_fields,
        "restart_required": restart_required,
    }
