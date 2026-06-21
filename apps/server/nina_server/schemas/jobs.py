from __future__ import annotations

from pydantic import BaseModel


class JobCreate(BaseModel):
    name: str
    workflow_name: str = "summarize-last-day"
    schedule: str
    enabled: bool = True


class JobUpdate(BaseModel):
    enabled: bool
