from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from sqlalchemy.orm import Session

from nina_core.config.settings import SearchConfig
from nina_core.llm.provider import ToolDefinition
from nina_core.obsidian.service import ObsidianService


@dataclass
class ToolContext:
    db_path: str
    vault_path: Path
    db: Session
    obsidian: ObsidianService
    session_id: str | None = None
    embeddings: Any | None = None
    search_config: SearchConfig | None = None


ToolHandler = Callable[[ToolContext, dict[str, Any]], dict[str, Any]]


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: ToolHandler
    read_only: bool = True


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if spec.name in self._tools:
            raise ValueError(f"Tool '{spec.name}' is already registered")
        if spec.parameters.get("type", "object") != "object":
            raise ValueError(
                f"Tool '{spec.name}' parameters must have type='object' (got {spec.parameters.get('type')!r})"
            )
        self._tools[spec.name] = spec

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return sorted(self._tools)

    def definitions(self, *, read_only: bool | None = None) -> list[ToolDefinition]:
        out: list[ToolDefinition] = []
        for name in self.names():
            spec = self._tools[name]
            if read_only is True and not spec.read_only:
                continue
            out.append(
                ToolDefinition(
                    name=spec.name,
                    description=spec.description,
                    parameters=spec.parameters,
                )
            )
        return out

    def execute(self, name: str, args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        spec = self._tools.get(name)
        if spec is None:
            return {"error": f"Unknown tool '{name}'"}
        try:
            result = spec.handler(ctx, args or {})
            if not isinstance(result, dict):
                result = {"result": result}
            return result
        except Exception as exc:  # surface errors back to the model
            return {"error": f"{type(exc).__name__}: {exc}"}


def _string_schema(
    properties: dict[str, dict[str, Any]], required: list[str] | None = None
) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": False,
    }
