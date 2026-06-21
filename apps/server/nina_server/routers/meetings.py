from __future__ import annotations

import asyncio
import concurrent.futures
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from nina_core.meetings.manager import RecordingRequest
from nina_core.meetings.recorder import RecorderError
from nina_core.workflows.runner import WorkflowRunner

from ..dependencies import (
    _active_config_path,
    _request_config,
    _request_config_dir,
    get_meeting_recorder,
    get_meeting_service,
)
from ..schemas import MeetingCreate, MeetingRecord, MeetingStop


router = APIRouter()


@router.post("/meetings")
async def create_meeting(request: Request, data: MeetingCreate) -> dict[str, Any]:
    service = get_meeting_service(request)
    return service.start(
        title=data.title,
        source=data.source,
        device_name=data.device_name,
        sample_rate=data.sample_rate,
        channels=data.channels,
        audio_format=data.audio_format,
    )


@router.post("/meetings/record")
async def record_meeting(request: Request, data: MeetingRecord) -> dict[str, Any]:
    config = _request_config(request)
    recorder = get_meeting_recorder(request)
    config_dir = _request_config_dir(request)
    try:
        return recorder.start(
            config=config,
            config_dir=config_dir,
            request=RecordingRequest(
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


@router.get("/meetings")
async def list_meetings(
    request: Request,
    status: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    service = get_meeting_service(request)
    return {"meetings": service.list(status=status, limit=limit)}


@router.get("/meetings/devices")
@router.get("/meetings-devices")
async def list_meeting_devices() -> dict[str, Any]:
    from nina_core.meetings.recorder import (
        list_input_devices,
        list_pulse_sources,
        list_soundcard_devices,
    )

    soundcard = list_soundcard_devices()
    return {
        "inputs": list_input_devices(),
        "pulse_sources": list_pulse_sources(),
        "soundcard_microphones": soundcard.get("microphones", []),
        "soundcard_speakers": soundcard.get("speakers", []),
    }


@router.get("/meetings/{meeting_id}")
async def get_meeting(request: Request, meeting_id: str) -> dict[str, Any]:
    service = get_meeting_service(request)
    meeting = service.get(meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail="Not found")
    return meeting


@router.post("/meetings/{meeting_id}/stop")
async def stop_meeting(
    request: Request,
    meeting_id: str,
    data: MeetingStop | None = None,
) -> dict[str, Any]:
    service = get_meeting_service(request)
    recorder = get_meeting_recorder(request)
    payload = data or MeetingStop()
    try:
        meeting = recorder.stop(meeting_id)
    except RecorderError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if meeting is not None:
        if payload.error is not None:
            service.update_status(meeting_id, error=payload.error)
            meeting = service.get(meeting_id) or meeting
        return meeting
    meeting = service.stop(
        meeting_id,
        duration_seconds=payload.duration_seconds,
        size_bytes=payload.size_bytes,
        error=payload.error,
    )
    if meeting is None:
        raise HTTPException(status_code=404, detail="Not found")
    return meeting


@router.post("/meetings/{meeting_id}/pipeline")
async def pipeline_meeting(request: Request, meeting_id: str) -> Any:
    """Run transcribe + summarize back-to-back for an existing meeting."""

    db_path = _active_config_path()

    def _run() -> dict[str, Any]:
        runner = WorkflowRunner(db_path, config=_request_config(request))
        return runner.run("meeting-pipeline", {"meeting_id": meeting_id, "input": {}})

    loop = asyncio.get_running_loop()
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        result = await loop.run_in_executor(executor, _run)
    if result.get("status") != "completed":
        return JSONResponse(status_code=400, content=result)
    return result


@router.get("/meetings/{meeting_id}/transcript")
async def get_meeting_transcript(request: Request, meeting_id: str) -> dict[str, Any]:
    service = get_meeting_service(request)
    meeting = service.get(meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail="Not found")
    transcript_path = meeting.get("transcript_path")
    if not transcript_path:
        return {"transcript": "", "status": meeting.get("status")}
    full = Path(transcript_path)
    if not full.is_file():
        return {"transcript": "", "status": meeting.get("status")}
    return {"transcript": full.read_text(), "status": meeting.get("status")}


@router.delete("/meetings/{meeting_id}")
async def delete_meeting(request: Request, meeting_id: str) -> dict[str, Any]:
    service = get_meeting_service(request)
    ok = service.delete(meeting_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Not found")
    return {"deleted": True}
