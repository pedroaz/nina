from __future__ import annotations

from .base import (
    IdentityResult,
    Integration,
    IntegrationInfo,
    IntegrationStatus,
    TestResult,
)
from .confluence import ConfluenceIntegration
from .credentials import (
    credentials_path,
    delete_credentials,
    get_integrations_dir,
    load_credentials,
    save_credentials,
)
from .jira import JiraIntegration
from .registry import (
    INTEGRATION_NAMES,
    get_integration,
    list_integrations,
    register_integration,
)
from .service import IntegrationService
from .slack import SlackIntegration
from .teams import TeamsIntegration


def _register_builtins() -> None:
    for integration in (
        ConfluenceIntegration(),
        JiraIntegration(),
        SlackIntegration(),
        TeamsIntegration(),
    ):
        register_integration(integration)


_register_builtins()


__all__ = [
    "IdentityResult",
    "Integration",
    "IntegrationInfo",
    "IntegrationStatus",
    "TestResult",
    "IntegrationService",
    "ConfluenceIntegration",
    "JiraIntegration",
    "SlackIntegration",
    "TeamsIntegration",
    "INTEGRATION_NAMES",
    "get_integration",
    "list_integrations",
    "register_integration",
    "credentials_path",
    "delete_credentials",
    "get_integrations_dir",
    "load_credentials",
    "save_credentials",
]
