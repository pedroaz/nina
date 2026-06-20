from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest
from nina_core.integrations import (
    credentials_path,
    delete_credentials,
    get_integrations_dir,
    load_credentials,
    save_credentials,
)


def test_integrations_dir_under_config(tmp_path: Path) -> None:
    integrations_dir = get_integrations_dir(tmp_path)
    assert integrations_dir == tmp_path / "integrations"


def test_credentials_path_rejects_invalid_names(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        credentials_path("../escape", tmp_path)
    with pytest.raises(ValueError):
        credentials_path("nested/name", tmp_path)
    with pytest.raises(ValueError):
        credentials_path("", tmp_path)


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    payload = {"base_url": "https://example.atlassian.net", "email": "a@b", "api_token": "tok"}
    path = save_credentials("confluence", payload, config_dir=tmp_path)
    assert path.exists()
    assert path == tmp_path / "integrations" / "confluence.json"
    mode = stat.S_IMODE(path.stat().st_mode)
    assert mode == 0o600, f"expected 0o600, got {oct(mode)}"
    loaded = load_credentials("confluence", config_dir=tmp_path)
    assert loaded == payload


def test_save_overwrites_existing(tmp_path: Path) -> None:
    save_credentials("slack", {"bot_token": "old"}, config_dir=tmp_path)
    save_credentials("slack", {"bot_token": "new"}, config_dir=tmp_path)
    assert load_credentials("slack", config_dir=tmp_path) == {"bot_token": "new"}


def test_load_returns_none_when_missing(tmp_path: Path) -> None:
    assert load_credentials("does-not-exist", config_dir=tmp_path) is None


def test_load_returns_none_for_garbage_file(tmp_path: Path) -> None:
    path = credentials_path("confluence", tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not json")
    assert load_credentials("confluence", config_dir=tmp_path) is None


def test_delete_credentials_returns_true_when_present(tmp_path: Path) -> None:
    save_credentials("jira", {"base_url": "x"}, config_dir=tmp_path)
    assert delete_credentials("jira", config_dir=tmp_path) is True
    assert not credentials_path("jira", tmp_path).exists()


def test_delete_credentials_returns_false_when_absent(tmp_path: Path) -> None:
    assert delete_credentials("ghost", config_dir=tmp_path) is False


def test_save_creates_parent_dir(tmp_path: Path) -> None:
    save_credentials("teams", {"access_token": "t"}, config_dir=tmp_path)
    assert (tmp_path / "integrations").is_dir()
    assert json.loads((tmp_path / "integrations" / "teams.json").read_text()) == {
        "access_token": "t"
    }


def test_save_does_not_leak_on_write_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    save_credentials("confluence", {"x": 1}, config_dir=tmp_path)
    # Force the file open to raise after the file is created so the cleanup
    # path runs and the partial file is removed.
    real_open = os.fdopen

    def boom(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("disk full")

    monkeypatch.setattr(os, "fdopen", boom)
    with pytest.raises(RuntimeError):
        save_credentials("confluence", {"x": 2}, config_dir=tmp_path)
    monkeypatch.setattr(os, "fdopen", real_open)
    # The truncated/partial file should be removed by the cleanup path.
    assert not (tmp_path / "integrations" / "confluence.json").exists()
