from __future__ import annotations

from pydantic import BaseModel


class IntegrationCredentialsUpdate(BaseModel):
    credentials: dict[str, object]
