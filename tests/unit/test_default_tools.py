from __future__ import annotations

from pathlib import Path

import pytest
from nina_core.config import get_database_path, get_vault_path
from nina_core.llm.default_tools import register_default_tools
from nina_core.llm.tools import ToolContext, ToolRegistry
from nina_core.obsidian.service import ObsidianService


@pytest.fixture
def tool_context(isolated_config: Path) -> ToolContext:
    db_path = str(get_database_path(isolated_config))
    vault_path = get_vault_path(isolated_config)
    obsidian = ObsidianService(vault_path)
    # Build a session for handlers that need a live db connection
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    session_local = sessionmaker(bind=engine)
    db = session_local()
    return ToolContext(
        db_path=db_path,
        vault_path=vault_path,
        db=db,
        obsidian=obsidian,
    )


def test_obsidian_search_returns_matches(tool_context: ToolContext) -> None:
    note_dir = tool_context.vault_path / "Research"
    note_dir.mkdir(parents=True, exist_ok=True)
    (note_dir / "codex.md").write_text(
        "---\ntitle: Codex Auth Notes\nnina_type: note\n---\n\nCodex OAuth is used through the local Codex CLI session.\n"
    )
    (note_dir / "other.md").write_text(
        "---\ntitle: Other\nnina_type: note\n---\n\nUnrelated content here.\n"
    )
    registry = ToolRegistry()
    register_default_tools(registry)
    result = registry.execute(
        "obsidian_search",
        {"query": "Codex OAuth", "limit": 5},
        tool_context,
    )
    paths = [r["path"] for r in result["results"]]
    assert "Research/codex.md" in paths
    assert all(r["snippet"] for r in result["results"])


def test_obsidian_search_empty_query(tool_context: ToolContext) -> None:
    registry = ToolRegistry()
    register_default_tools(registry)
    result = registry.execute("obsidian_search", {"query": ""}, tool_context)
    assert result == {"results": []}


def test_obsidian_get_note(tool_context: ToolContext) -> None:
    note_dir = tool_context.vault_path / "Research"
    note_dir.mkdir(parents=True, exist_ok=True)
    body = "---\ntitle: Codex Auth Notes\nnina_type: note\n---\n\nCodex OAuth is used through the local Codex CLI session.\n"
    from nina_core.notes.service import NoteService

    NoteService(tool_context.db_path, tool_context.vault_path).create_note(
        "Research/codex.md", body, nina_type="note"
    )
    registry = ToolRegistry()
    register_default_tools(registry)
    result = registry.execute("obsidian_get_note", {"path": "Research/codex.md"}, tool_context)
    assert "Codex OAuth" in result["body"]
    assert result["frontmatter"]["title"] == "Codex Auth Notes"


def test_obsidian_get_note_missing(tool_context: ToolContext) -> None:
    registry = ToolRegistry()
    register_default_tools(registry)
    result = registry.execute("obsidian_get_note", {"path": "Research/nope.md"}, tool_context)
    assert "error" in result


def test_obsidian_list_notes(tool_context: ToolContext) -> None:
    note_dir = tool_context.vault_path / "Research"
    note_dir.mkdir(parents=True, exist_ok=True)
    (note_dir / "a.md").write_text("---\ntitle: A\nnina_type: note\n---\n\na body\n")
    (tool_context.vault_path / "Projects" / "p.md").write_text(
        "---\ntitle: P\nnina_type: project\n---\n\np body\n"
    )
    # Bump last_indexed_at by upserting through NoteService
    from nina_core.notes.service import NoteService

    svc = NoteService(tool_context.db_path, tool_context.vault_path)
    svc.create_note("Research/a.md", (note_dir / "a.md").read_text(), nina_type="note")
    svc.create_note(
        "Projects/p.md",
        (tool_context.vault_path / "Projects" / "p.md").read_text(),
        nina_type="project",
    )
    registry = ToolRegistry()
    register_default_tools(registry)
    result = registry.execute("obsidian_list_notes", {"nina_type": "project"}, tool_context)
    assert {n["path"] for n in result["notes"]} == {"Projects/p.md"}


def test_definitions_filters_read_only(tool_context: ToolContext) -> None:
    registry = ToolRegistry()
    register_default_tools(registry)
    read_only = {d.name for d in registry.definitions(read_only=True)}
    assert "obsidian_search" in read_only
    assert "obsidian_get_note" in read_only
    assert "kanban_get" in read_only
