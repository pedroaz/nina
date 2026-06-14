from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Sequence

ALLOWED_TOP_LEVEL_COMMANDS = {
    "ask",
    "job",
    "kanban",
    "project",
    "research",
    "task",
    "ticket",
    "workflow",
}

CREATED_ID_RE = re.compile(r"Created (?:task|ticket) (?P<id>[A-Za-z0-9-]+)")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_nina_command(args: Sequence[str]) -> str:
    return " ".join(["nina", *[shlex.quote(arg) for arg in args]])


def extract_created_id(output: str) -> str | None:
    match = CREATED_ID_RE.search(output)
    return match.group("id") if match else None


@dataclass
class CommandResult:
    command: str
    exit_code: int
    stdout: str
    stderr: str
    started_at: str
    completed_at: str
    command_id: str = ""
    created_id: str | None = None


class NinaCommandRunner:
    def __init__(self, env: dict[str, str] | None = None, timeout_seconds: int = 180) -> None:
        self.env = env or os.environ.copy()
        self.timeout_seconds = timeout_seconds

    def run(self, command: str) -> CommandResult:
        args = shlex.split(command)
        if len(args) < 2 or args[0] != "nina":
            raise ValueError("Only nina commands can be executed")
        if args[1] not in ALLOWED_TOP_LEVEL_COMMANDS:
            raise ValueError(f"Command 'nina {args[1]}' is not allowed")
        started_at = _now()
        completed = subprocess.run(
            [sys.executable, "-m", "nina_cli.main", *args[1:]],
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
            env=self.env,
            check=False,
        )
        completed_at = _now()
        stdout = completed.stdout.strip()
        stderr = completed.stderr.strip()
        return CommandResult(
            command=command,
            exit_code=completed.returncode,
            stdout=stdout,
            stderr=stderr,
            started_at=started_at,
            completed_at=completed_at,
            command_id=str(uuid.uuid4()),
            created_id=extract_created_id(stdout),
        )
