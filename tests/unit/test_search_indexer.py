from __future__ import annotations

from pathlib import Path

from nina_core.config import get_database_path, get_vault_path
from nina_core.search.indexer import index_notes, search


def _write_note(path: Path, title: str, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\ntitle: {title}\nnina_type: note\n---\n\n{body}")


def test_index_notes_skips_protected_and_obsidian_paths(isolated_config: Path) -> None:
    vault = get_vault_path(isolated_config)
    db_path = str(get_database_path(isolated_config))
    _write_note(vault / "Research" / "visible.md", "Visible", "visible keyword")
    _write_note(vault / "System" / "Deleted" / "deleted.md", "Deleted", "secret keyword")
    _write_note(vault / "System" / "Archived" / "archived.md", "Archived", "secret keyword")
    _write_note(vault / ".obsidian" / "metadata.md", "Metadata", "secret keyword")

    index_notes(db_path, str(vault))

    assert [result["path"] for result in search(db_path, "visible", limit=10)] == [
        "Research/visible.md"
    ]
    assert search(db_path, "secret", limit=10) == []
