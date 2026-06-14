from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, cast

CACHE_FILENAME = "provider_pricing.json"
CACHE_VERSION = 1


def cache_filename() -> str:
    return CACHE_FILENAME


def cache_path(config_dir: Path | str) -> Path:
    return Path(config_dir) / CACHE_FILENAME


def _resolve_config_dir(config_dir: Path | str | None) -> Path:
    if config_dir is not None:
        return Path(config_dir)
    env_dir = os.environ.get("NINA_CONFIG_DIR")
    if env_dir:
        return Path(env_dir)
    raise RuntimeError(
        "NINA_CONFIG_DIR is not set; pass config_dir explicitly to the pricing service"
    )


def load_cache(config_dir: Path | str | None = None) -> dict[str, Any]:
    path = cache_path(_resolve_config_dir(config_dir))
    if not path.exists():
        return {"version": CACHE_VERSION, "providers": {}}
    try:
        raw_text: str = path.read_text()
    except OSError:
        return {"version": CACHE_VERSION, "providers": {}}
    try:
        parsed: Any = json.loads(raw_text)
    except (ValueError, TypeError):
        return {"version": CACHE_VERSION, "providers": {}}
    if not isinstance(parsed, dict):
        return {"version": CACHE_VERSION, "providers": {}}
    data: dict[str, Any] = cast(dict[str, Any], parsed)
    raw_providers: object = data.get("providers", {})
    providers: dict[str, Any] = (
        cast(dict[str, Any], raw_providers) if isinstance(raw_providers, dict) else {}
    )
    result: dict[str, Any] = {"version": CACHE_VERSION, "providers": providers}
    raw_version: object = data.get("version", CACHE_VERSION)
    if isinstance(raw_version, int):
        result["version"] = raw_version
    return result


def save_cache(payload: dict[str, Any], config_dir: Path | str | None = None) -> Path:
    target = cache_path(_resolve_config_dir(config_dir))
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{CACHE_FILENAME}.", suffix=".tmp", dir=str(target.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, indent=2, sort_keys=False))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, target)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    return target
