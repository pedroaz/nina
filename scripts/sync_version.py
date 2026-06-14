#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = REPO_ROOT / "VERSION"

TOML_FILES = [
    REPO_ROOT / "pyproject.toml",
    REPO_ROOT / "packages" / "nina_core" / "pyproject.toml",
    REPO_ROOT / "apps" / "cli" / "pyproject.toml",
    REPO_ROOT / "apps" / "server" / "pyproject.toml",
]

PYTHON_FILES = [
    (
        REPO_ROOT / "packages" / "nina_core" / "nina_core" / "__init__.py",
        r'__version__\s*=\s*"[^"]+"',
        '__version__ = "{version}"',
    ),
]

JSON_FILES = [
    REPO_ROOT / "apps" / "tui" / "package.json",
]


def read_version() -> str:
    return VERSION_FILE.read_text().strip().splitlines()[0].strip()


def sync_toml(path: Path, version: str) -> bool:
    content = path.read_text()
    new_content = re.sub(
        r'^version\s*=\s*"[^"]+"',
        f'version = "{version}"',
        content,
        count=1,
        flags=re.MULTILINE,
    )
    if new_content != content:
        path.write_text(new_content)
        return True
    return False


def sync_python(path: Path, pattern: str, template: str, version: str) -> bool:
    content = path.read_text()
    new_content = re.sub(pattern, template.format(version=version), content, count=1)
    if new_content != content:
        path.write_text(new_content)
        return True
    return False


def sync_json(path: Path, version: str) -> bool:
    content = path.read_text()
    data = json.loads(content)
    old_version = data.get("version")
    if old_version != version:
        data["version"] = version
        path.write_text(json.dumps(data, indent=2) + "\n")
        return True
    return False


def main() -> int:
    version = read_version()
    updated = False

    for path in TOML_FILES:
        if sync_toml(path, version):
            print(f"Updated {path.relative_to(REPO_ROOT)}")
            updated = True

    for path, pattern, template in PYTHON_FILES:
        if sync_python(path, pattern, template, version):
            print(f"Updated {path.relative_to(REPO_ROOT)}")
            updated = True

    for path in JSON_FILES:
        if sync_json(path, version):
            print(f"Updated {path.relative_to(REPO_ROOT)}")
            updated = True

    if not updated:
        print(f"All files already at version {version}.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
