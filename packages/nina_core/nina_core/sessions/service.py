from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from nina_core.cli.runner import NinaCommandRunner, build_nina_command, extract_created_id
from nina_core.llm.provider import LLMRequest, LLMService
from nina_core.models.models import ConversationMessage, ConversationSession
from nina_core.search.indexer import ask_obsidian

LAST_CREATED_ID_PLACEHOLDER = "{{last_created_id}}"
COMMAND_LINE_RE = re.compile(r"(?m)^\s*(?:[-*]\s*)?(nina\s+.+?)\s*$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False)


def _json_loads(data: str | None) -> Any:
    if not data:
        return {}
    try:
        return json.loads(data)
    except json.JSONDecodeError:
        return {"raw": data}


def _session_title(text: str) -> str:
    collapsed = " ".join(text.split())
    return collapsed[:60] or "Conversation"


def _extract_commands(text: str) -> list[str]:
    commands: list[str] = []
    for match in COMMAND_LINE_RE.finditer(text):
        command = match.group(1).strip()
        if command not in commands:
            commands.append(command)
    return commands


def _strip_commands(text: str) -> str:
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("nina "):
            continue
        if stripped.startswith("- nina ") or stripped.startswith("* nina "):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def _extract_ticket_title(message: str) -> str:
    clause_verb = r"(?:put|move|set|assign|mention|add|include|note|describe|document|capture|track)"
    patterns = [
        rf"create\s+(?:a\s+)?(?:ticket|task)\s*(?:to|for)?\s*(?P<title>.*?)(?:\s+(?:and|then)\s+{clause_verb}\b|;|\.|$)",
        rf"(?:ticket|task)\s*[:\-]\s*(?P<title>.*?)(?:\s+(?:and|then)\s+{clause_verb}\b|;|\.|$)",
    ]
    for pattern in patterns:
        match = re.search(pattern, message, flags=re.IGNORECASE)
        if match:
            title = re.sub(rf"\b(?:and|then)\s+{clause_verb}\b.*$", "", match.group("title"), flags=re.IGNORECASE).strip()
            if title:
                return title
    fallback = re.split(rf"\b(?:and|then)\s+{clause_verb}\b", message, maxsplit=1, flags=re.IGNORECASE)[0]
    fallback = re.sub(r"^(?:create\s+(?:a\s+)?(?:ticket|task)\s*(?:to|for)?\s*)", "", fallback, flags=re.IGNORECASE).strip()
    return fallback[:80] or "Untitled ticket"


def _extract_target_column(message: str) -> str | None:
    lowered = message.lower()
    mapping = {
        "backlog": "Backlog",
        "todo": "Todo",
        "doing": "Doing",
        "review": "Review",
        "done": "Done",
    }
    for key, value in mapping.items():
        if f" in {key}" in lowered or f" to {key}" in lowered or f"move it to {key}" in lowered:
            return value
    return None


@dataclass
class AgentPlan:
    response: str
    commands: list[str]


class SessionService:
    def __init__(self, db_path: str, vault_path: str, command_runner: NinaCommandRunner | None = None) -> None:
        self.db_path = db_path
        self.vault_path = Path(vault_path)
        self.command_runner = command_runner or NinaCommandRunner()
        self.llm = LLMService(db_path)
        self.engine = create_engine(f"sqlite:///{db_path}", echo=False)
        self.session_factory = sessionmaker(bind=self.engine)

    def _session(self) -> Session:
        return self.session_factory()

    def create_session(self, mode: str, title: str | None = None) -> dict[str, Any]:
        db = self._session()
        session = ConversationSession(
            id=str(uuid.uuid4()),
            mode=mode,
            title=title,
            created_at=_now(),
            updated_at=_now(),
        )
        db.add(session)
        db.commit()
        result = self._serialize_session(session, [])
        db.close()
        return result

    def list_sessions(self, mode: str | None = None) -> list[dict[str, Any]]:
        db = self._session()
        query = db.query(ConversationSession)
        if mode:
            query = query.filter(ConversationSession.mode == mode)
        sessions = query.order_by(ConversationSession.updated_at.desc()).all()
        result = [self._serialize_session(session, []) for session in sessions]
        db.close()
        return result

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        db = self._session()
        session = db.query(ConversationSession).filter(ConversationSession.id == session_id).first()
        if not session:
            db.close()
            return None
        messages = (
            db.query(ConversationMessage)
            .filter(ConversationMessage.session_id == session_id)
            .order_by(ConversationMessage.created_at.asc())
            .all()
        )
        result = self._serialize_session(session, messages)
        db.close()
        return result

    def add_message(self, session_id: str, role: str, content: str, metadata: Any | None = None) -> ConversationMessage:
        db = self._session()
        message = ConversationMessage(
            id=str(uuid.uuid4()),
            session_id=session_id,
            role=role,
            content=content,
            metadata_json=_json_dumps(metadata or {}),
            created_at=_now(),
        )
        db.add(message)
        session = db.query(ConversationSession).filter(ConversationSession.id == session_id).first()
        if session:
            session.updated_at = _now()
        db.commit()
        db.refresh(message)
        db.close()
        return message

    async def send_message(self, session_id: str, content: str) -> dict[str, Any]:
        db = self._session()
        session = db.query(ConversationSession).filter(ConversationSession.id == session_id).first()
        if not session:
            db.close()
            raise RuntimeError(f"Unknown session '{session_id}'")
        mode = session.mode
        if not session.title:
            session.title = _session_title(content)
        db.commit()
        db.close()

        self.add_message(session_id, "user", content)
        if mode == "chat":
            return await self._send_chat(session_id, content)
        if mode == "agent":
            return await self._send_agent(session_id, content)
        raise RuntimeError(f"Unsupported session mode: {mode}")

    async def _send_chat(self, session_id: str, content: str) -> dict[str, Any]:
        answer = await ask_obsidian(self.db_path, str(self.vault_path), content, limit=5)
        assistant = self.add_message(
            session_id,
            "assistant",
            answer["answer"],
            {
                "provider": answer.get("provider"),
                "model": answer.get("model"),
                "sources": answer.get("sources", []),
                "mode": "chat",
            },
        )
        return {
            "session": self.get_session(session_id),
            "assistant": self._serialize_message(assistant),
            "sources": answer.get("sources", []),
        }

    async def _send_agent(self, session_id: str, content: str) -> dict[str, Any]:
        plan = await self._build_agent_plan(session_id, content)
        results: list[dict[str, Any]] = []
        last_created_id: str | None = None
        for command in plan.commands:
            resolved = command.replace(LAST_CREATED_ID_PLACEHOLDER, last_created_id or "")
            if LAST_CREATED_ID_PLACEHOLDER in command and not last_created_id:
                raise RuntimeError("Agent plan referenced a created ID before any creation command succeeded")
            result = self.command_runner.run(resolved)
            if result.created_id:
                last_created_id = result.created_id
            else:
                maybe_created = extract_created_id(result.stdout)
                if maybe_created:
                    last_created_id = maybe_created
            results.append(
                {
                    "command": resolved,
                    "exit_code": result.exit_code,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "created_id": result.created_id or last_created_id,
                }
            )
            self.add_message(
                session_id,
                "tool",
                self._format_tool_message(resolved, result.stdout, result.stderr, result.exit_code),
                {
                    "command": resolved,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "exit_code": result.exit_code,
                    "created_id": result.created_id or last_created_id,
                },
            )
            if result.exit_code != 0:
                break
        final_response = plan.response.strip() or "Done."
        if last_created_id:
            lower = final_response.lower()
            if lower.startswith("fake response") or "created ticket" not in lower:
                final_response = f"Created ticket {last_created_id}."
                if len(results) > 1:
                    final_response = f"{final_response} Ran {len(results)} Nina command(s)."
        assistant = self.add_message(
            session_id,
            "assistant",
            final_response,
            {
                "commands": plan.commands,
                "results": results,
                "mode": "agent",
            },
        )
        return {
            "session": self.get_session(session_id),
            "assistant": self._serialize_message(assistant),
            "commands": results,
        }

    async def _build_agent_plan(self, session_id: str, content: str) -> AgentPlan:
        db = self._session()
        history_messages = (
            db.query(ConversationMessage)
            .filter(ConversationMessage.session_id == session_id)
            .order_by(ConversationMessage.created_at.desc())
            .limit(6)
            .all()
        )
        db.close()
        history_lines = []
        for message in reversed(history_messages):
            history_lines.append(f"{message.role}: {message.content}")
        prompt = "\n".join(
            [
                "You are Nina Agent.",
                "Only emit Nina CLI commands, never arbitrary shell commands.",
                "Allowed commands: nina ask, nina job, nina kanban, nina project, nina research, nina task, nina ticket, nina workflow.",
                "If a later command needs the ID of a created ticket, use the placeholder {{last_created_id}}.",
                "Respond in plain text. Put each command on its own line starting with 'nina '.",
                "",
                "Conversation history:",
                *(history_lines or ["(no prior history)"]),
                "",
                "User request:",
                content,
            ]
        )
        response = await self.llm.complete(
            LLMRequest(
                purpose="agent_plan",
                prompt=prompt,
            )
        )
        commands = _extract_commands(response.response)
        assistant_text = _strip_commands(response.response) or response.response.strip()
        if not commands:
            commands = self._fallback_agent_commands(content)
        if not assistant_text:
            assistant_text = "Done."
        return AgentPlan(response=assistant_text, commands=commands)

    def _fallback_agent_commands(self, content: str) -> list[str]:
        lowered = content.lower()
        if "ticket" not in lowered and "task" not in lowered:
            return []
        title = _extract_ticket_title(content)
        description = content.strip()
        commands = [build_nina_command(["ticket", "create", title, "--description", description])]
        target_column = _extract_target_column(content)
        if target_column:
            commands.append(
                build_nina_command(
                    [
                        "ticket",
                        "move",
                        LAST_CREATED_ID_PLACEHOLDER,
                        "--column",
                        target_column,
                        "--position",
                        "0",
                    ]
                )
            )
        return commands

    def _format_tool_message(self, command: str, stdout: str, stderr: str, exit_code: int) -> str:
        parts = [f"Command: {command}", f"Exit code: {exit_code}"]
        if stdout:
            parts.extend(["Stdout:", stdout])
        if stderr:
            parts.extend(["Stderr:", stderr])
        return "\n".join(parts)

    def _serialize_session(self, session: ConversationSession, messages: list[ConversationMessage]) -> dict[str, Any]:
        return {
            "id": session.id,
            "mode": session.mode,
            "title": session.title,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
            "completed_at": session.completed_at,
            "messages": [self._serialize_message(message) for message in messages],
        }

    def _serialize_message(self, message: ConversationMessage) -> dict[str, Any]:
        return {
            "id": message.id,
            "session_id": message.session_id,
            "role": message.role,
            "content": message.content,
            "metadata": _json_loads(message.metadata_json),
            "created_at": message.created_at,
        }
