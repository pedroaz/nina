from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable


class IntegrationStatus(str, Enum):
    NOT_CONFIGURED = "not_configured"
    OK = "ok"
    FAILED = "failed"


@dataclass
class IntegrationInfo:
    name: str
    display_name: str
    description: str
    docs_url: str
    auth_style: str


@dataclass
class IdentityResult:
    account_id: str
    display_name: str
    email: str | None = None
    workspace: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)  # type: ignore[arg-type]

    def to_dict(self) -> dict[str, Any]:
        return {
            "account_id": self.account_id,
            "display_name": self.display_name,
            "email": self.email,
            "workspace": self.workspace,
        }


@dataclass
class TestResult:
    status: IntegrationStatus
    latency_ms: int
    identity: IdentityResult | None
    error: str | None
    tested_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "latency_ms": self.latency_ms,
            "identity": self.identity.to_dict() if self.identity else None,
            "error": self.error,
            "tested_at": self.tested_at,
        }


@runtime_checkable
class Integration(Protocol):
    info: IntegrationInfo

    def is_configured(self) -> bool: ...

    async def test(self) -> TestResult: ...
