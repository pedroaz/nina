from __future__ import annotations

from pathlib import Path

import pytest
from nina_core.config import get_database_path, get_vault_path
from nina_core.llm.default_tools import register_default_tools
from nina_core.llm.tools import ToolContext, ToolRegistry
from nina_core.llm.write_tools import register_write_tools
from nina_core.obsidian.service import ObsidianService


@pytest.fixture
def tool_context(isolated_config: Path) -> ToolContext:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    db_path = str(get_database_path(isolated_config))
    vault_path = get_vault_path(isolated_config)
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    session_local = sessionmaker(bind=engine)
    db = session_local()
    return ToolContext(
        db_path=db_path,
        vault_path=vault_path,
        db=db,
        obsidian=ObsidianService(vault_path),
    )


def test_tickets_create(tool_context: ToolContext) -> None:
    registry = ToolRegistry()
    register_default_tools(registry)
    register_write_tools(registry)
    result = registry.execute(
        "tickets_create",
        {"title": "Test ticket", "description": "A test"},
        tool_context,
    )
    assert "ticket" in result
    assert result["ticket"]["title"] == "Test ticket"
    assert result["ticket"]["kanban_column"] == "Todo"


def test_tickets_create_and_move(tool_context: ToolContext) -> None:
    registry = ToolRegistry()
    register_default_tools(registry)
    register_write_tools(registry)
    result = registry.execute(
        "tickets_create",
        {"title": "Test", "kanban_column": "Doing"},
        tool_context,
    )
    ticket_id = result["ticket"]["id"]
    moved = registry.execute("tickets_move", {"id": ticket_id, "column": "Review"}, tool_context)
    assert moved["ticket"]["kanban_column"] == "Review"
    assert moved["ticket"]["status"] == "review"


def test_notes_create_appends_to_vault(tool_context: ToolContext) -> None:
    registry = ToolRegistry()
    register_default_tools(registry)
    register_write_tools(registry)
    registry.execute(
        "notes_create",
        {
            "path": "Research/agent-note.md",
            "body": "---\ntitle: Agent Note\n---\n\nHello",
            "nina_type": "note",
        },
        tool_context,
    )
    full = tool_context.vault_path / "Research" / "agent-note.md"
    assert full.is_file()
    text = full.read_text()
    assert "Agent Note" in text
    assert "Hello" in text


def test_notes_create_rejects_unsafe(tool_context: ToolContext) -> None:
    registry = ToolRegistry()
    register_default_tools(registry)
    register_write_tools(registry)
    result = registry.execute(
        "notes_create", {"path": "../escape.md", "body": "x", "nina_type": "note"}, tool_context
    )
    assert "error" in result


def test_search_reindex(tool_context: ToolContext) -> None:
    registry = ToolRegistry()
    register_default_tools(registry)
    register_write_tools(registry)
    note_dir = tool_context.vault_path / "Research"
    note_dir.mkdir(parents=True, exist_ok=True)
    (note_dir / "x.md").write_text("---\ntitle: X\nnina_type: note\n---\n\nhello world")
    result = registry.execute("search_reindex", {}, tool_context)
    assert result == {"reindexed": True}


def test_definitions_split_read_and_write(tool_context: ToolContext) -> None:
    registry = ToolRegistry()
    register_default_tools(registry)
    register_write_tools(registry)
    read = {d.name for d in registry.definitions(read_only=True)}
    write = {d.name for d in registry.definitions(read_only=False)}
    assert "obsidian_search" in read
    assert "tickets_create" in write
    assert "tickets_create" not in read
    assert "notes_create" in write
