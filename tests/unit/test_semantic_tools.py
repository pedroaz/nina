from __future__ import annotations

from pathlib import Path

import pytest
from nina_core.config import get_database_path, get_vault_path
from nina_core.llm.default_tools import register_default_tools
from nina_core.llm.tools import ToolContext, ToolRegistry
from nina_core.obsidian.service import ObsidianService


@pytest.fixture
def tool_context(isolated_config: Path, monkeypatch: pytest.MonkeyPatch) -> ToolContext:
    monkeypatch.setenv("NINA_EMBEDDING_PROVIDER", "fake")
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


def test_semantic_search_returns_results(tool_context: ToolContext) -> None:
    note_dir = tool_context.vault_path / "Research"
    note_dir.mkdir(parents=True, exist_ok=True)
    (note_dir / "a.md").write_text(
        "---\ntitle: A\nnina_type: note\n---\n\nthe quick brown fox"
    )
    (note_dir / "b.md").write_text(
        "---\ntitle: B\nnina_type: note\n---\n\nhello world"
    )
    registry = ToolRegistry()
    register_default_tools(registry)
    result = registry.execute(
        "obsidian_semantic_search",
        {"query": "the quick brown fox", "limit": 5},
        tool_context,
    )
    paths = [r["path"] for r in result["results"]]
    assert "Research/a.md" in paths


def test_hybrid_search_returns_results(tool_context: ToolContext) -> None:
    note_dir = tool_context.vault_path / "Research"
    note_dir.mkdir(parents=True, exist_ok=True)
    (note_dir / "alpha.md").write_text(
        "---\ntitle: Alpha\nnina_type: note\n---\n\nCodex OAuth setup"
    )
    (note_dir / "beta.md").write_text(
        "---\ntitle: Beta\nnina_type: note\n---\n\ncompletely unrelated content"
    )
    registry = ToolRegistry()
    register_default_tools(registry)
    result = registry.execute(
        "obsidian_hybrid_search",
        {"query": "How do I authenticate with Codex?", "limit": 5},
        tool_context,
    )
    paths = [r["path"] for r in result["results"]]
    assert "Research/alpha.md" in paths
    assert all(r.get("ranker") == "hybrid" for r in result["results"])


def test_semantic_search_empty_query(tool_context: ToolContext) -> None:
    registry = ToolRegistry()
    register_default_tools(registry)
    result = registry.execute("obsidian_semantic_search", {"query": ""}, tool_context)
    assert result == {"results": []}
