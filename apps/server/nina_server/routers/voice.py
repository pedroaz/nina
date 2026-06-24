from __future__ import annotations

import asyncio
import concurrent.futures
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from nina_core.meetings.recorder import RecorderError
from nina_core.voice.manager import VoiceRecordingRequest

from ..dependencies import (
    _request_config,
    _request_config_dir,
    get_meeting_recorder,
    get_voice_recorder,
    get_voice_service,
)
from ..schemas import VoiceRecord, VoiceStop, VoiceTranscribe

router = APIRouter()


@router.post("/voice/record")
async def record_voice(request: Request, data: VoiceRecord) -> dict[str, Any]:
    meeting_recorder = get_meeting_recorder(request)
    if meeting_recorder.active_meeting_id() is not None:
        raise HTTPException(status_code=409, detail="A meeting recording is already active.")
    config = _request_config(request)
    recorder = get_voice_recorder(request)
    try:
        return recorder.start(
            config=config,
            config_dir=_request_config_dir(request),
            request=VoiceRecordingRequest(
                title=data.title,
                source=data.source,
                device=data.device,
                mic_device=data.mic_device,
                system_device=data.system_device,
                sample_rate=data.sample_rate,
                channels=data.channels,
                duration_seconds=data.duration_seconds,
                gain=data.gain,
                auto_normalize=data.auto_normalize,
                normalize_target_dbfs=data.normalize_target_dbfs,
                noise_reduction=data.noise_reduction,
            ),
        )
    except RecorderError as exc:
        status_code = 409 if "already active" in str(exc).lower() else 400
        raise HTTPException(status_code=status_code, detail=str(exc))


@router.get("/voice")
async def list_voice(
    request: Request,
    status: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    service = get_voice_service(request)
    return {"captures": service.list(status=status, limit=limit)}


@router.get("/voice/{capture_id}")
async def get_voice(request: Request, capture_id: str) -> dict[str, Any]:
    service = get_voice_service(request)
    capture = service.get(capture_id)
    if capture is None:
        raise HTTPException(status_code=404, detail="Not found")
    return capture


@router.post("/voice/{capture_id}/stop")
async def stop_voice(
    request: Request,
    capture_id: str,
    data: VoiceStop | None = None,
) -> dict[str, Any]:
    service = get_voice_service(request)
    recorder = get_voice_recorder(request)
    payload = data or VoiceStop()
    try:
        capture = recorder.stop(capture_id)
    except RecorderError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if capture is not None:
        if payload.error is not None:
            service.update_status(capture_id, error=payload.error)
            capture = service.get(capture_id) or capture
        return capture
    capture = service.stop(
        capture_id,
        duration_seconds=payload.duration_seconds,
        size_bytes=payload.size_bytes,
        error=payload.error,
    )
    if capture is None:
        raise HTTPException(status_code=404, detail="Not found")
    return capture


@router.post("/voice/{capture_id}/transcribe")
async def transcribe_voice(
    request: Request,
    capture_id: str,
    data: VoiceTranscribe | None = None,
) -> dict[str, Any]:
    service = get_voice_service(request)
    config = _request_config(request)
    payload = data or VoiceTranscribe()

    def _run() -> dict[str, Any]:
        return service.transcribe(
            capture_id,
            transcription_config=config.transcription,
            save_note=payload.save_note,
        )

    loop = asyncio.get_running_loop()
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            return await loop.run_in_executor(executor, _run)
    except RuntimeError as exc:
        status_code = 404 if "not found" in str(exc).lower() else 400
        raise HTTPException(status_code=status_code, detail=str(exc))
