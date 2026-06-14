from __future__ import annotations

import sys
from dataclasses import dataclass

import pytest
from nina_core.cli.runner import NinaCommandRunner, build_nina_command, extract_created_id


@dataclass
class FakeCompleted:
    returncode: int = 0
    stdout: str = ""
    stderr: str = ""


def test_build_nina_command_quotes_arguments() -> None:
    command = build_nina_command(
        ["ticket", "create", "Fix daemon stop", "--description", "Needs follow up"]
    )

    assert command == "nina ticket create 'Fix daemon stop' --description 'Needs follow up'"


def test_extract_created_id_handles_tasks_and_tickets() -> None:
    assert extract_created_id("Created ticket abc-123") == "abc-123"
    assert extract_created_id("Created task task-9") == "task-9"
    assert extract_created_id("No ticket here") is None


def test_runner_executes_allowed_ticket_command(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return FakeCompleted(stdout="Created ticket abc-123\n")

    monkeypatch.setattr("nina_core.cli.runner.subprocess.run", fake_run)

    runner = NinaCommandRunner(env={"NINA_CONFIG_DIR": "/tmp/nina"}, timeout_seconds=7)
    command = build_nina_command(["ticket", "create", "Fix daemon stop"])
    result = runner.run(command)

    assert captured["cmd"] == [
        sys.executable,
        "-m",
        "nina_cli.main",
        "ticket",
        "create",
        "Fix daemon stop",
    ]
    assert result.command == command
    assert result.exit_code == 0
    assert result.created_id == "abc-123"


def test_runner_rejects_disallowed_commands() -> None:
    runner = NinaCommandRunner()

    with pytest.raises(ValueError):
        runner.run("bash -lc 'echo hi'")
    with pytest.raises(ValueError):
        runner.run("nina daemon stop")
