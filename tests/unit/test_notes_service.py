from __future__ import annotations

from pathlib import Path

import pytest
from nina_core.config import get_database_path, get_vault_path
from nina_core.notes.service import NotePathError, NoteService, safe_resolve_path


def test_safe_resolve_accepts_normal_path(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    result = safe_resolve_path(vault, "Research/note.md")
    assert result == (vault / "Research/note.md").resolve()


def test_safe_resolve_rejects_absolute(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    with pytest.raises(NotePathError):
        safe_resolve_path(vault, "/etc/passwd")


def test_safe_resolve_rejects_traversal(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    with pytest.raises(NotePathError):
        safe_resolve_path(vault, "../escape.md")


def test_safe_resolve_rejects_protected_prefixes(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    for path in ["System/Deleted/note.md", "System/Archived/note.md"]:
        with pytest.raises(NotePathError):
            safe_resolve_path(vault, path)


def test_safe_resolve_allows_former_placeholder_folders(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    for path in [
        "System/Indexes/idx.md",
        "System/Logs/log.md",
        "Templates/template.md",
    ]:
        assert safe_resolve_path(vault, path) == (vault / path).resolve()


def test_create_and_get_note(isolated_config: Path) -> None:
    service = NoteService(
        str(get_database_path(isolated_config)),
        get_vault_path(isolated_config),
    )
    body = "---\ntitle: Hello\nnina_type: note\n---\n\nBody text."
    created = service.create_note("Research/hello.md", body, nina_type="note")
    assert created["path"] == "Research/hello.md"

    fetched = service.get_note("Research/hello.md")
    assert fetched is not None
    assert fetched["title"] == "Hello"
    assert fetched["nina_type"] == "note"
    assert "Body text." in fetched["body"]


def test_create_note_rejects_unsafe_path(isolated_config: Path) -> None:
    service = NoteService(
        str(get_database_path(isolated_config)),
        get_vault_path(isolated_config),
    )
    with pytest.raises(NotePathError):
        service.create_note("../escape.md", "x", nina_type="note")
    with pytest.raises(NotePathError):
        service.create_note("System/Deleted/x.md", "x", nina_type="note")


def test_append_note(isolated_config: Path) -> None:
    service = NoteService(
        str(get_database_path(isolated_config)),
        get_vault_path(isolated_config),
    )
    service.create_note("Daily/2026-06-13.md", "first", nina_type="daily_summary")
    service.append_note("Daily/2026-06-13.md", "\nsecond")
    fetched = service.get_note("Daily/2026-06-13.md")
    assert fetched is not None
    assert "first" in fetched["body"]
    assert "second" in fetched["body"]


def test_update_note(isolated_config: Path) -> None:
    service = NoteService(
        str(get_database_path(isolated_config)),
        get_vault_path(isolated_config),
    )
    service.create_note(
        "Research/x.md",
        "---\ntitle: X\n---\n\nold",
        nina_type="note",
    )
    service.update_note(
        "Research/x.md",
        "new",
        frontmatter_patch={"title": "X renamed"},
    )
    fetched = service.get_note("Research/x.md")
    assert fetched is not None
    assert "new" in fetched["body"]
    assert fetched["frontmatter"].get("title") == "X renamed"


def test_list_notes(isolated_config: Path) -> None:
    service = NoteService(
        str(get_database_path(isolated_config)),
        get_vault_path(isolated_config),
    )
    service.create_note("Research/a.md", "a", nina_type="note")
    service.create_note("Research/b.md", "b", nina_type="note")
    service.create_note("Projects/c.md", "c", nina_type="project")
    notes = service.list_notes(folder="Research")
    assert {n["path"] for n in notes} == {"Research/a.md", "Research/b.md"}
    notes = service.list_notes(nina_type="project")
    assert {n["path"] for n in notes} == {"Projects/c.md"}
