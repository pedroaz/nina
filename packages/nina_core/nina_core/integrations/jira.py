from __future__ import annotations

import base64
from typing import Any

import httpx

from ._http import NotConfiguredIntegration
from .base import IdentityResult, IntegrationInfo


JIRA_INFO = IntegrationInfo(
    name="jira",
    display_name="Jira",
    description="Atlassian Jira (Cloud or Data Center). Read-only identity ping for now.",
    docs_url="https://developer.atlassian.com/cloud/jira/platform/rest/v3/intro/",
    auth_style="basic_email_token",
)


class JiraIntegration(NotConfiguredIntegration):
    info = JIRA_INFO
    credentials_key = "jira"

    def _required_fields(self) -> tuple[str, ...]:
        return ("base_url", "email", "api_token")

    async def _resolve_identity(self, creds: dict[str, Any]) -> IdentityResult:
        base_url = str(creds["base_url"]).rstrip("/")
        token = base64.b64encode(f"{creds['email']}:{creds['api_token']}".encode()).decode()
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{base_url}/rest/api/3/myself",
                headers={
                    "Authorization": f"Basic {token}",
                    "Accept": "application/json",
                },
            )
        response.raise_for_status()
        data = response.json()
        return IdentityResult(
            account_id=str(data.get("accountId", "")),
            display_name=str(data.get("displayName", "")),
            email=data.get("emailAddress"),
            workspace=base_url,
            raw=data,
        )
