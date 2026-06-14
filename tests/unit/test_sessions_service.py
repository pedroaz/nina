from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest
from nina_core.cli.runner import CommandResult
from nina_core.config import get_database_path, get_vault_path
from nina_core.sessions.service import SessionService

NOW = "2026-06-13T00:00:00+00:00"


@dataclass
class FakeCommandRunner:
    commands: list[str]

    def run(self, command: str) -> CommandResult:
        self.commands.append(command)
        if "ticket create" in command:
            return CommandResult(
                command=command,
                exit_code=0,
                stdout="Created ticket ticket-123",
                stderr="",
                started_at=NOW,
                completed_at=NOW,
                command_id="cmd-create",
                created_id="ticket-123",
            )
        if "ticket move" in command:
            return CommandResult(
                command=command,
                exit_code=0,
                stdout="Moved ticket ticket-123 to Doing:0",
                stderr="",
                started_at=NOW,
                completed_at=NOW,
                command_id="cmd-move",
                created_id="ticket-123",
            )
        return CommandResult(
            command=command,
            exit_code=0,
            stdout="",
            stderr="",
            started_at=NOW,
            completed_at=NOW,
            command_id="cmd-generic",
        )


async def test_chat_session_uses_obsidian_context(
    isolated_config: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NINA_LLM_PROVIDER", "fake")
    note_dir = isolated_config / "vault" / "Research"
    note_dir.mkdir(parents=True, exist_ok=True)
    (note_dir / "codex.md").write_text(
        "---\ntitle: Codex Auth Notes\nnina_type: note\n---\n\nCodex OAuth is used through the local Codex CLI session.\n"
    )

    service = SessionService(
        str(get_database_path(isolated_config)), str(get_vault_path(isolated_config))
    )
    session = service.create_session("chat", "Chat")
    response = await service.send_message(session["id"], "How is Codex OAuth used?")

    assert response["assistant"]["role"] == "assistant"
    assert response["sources"][0]["path"] == "Research/codex.md"
    assert response["session"]["messages"][-1]["role"] == "assistant"


async def test_agent_session_creates_ticket_and_moves_it(
    isolated_config: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NINA_LLM_PROVIDER", "fake")
    fake_runner = FakeCommandRunner(commands=[])
    service = SessionService(
        str(get_database_path(isolated_config)),
        str(get_vault_path(isolated_config)),
        command_runner=fake_runner,
    )
    session = service.create_session("agent", "Agent")
    response = await service.send_message(
        session["id"],
        "Create a ticket to fix daemon stop and put it in Doing.",
    )

    assert len(fake_runner.commands) == 2
    assert fake_runner.commands[0].startswith("nina ticket create")
    assert fake_runner.commands[1].startswith("nina ticket move ticket-123")
    assert response["assistant"]["content"].startswith("Created ticket ticket-123")
    assert response["commands"][0]["created_id"] == "ticket-123"
    assert [message["role"] for message in response["session"]["messages"]] == [
        "user",
        "tool",
        "tool",
        "assistant",
    ]
