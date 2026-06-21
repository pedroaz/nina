from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ResearchRunInput(BaseModel):
    topic: str


class WorkflowInput(BaseModel):
    input: dict[str, Any] = {}
