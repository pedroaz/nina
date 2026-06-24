from __future__ import annotations

import sys
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Request

from nina_core.config import get_log_path
from nina_core.llm.transcription import check_transcription_status

from ..dependencies import _request_config, _request_config_dir


router = APIRouter()


def _transcription_status_payload(config: Any) -> dict[str, Any]:
    try:
        return asdict(check_transcription_status(config.transcription))
    except Exception as exc:  # noqa: BLE001
        transcription = getattr(config, "transcription", None)
        return {
            "backend": getattr(transcription, "backend", "unknown"),
            "model": getattr(transcription, "model", "unknown"),
            "device": getattr(transcription, "device", "unknown"),
            "compute_type": getattr(transcription, "compute_type", "unknown"),
            "available": False,
            "detail": str(exc),
            "provider_class": None,
        }


@router.get("/health")
async def health(request: Request) -> dict[str, Any]:
    config = _request_config(request)
    return {
        "status": "ok",
        "profile": config.profile,
        "vault_path": config.vault_path,
        "transcription": _transcription_status_payload(config),
    }


@router.get("/status")
async def status(request: Request) -> dict[str, Any]:
    config = _request_config(request)
    watcher = getattr(request.app.state, "watcher", None)
    scheduler = getattr(request.app.state, "scheduler", None)
    codex = getattr(request.app.state, "codex", None)
    codex_status = codex.status().model_dump() if codex is not None else None
    return {
        "profile": config.profile,
        "config_dir": str(getattr(request.app.state, "config_dir", "")),
        "config_path": str(getattr(request.app.state, "config_path", "")),
        "vault_path": config.vault_path,
        "database_path": config.database_path,
        "daemon_host": config.daemon_host,
        "daemon_port": config.daemon_port,
        "python_executable": sys.executable,
        "transcription": _transcription_status_payload(config),
        "watcher_enabled": bool(watcher is not None),
        "scheduler_running": bool(getattr(getattr(scheduler, "scheduler", None), "running", False)),
        "codex": codex_status,
    }


@router.get("/logs/daemon")
async def daemon_logs(
    request: Request,
    tail: int = 200,
    task_id: str | None = None,
) -> dict[str, Any]:
    log_path = get_log_path(_request_config_dir(request))
    if not log_path.exists():
        return {"path": str(log_path), "lines": [], "tail": tail, "task_id": task_id}

    lines = log_path.read_text(errors="replace").splitlines()
    if task_id:
        task_token = f"task={task_id}"
        lines = [line for line in lines if task_token in line or task_id in line]
    if tail >= 0:
        lines = lines[-tail:]
    return {"path": str(log_path), "lines": lines, "tail": tail, "task_id": task_id}


@router.get("/capabilities")
async def capabilities() -> dict[str, Any]:
    return {
        "routes": [
            "/tasks",
            "/tickets",
            "/sessions",
            "/notes",
            "/jobs",
            "/meetings",
            "/integrations",
            "/codex",
            "/workflows",
            "/search",
            "/llm",
        ]
    }
