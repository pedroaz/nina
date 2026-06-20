from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from nina_core.config import get_config_dir  # type: ignore[import-untyped]


def get_integrations_dir(config_dir: Path | None = None) -> Path:
    """Directory that stores per-integration credential files."""

    base = config_dir if config_dir is not None else get_config_dir()
    return base / "integrations"


def credentials_path(name: str, config_dir: Path | None = None) -> Path:
    """Where a single integration's credentials live.

    Files are stored with `0600` permissions because they hold API tokens.
    """

    if not name or "/" in name or ".." in name:
        raise ValueError(f"Invalid integration name: {name!r}")
    return get_integrations_dir(config_dir) / f"{name}.json"


def load_credentials(name: str, config_dir: Path | None = None) -> dict[str, Any] | None:
    path = credentials_path(name, config_dir)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return dict(data)  # type: ignore[arg-type]


def save_credentials(
    name: str,
    payload: dict[str, Any],
    config_dir: Path | None = None,
) -> Path:
    path = credentials_path(name, config_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
    except BaseException:
        # On any failure, attempt to remove the partial file and close the
        # descriptor if it has not been handed off to fdopen yet. The
        # `os.fdopen` line is the only path that takes ownership of the FD;
        # any failure before that point means we still hold it.
        try:
            path.unlink()
        except OSError:
            pass
        raise
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return path


def delete_credentials(name: str, config_dir: Path | None = None) -> bool:
    path = credentials_path(name, config_dir)
    if not path.exists():
        return False
    path.unlink()
    return True
