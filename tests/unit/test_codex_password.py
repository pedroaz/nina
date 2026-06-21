"""Unit tests for the codex password file management."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest
from nina_core.codex.password import (
    ensure_password_file,
    generate_password,
    password_path,
    read_password,
)


def test_generate_password_is_url_safe_and_long() -> None:
    password = generate_password()
    assert isinstance(password, str)
    # token_urlsafe(32) yields >= 43 chars, no padding.
    assert len(password) >= 40
    assert "+" not in password
    assert "/" not in password


def test_password_path_rejects_traversal(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        password_path(tmp_path, "../escape")
    with pytest.raises(ValueError):
        password_path(tmp_path, "/abs/path")
    with pytest.raises(ValueError):
        password_path(tmp_path, "nested/dir")


def test_ensure_password_file_creates_with_0600(tmp_path: Path) -> None:
    path = ensure_password_file(tmp_path, "codex_password")
    assert path.exists()
    text = path.read_text().strip()
    assert len(text) >= 40
    if os.name == "posix":
        mode = stat.S_IMODE(path.stat().st_mode)
        assert mode == 0o600


def test_ensure_password_file_is_idempotent(tmp_path: Path) -> None:
    path = ensure_password_file(tmp_path, "codex_password")
    first = path.read_text()
    path2 = ensure_password_file(tmp_path, "codex_password")
    second = path2.read_text()
    assert first == second
    assert path == path2


def test_ensure_password_file_force_regenerates(tmp_path: Path) -> None:
    path = ensure_password_file(tmp_path, "codex_password")
    first = path.read_text()
    path2 = ensure_password_file(tmp_path, "codex_password", force=True)
    second = path2.read_text()
    assert first != second


def test_read_password_round_trips(tmp_path: Path) -> None:
    path = ensure_password_file(tmp_path, "codex_password")
    expected = path.read_text().strip()
    assert read_password(tmp_path, "codex_password") == expected
