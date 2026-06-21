from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from nina_core.llm.provider import LLMRequest, LLMService
from nina_core.models.models import LLMInteraction

from ..dependencies import _active_config_path, _request_config, get_db_session


router = APIRouter()


@router.post("/llm/complete")
async def llm_complete(request: Request, data: LLMRequest) -> dict[str, Any]:
    db_path = _active_config_path()
    config = _request_config(request)
    service = LLMService(db_path, config=config.llm, codex_binary_path=config.codex.binary_path)
    response = await service.complete(data)
    return {"response": response.response, "model": response.model, "provider": response.provider}


@router.get("/llm/interactions")
async def llm_interactions(request: Request) -> list[dict[str, Any]]:
    with get_db_session() as db:
        interactions = db.query(LLMInteraction).order_by(LLMInteraction.created_at.desc()).all()
        return [
            {
                "id": interaction.id,
                "provider": interaction.provider,
                "model": interaction.model,
                "purpose": interaction.purpose,
                "status": interaction.status,
                "created_at": interaction.created_at,
            }
            for interaction in interactions
        ]
