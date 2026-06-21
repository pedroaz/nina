from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class SessionCreate(BaseModel):
    mode: Literal["chat", "agent"]
    title: str | None = None


class SessionMessageCreate(BaseModel):
    content: str
