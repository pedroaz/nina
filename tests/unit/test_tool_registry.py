from __future__ import annotations

import pytest
from nina_core.llm.tools import ToolContext, ToolRegistry, ToolSpec, _string_schema


def _ctx(tmp_path) -> ToolContext:
    return ToolContext(
        db_path=str(tmp_path / "nina.db"),
        vault_path=tmp_path,
        db=None,  # type: ignore[arg-type]
        obsidian=None,  # type: ignore[arg-type]
    )


def test_register_and_lookup() -> None:
    registry = ToolRegistry()

    def handler(ctx: ToolContext, args: dict) -> dict:
        return {"echoed": args.get("value")}

    registry.register(
        ToolSpec(
            name="echo",
            description="Echoes a value back",
            parameters=_string_schema({"value": {"type": "string"}}),
            handler=handler,
        )
    )
    assert registry.get("echo") is not None
    assert "echo" in registry.names()


def test_definitions_read_only_filter() -> None:
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="r",
            description="read",
            parameters=_string_schema({}),
            handler=lambda c, a: {},
            read_only=True,
        )
    )
    registry.register(
        ToolSpec(
            name="w",
            description="write",
            parameters=_string_schema({}),
            handler=lambda c, a: {},
            read_only=False,
        )
    )
    assert {d.name for d in registry.definitions(read_only=True)} == {"r"}
    assert {d.name for d in registry.definitions(read_only=False)} == {"r", "w"}
    assert {d.name for d in registry.definitions()} == {"r", "w"}


def test_duplicate_registration_raises(tmp_path) -> None:
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="x",
            description="x",
            parameters=_string_schema({}),
            handler=lambda c, a: {},
        )
    )
    with pytest.raises(ValueError):
        registry.register(
            ToolSpec(
                name="x",
                description="x",
                parameters=_string_schema({}),
                handler=lambda c, a: {},
            )
        )


def test_execute_returns_error_for_unknown_tool(tmp_path) -> None:
    registry = ToolRegistry()
    result = registry.execute("missing", {}, _ctx(tmp_path))
    assert result == {"error": "Unknown tool 'missing'"}


def test_execute_wraps_handler_exceptions(tmp_path) -> None:
    registry = ToolRegistry()

    def handler(ctx: ToolContext, args: dict) -> dict:
        raise ValueError("boom")

    registry.register(
        ToolSpec(
            name="fail",
            description="always fails",
            parameters=_string_schema({}),
            handler=handler,
        )
    )
    result = registry.execute("fail", {}, _ctx(tmp_path))
    assert result == {"error": "ValueError: boom"}


def test_execute_returns_handler_dict(tmp_path) -> None:
    registry = ToolRegistry()

    def handler(ctx: ToolContext, args: dict) -> dict:
        return {"ok": True, "args": args}

    registry.register(
        ToolSpec(
            name="ok",
            description="ok",
            parameters=_string_schema({}),
            handler=handler,
        )
    )
    assert registry.execute("ok", {"x": 1}, _ctx(tmp_path)) == {"ok": True, "args": {"x": 1}}


def test_string_schema_sets_object_type() -> None:
    schema = _string_schema({"a": {"type": "string"}}, required=["a"])
    assert schema["type"] == "object"
    assert schema["required"] == ["a"]
    assert "a" in schema["properties"]


def test_non_object_schema_raises() -> None:
    registry = ToolRegistry()
    with pytest.raises(ValueError):
        registry.register(
            ToolSpec(
                name="bad",
                description="bad",
                parameters={"type": "string"},
                handler=lambda c, a: {},
            )
        )
