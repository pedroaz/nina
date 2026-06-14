from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest
from nina_core.cli.runner import CommandResult
from nina_core.config import get_database_path, get_vault_path
from nina_core.llm import provider as provider_module
from nina_core.llm.provider import LLMRequest, LLMService, ToolCall
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
    assert "nina ticket move" in fake_runner.commands[1]
    assert "ticket-123" in fake_runner.commands[1]
    assert response["assistant"]["content"].startswith("Created ticket ticket-123")
    assert response["commands"][0]["created_id"] == "ticket-123"
    assert [message["role"] for message in response["session"]["messages"]] == [
        "user",
        "tool",
        "tool",
        "assistant",
    ]


def _stub_fake_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace LLMService provider with a FakeProvider for predictable tests."""

    fake = provider_module.FakeProvider()
    monkeypatch.setattr(LLMService, "_build_provider", lambda self: fake)
    return fake


async def test_chat_session_uses_obsidian_search_tool_call(
    isolated_config: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NINA_LLM_PROVIDER", "fake")
    fake = _stub_fake_provider(monkeypatch)

    note_dir = isolated_config / "vault" / "Research"
    note_dir.mkdir(parents=True, exist_ok=True)
    (note_dir / "codex.md").write_text(
        "---\ntitle: Codex Auth Notes\nnina_type: note\n---\n\nCodex OAuth is used through the local Codex CLI session.\n"
    )

    service = SessionService(
        str(get_database_path(isolated_config)), str(get_vault_path(isolated_config))
    )
    session = service.create_session("chat", "Chat")

    # First LLM call returns a tool call; second returns the final text.
    call = ToolCall(
        id="call-1",
        name="obsidian_search",
        arguments={"query": "Codex OAuth", "limit": 3},
    )
    fake.queue_tool_calls([call], "")
    fake.queue_text("Found information about Codex OAuth in the vault.")

    response = await service.send_message(session["id"], "How is Codex OAuth used?")

    assert response["assistant"]["content"] == "Found information about Codex OAuth in the vault."
    assert response["sources"][0]["path"] == "Research/codex.md"
    assert response["tools_used"][0]["name"] == "obsidian_search"
    # user + tool + assistant
    assert [m["role"] for m in response["session"]["messages"]] == [
        "user",
        "tool",
        "assistant",
    ]


async def test_chat_session_carries_history_into_tool_loop(
    isolated_config: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NINA_LLM_PROVIDER", "fake")
    fake = _stub_fake_provider(monkeypatch)
    service = SessionService(
        str(get_database_path(isolated_config)), str(get_vault_path(isolated_config))
    )
    session = service.create_session("chat", "Chat")

    # First turn
    fake.queue_text("first answer")
    await service.send_message(session["id"], "first question")

    # Second turn: capture the messages sent to the LLM
    captured: list[dict] = []

    async def capture(provider_self, request: LLMRequest):
        captured.append({"messages": list(request.messages or []), "purpose": request.purpose})
        if len(captured) == 1:
            return provider_module.LLMResponse(
                response="second answer", model="fake", provider="fake"
            )
        return provider_module.LLMResponse(response="second answer", model="fake", provider="fake")

    # Patch at instance level to capture.
    original_complete = service.llm.complete

    async def wrapper(request: LLMRequest):
        captured.append({"messages": list(request.messages or []), "purpose": request.purpose})
        return await original_complete(request)

    service.llm.complete = wrapper  # type: ignore[assignment]
    await service.send_message(session["id"], "second question")

    second_messages = captured[-1]["messages"]
    roles = [m.get("role") for m in second_messages]
    assert roles[0] == "system"
    assert "user" in roles
    user_messages = [m for m in second_messages if m.get("role") == "user"]
    assert any(m.get("content") == "first question" for m in user_messages)
    assert any(m.get("content") == "second question" for m in user_messages)


async def test_session_cancel_marks_session(
    isolated_config: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NINA_LLM_PROVIDER", "fake")
    service = SessionService(
        str(get_database_path(isolated_config)), str(get_vault_path(isolated_config))
    )
    session = service.create_session("chat", "Chat")
    assert service.request_cancel(session["id"]) is True
    fetched = service.get_session(session["id"])
    assert fetched is not None
    assert fetched["cancel_requested"] is True
    # Clear for the next request
    service.clear_cancel(session["id"])
    fetched = service.get_session(session["id"])
    assert fetched is not None
    assert fetched["cancel_requested"] is False


async def test_chat_session_cancelled_run_records_finish_reason(
    isolated_config: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NINA_LLM_PROVIDER", "fake")
    fake = _stub_fake_provider(monkeypatch)
    service = SessionService(
        str(get_database_path(isolated_config)), str(get_vault_path(isolated_config))
    )
    session = service.create_session("chat", "Chat")
    # Pre-cancel
    service.request_cancel(session["id"])
    # LLM should not even be called, but if it returns a normal text we should
    # observe finish_reason=cancelled.
    fake.queue_text("ignored")
    response = await service.send_message(session["id"], "hi")
    metadata = response["assistant"]["metadata"]
    assert metadata["finish_reason"] == "cancelled"


async def test_agent_session_uses_tickets_create_tool(
    isolated_config: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NINA_LLM_PROVIDER", "fake")
    fake = _stub_fake_provider(monkeypatch)
    service = SessionService(
        str(get_database_path(isolated_config)),
        str(get_vault_path(isolated_config)),
    )
    session = service.create_session("agent", "Agent")

    # First call: create ticket; second call: move it to Doing
    fake.queue_tool_calls(
        [
            ToolCall(
                id="c1",
                name="tickets_create",
                arguments={"title": "Add a CLI flag", "description": "Flag X"},
            )
        ],
        "",
    )
    fake.queue_tool_calls(
        [
            ToolCall(
                id="c2",
                name="tickets_move",
                arguments={"id": "{{last_created_id}}", "column": "Doing"},
            )
        ],
        "",
    )
    fake.queue_text("Created and moved the ticket to Doing.")

    response = await service.send_message(
        session["id"],
        "Add a ticket to add a CLI flag and put it in Doing",
    )

    assert response["tools_used"][0]["name"] == "tickets_create"
    assert response["tools_used"][1]["name"] == "tickets_move"
    # The assistant message confirms completion
    assert (
        "Doing" in response["assistant"]["content"] or "Created" in response["assistant"]["content"]
    )


async def test_agent_session_creates_note_via_tool(
    isolated_config: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NINA_LLM_PROVIDER", "fake")
    fake = _stub_fake_provider(monkeypatch)
    service = SessionService(
        str(get_database_path(isolated_config)),
        str(get_vault_path(isolated_config)),
    )
    session = service.create_session("agent", "Agent")

    fake.queue_tool_calls(
        [
            ToolCall(
                id="c1",
                name="notes_create",
                arguments={
                    "path": "Research/captured.md",
                    "body": "---\ntitle: Captured\n---\n\nFindings.",
                    "nina_type": "note",
                },
            )
        ],
        "",
    )
    fake.queue_text("Captured the findings into Research/captured.md.")

    await service.send_message(session["id"], "Save what we discussed into a note.")

    full_path = isolated_config / "vault" / "Research" / "captured.md"
    assert full_path.is_file()
    text = full_path.read_text()
    assert "Findings" in text
