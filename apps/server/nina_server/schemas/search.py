from __future__ import annotations

from pydantic import BaseModel


class SearchQuery(BaseModel):
    query: str
    limit: int = 20


class AskQuery(BaseModel):
    question: str
    limit: int = 5


class SearchReindex(BaseModel):
    pass


class SearchOpen(BaseModel):
    path: str
