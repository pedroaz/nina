from __future__ import annotations

from typing import Any

import httpx

from ._http import NotConfiguredIntegration
from .base import CredentialField, IdentityResult, IntegrationInfo


SLACK_INFO = IntegrationInfo(
    name="slack",
    display_name="Slack",
    description="Slack workspace using a bot token (xoxb-). Read-only identity ping for now.",
    docs_url="https://api.slack.com/methods/auth.test",
    auth_style="bearer_bot",
    credential_fields=(
        CredentialField(
            name="bot_token",
            label="Bot token",
            secret=True,
            placeholder="xoxb-...",
        ),
    ),
)


class SlackIntegration(NotConfiguredIntegration):
    info = SLACK_INFO
    credentials_key = "slack"

    def _required_fields(self) -> tuple[str, ...]:
        return ("bot_token",)

    async def _resolve_identity(self, creds: dict[str, Any]) -> IdentityResult:
        bot_token = str(creds["bot_token"])
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "https://slack.com/api/auth.test",
                headers={"Authorization": f"Bearer {bot_token}"},
            )
        response.raise_for_status()
        data = response.json()
        if not data.get("ok"):
            raise RuntimeError(f"slack auth.test failed: {data.get('error', 'unknown')}")
        return IdentityResult(
            account_id=str(data.get("user_id", "")),
            display_name=str(data.get("user", "")),
            email=None,
            workspace=str(data.get("team", "")) or None,
            raw=data,
        )
