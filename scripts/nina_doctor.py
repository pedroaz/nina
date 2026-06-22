#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def path_entries() -> list[Path]:
    return [
        Path(entry).expanduser() for entry in os.environ.get("PATH", "").split(os.pathsep) if entry
    ]


def executable_names() -> list[str]:
    return ["nina.cmd", "nina.exe"] if os.name == "nt" else ["nina"]


def find_nina_commands() -> list[Path]:
    names = executable_names()
    found: list[Path] = []
    seen: set[Path] = set()
    for directory in path_entries():
        for name in names:
            candidate = directory / name
            if candidate.exists() and os.access(candidate, os.X_OK):
                resolved = candidate.resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    found.append(candidate)
    return found


def print_path_status(path: Path, label: str) -> None:
    if not path.exists():
        print(f"{label}: missing ({path})")
        return
    if path.is_symlink():
        print(f"{label}: symlink -> {path.resolve()} ({path})")
        return
    print(f"{label}: file ({path})")


def is_repo_venv_command(path: Path) -> bool:
    return path.resolve() == (REPO_ROOT / ".venv" / "bin" / "nina").resolve()


def main() -> int:
    commands = find_nina_commands()
    print("Nina doctor")
    print()

    if commands:
        print("nina commands on PATH:")
        for index, command in enumerate(commands, start=1):
            target = f" -> {command.resolve()}" if command.is_symlink() else ""
            marker = " (active)" if index == 1 else ""
            source = " [repo .venv]" if is_repo_venv_command(command) else ""
            print(f"  {index}. {command}{target}{source}{marker}")
    else:
        print("nina commands on PATH: none")

    print()
    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA")
        launcher = (
            Path(local_app_data) / "Programs" / "Nina" / "bin" / "nina.cmd"
            if local_app_data
            else Path.home() / "AppData" / "Local" / "Programs" / "Nina" / "bin" / "nina.cmd"
        )
    else:
        launcher = Path.home() / ".local" / "bin" / "nina"

    print_path_status(launcher, "Expected launcher")

    print()
    if len(commands) > 1:
        print("Status: warning - more than one nina command is on PATH")
        if any(is_repo_venv_command(command) for command in commands):
            print(
                "The repo .venv entry is normal during development, but deactivate it to test the installed launcher exactly as a user would."
            )
        return 1
    if not commands:
        print("Status: warning - nina is not on PATH")
        return 1
    print("Status: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
