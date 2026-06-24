from __future__ import annotations

from pathlib import Path
from typing import Iterable, Iterator


DEFAULT_VAULT_FOLDERS = (
    "Tasks",
    "Research",
    "Meetings",
    "Voice",
    "System/Deleted",
    "System/Archived",
)

PROTECTED_NOTE_PREFIXES = (
    "System/Deleted/",
    "System/Archived/",
)

INDEX_EXCLUDED_PREFIXES = (
    *PROTECTED_NOTE_PREFIXES,
    ".obsidian/",
)

TEMP_NOTE_SUFFIXES = (".tmp", ".swp", ".part", ".crdownload")


def vault_relative_path(path: str | Path, vault: Path | None = None) -> str:
    target = Path(path)
    if vault is not None and target.is_absolute():
        try:
            target = target.resolve().relative_to(vault.resolve())
        except ValueError:
            return target.as_posix()
    return target.as_posix().lstrip("/")


def _matches_prefix(path: str | Path, prefixes: Iterable[str]) -> bool:
    rel = vault_relative_path(path)
    return any(rel == prefix.rstrip("/") or rel.startswith(prefix) for prefix in prefixes)


def is_protected_note_path(path: str | Path) -> bool:
    return _matches_prefix(path, PROTECTED_NOTE_PREFIXES)


def is_index_excluded_path(path: str | Path) -> bool:
    return _matches_prefix(path, INDEX_EXCLUDED_PREFIXES)


def is_indexable_note_path(path: str | Path, vault: Path | None = None) -> bool:
    rel = vault_relative_path(path, vault)
    if is_index_excluded_path(rel):
        return False
    suffix = Path(rel).suffix.lower()
    if suffix in TEMP_NOTE_SUFFIXES:
        return False
    return suffix == ".md"


def iter_indexable_note_files(vault: Path) -> Iterator[tuple[str, Path]]:
    for path in vault.rglob("*.md"):
        rel_path = vault_relative_path(path, vault)
        if is_indexable_note_path(rel_path):
            yield rel_path, path
