from __future__ import annotations

from typing import Any

import httpx

from ._http import NotConfiguredIntegration
from .base import CredentialField, IdentityResult, IntegrationInfo


TEAMS_INFO = IntegrationInfo(
    name="teams",
    display_name="Microsoft Teams",
    description="Microsoft Graph / Teams. Read-only identity ping for now.",
    docs_url="https://learn.microsoft.com/en-us/graph/api/user-get",
    auth_style="bearer_azure_ad",
    credential_fields=(
        CredentialField(
            name="access_token",
            label="Access token",
            secret=True,
            placeholder="Microsoft Graph access token",
        ),
    ),
)


class TeamsIntegration(NotConfiguredIntegration):
    info = TEAMS_INFO
    credentials_key = "teams"

    def _required_fields(self) -> tuple[str, ...]:
        return ("access_token",)

    async def _resolve_identity(self, creds: dict[str, Any]) -> IdentityResult:
        access_token = str(creds["access_token"])
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://graph.microsoft.com/v1.0/me",
                headers={"Authorization": f"Bearer {access_token}"},
            )
        response.raise_for_status()
        data = response.json()
        return IdentityResult(
            account_id=str(data.get("id", "")),
            display_name=str(data.get("displayName", "")),
            email=data.get("mail") or data.get("userPrincipalName"),
            workspace=None,
            raw=data,
        )
