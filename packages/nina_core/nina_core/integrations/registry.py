from __future__ import annotations

from typing import Iterable

from .base import Integration


_INTEGRATIONS: dict[str, Integration] = {}


def register_integration(integration: Integration) -> None:
    name = integration.info.name
    if not name:
        raise ValueError("Integration name is required")
    if name in _INTEGRATIONS:
        raise ValueError(f"Integration {name!r} is already registered")
    _INTEGRATIONS[name] = integration


def get_integration(name: str) -> Integration | None:
    return _INTEGRATIONS.get(name)


def list_integrations() -> list[Integration]:
    return list(_INTEGRATIONS.values())


def INTEGRATION_NAMES() -> Iterable[str]:
    return tuple(_INTEGRATIONS.keys())
