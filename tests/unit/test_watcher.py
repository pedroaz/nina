from __future__ import annotations

from pathlib import Path

from nina_core.search.watcher import (
    REFUSED_PATHS,
    REFUSED_SUFFIXES,
    _should_skip,
)


def test_should_skip_refused_prefix(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    assert _should_skip(vault / "System/Indexes/x.md", vault)
    assert _should_skip(vault / "System/Logs/x.md", vault)
    assert _should_skip(vault / ".obsidian/x.md", vault)


def test_should_skip_refused_suffix(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    assert _should_skip(vault / "x.tmp", vault)
    assert _should_skip(vault / "x.swp", vault)


def test_should_skip_non_md(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    assert _should_skip(vault / "x.txt", vault)


def test_should_not_skip_normal_md(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    assert not _should_skip(vault / "Research/x.md", vault)


def test_constants_exist() -> None:
    assert "System/Indexes/" in REFUSED_PATHS
    assert ".tmp" in REFUSED_SUFFIXES
