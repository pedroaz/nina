from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from ..dependencies import get_session_service
from ..schemas import SessionCreate, SessionMessageCreate


router = APIRouter()


@router.get("/sessions")
async def list_sessions(request: Request, mode: str | None = None) -> list[dict[str, object]]:
    return get_session_service(request).list_sessions(mode)


@router.post("/sessions")
async def create_session(request: Request, data: SessionCreate) -> dict[str, object]:
    return get_session_service(request).create_session(data.mode, data.title)


@router.get("/sessions/{session_id}")
async def get_session(
    request: Request,
    session_id: str,
    messages_limit: int | None = None,
    messages_offset: int = 0,
) -> dict[str, object]:
    session = get_session_service(request).get_session(
        session_id,
        messages_limit=messages_limit,
        messages_offset=messages_offset,
    )
    if not session:
        raise HTTPException(status_code=404, detail="Not found")
    return session


@router.post("/sessions/{session_id}/messages")
async def send_session_message(
    request: Request,
    session_id: str,
    data: SessionMessageCreate,
    messages_limit: int | None = None,
    messages_offset: int = 0,
) -> dict[str, object]:
    service = get_session_service(request)
    try:
        return await service.send_message(
            session_id,
            data.content,
            messages_limit=messages_limit,
            messages_offset=messages_offset,
        )
    except RuntimeError as exc:
        message = str(exc)
        status = 404 if message.startswith("Unknown session") else 400
        raise HTTPException(status_code=status, detail=message)


@router.post("/sessions/{session_id}/cancel")
async def cancel_session(request: Request, session_id: str) -> dict[str, object]:
    service = get_session_service(request)
    ok = service.request_cancel(session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Not found")
    return {"cancelled": True}


@router.post("/sessions/{session_id}/clear-cancel")
async def clear_session_cancel(request: Request, session_id: str) -> dict[str, object]:
    service = get_session_service(request)
    service.clear_cancel(session_id)
    return {"cleared": True}
