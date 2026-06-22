from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ResearchRunInput(BaseModel):
    topic: str
    search_mode: str | None = None


class WorkflowInput(BaseModel):
    input: dict[str, Any] = {}
