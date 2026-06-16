from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from nina_core.cli.runner import NinaCommandRunner, build_nina_command, extract_created_id
from nina_core.config.settings import LLMConfig, SearchConfig
from nina_core.llm.default_tools import register_default_tools
from nina_core.llm.provider import LLMRequest, LLMResponse, LLMService, ToolCall
from nina_core.llm.tools import ToolContext, ToolRegistry
from nina_core.llm.write_tools import register_write_tools
from nina_core.models.models import ConversationMessage, ConversationSession
from nina_core.obsidian.service import ObsidianService

LAST_CREATED_ID_PLACEHOLDER = "{{last_created_id}}"
COMMAND_LINE_RE = re.compile(r"(?m)^\s*(?:[-*]\s*)?(nina\s+.+?)\s*$")
LOGGER = logging.getLogger(__name__)

CHAT_SYSTEM_PROMPT = (
    "You are Nina Chat, a local-first assistant for an Obsidian vault. "
    "You can read the vault via tools but you cannot write or run commands. "
    "When a tool returns a list of notes, prefer answering from those notes. "
    "Cite vault paths when relevant. Keep answers concise and grounded in the context."
)

AGENT_SYSTEM_PROMPT = (
    "You are Nina Agent, a local-first assistant that can read the vault and "
    "perform safe Nina operations via tools. You may also run shell commands "
    "limited to the `nina` CLI when no tool covers the action. Each tool's "
    "description lists its expected arguments. Prefer tools over shelling out. "
    "When a later command needs the ID of a created entity, use the placeholder "
    f"{LAST_CREATED_ID_PLACEHOLDER} or rely on tool return values."
)


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
    clause_verb = (
        r"(?:put|move|set|assign|mention|add|include|note|describe|document|capture|track)"
    )
    patterns = [
        rf"create\s+(?:a\s+)?(?:ticket|task)\s*(?:to|for)?\s*(?P<title>.*?)(?:\s+(?:and|then)\s+{clause_verb}\b|;|\.|$)",
        rf"(?:ticket|task)\s*[:\-]\s*(?P<title>.*?)(?:\s+(?:and|then)\s+{clause_verb}\b|;|\.|$)",
    ]
    for pattern in patterns:
        match = re.search(pattern, message, flags=re.IGNORECASE)
        if match:
            title = re.sub(
                rf"\b(?:and|then)\s+{clause_verb}\b.*$",
                "",
                match.group("title"),
                flags=re.IGNORECASE,
            ).strip()
            if title:
                return title
    fallback = re.split(
        rf"\b(?:and|then)\s+{clause_verb}\b", message, maxsplit=1, flags=re.IGNORECASE
    )[0]
    fallback = re.sub(
        r"^(?:create\s+(?:a\s+)?(?:ticket|task)\s*(?:to|for)?\s*)",
        "",
        fallback,
        flags=re.IGNORECASE,
    ).strip()
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


@dataclass
class ToolLoopResult:
    final_text: str
    iterations: int
    tools_used: list[dict[str, Any]]
    sources: list[dict[str, Any]]
    finish_reason: str


def default_tool_registry() -> ToolRegistry:
    """Return a fresh registry populated with Nina's default tools.

    Includes both read and write tools; callers filter by `read_only=True`
    when they want to limit chat sessions to non-mutating tools.
    """

    registry = ToolRegistry()
    register_default_tools(registry)
    register_write_tools(registry)
    return registry


class SessionService:
    def __init__(
        self,
        db_path: str,
        vault_path: str,
        command_runner: NinaCommandRunner | None = None,
        tools: ToolRegistry | None = None,
        llm: LLMService | None = None,
        obsidian: ObsidianService | None = None,
        history_limit: int = 6,
        llm_config: LLMConfig | None = None,
        search_config: "SearchConfig | None" = None,  # noqa: F821
    ) -> None:
        self.db_path = db_path
        self.vault_path = Path(vault_path)
        self.command_runner = command_runner or NinaCommandRunner()
        self.llm = llm or LLMService(db_path, config=llm_config)
        self.obsidian = obsidian or ObsidianService(self.vault_path)
        self.tools = tools or default_tool_registry()
        self.history_limit = history_limit
        self.search_config = search_config
        self.engine = create_engine(f"sqlite:///{db_path}", echo=False)
        self.session_factory = sessionmaker(bind=self.engine)

    def _session(self) -> Session:
        return self.session_factory()

    def _tool_context(self, session_id: str | None) -> ToolContext:
        return ToolContext(
            db_path=self.db_path,
            vault_path=self.vault_path,
            db=self._session(),
            obsidian=self.obsidian,
            search_config=self.search_config,
            session_id=session_id,
        )

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

    def add_message(
        self, session_id: str, role: str, content: str, metadata: Any | None = None
    ) -> ConversationMessage:
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

    def request_cancel(self, session_id: str) -> bool:
        db = self._session()
        try:
            session = (
                db.query(ConversationSession).filter(ConversationSession.id == session_id).first()
            )
            if session is None:
                return False
            session.cancel_requested = 1
            db.commit()
            return True
        finally:
            db.close()

    def clear_cancel(self, session_id: str) -> None:
        db = self._session()
        try:
            session = (
                db.query(ConversationSession).filter(ConversationSession.id == session_id).first()
            )
            if session is not None:
                session.cancel_requested = 0
                db.commit()
        finally:
            db.close()

    def _is_cancelled(self, session_id: str) -> bool:
        db = self._session()
        try:
            session = (
                db.query(ConversationSession).filter(ConversationSession.id == session_id).first()
            )
            return bool(session and session.cancel_requested)
        finally:
            db.close()

    async def send_message(self, session_id: str, content: str) -> dict[str, Any]:
        # Note: cancel flag is intentionally NOT cleared here so that a
        # request_cancel issued mid-run propagates. Callers that want a
        # fresh session should clear_cancel explicitly or POST /sessions.
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

    def _load_history(self, session_id: str, limit: int) -> list[ConversationMessage]:
        if limit <= 0:
            return []
        db = self._session()
        try:
            messages = (
                db.query(ConversationMessage)
                .filter(ConversationMessage.session_id == session_id)
                .order_by(ConversationMessage.created_at.desc())
                .limit(limit)
                .all()
            )
            return list(reversed(messages))
        finally:
            db.close()

    @staticmethod
    def _history_to_messages(history: list[ConversationMessage]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for message in history:
            if message.role in {"user", "assistant", "tool", "system"}:
                entry: dict[str, Any] = {"role": message.role, "content": message.content}
                if message.role == "tool":
                    metadata = _json_loads(message.metadata_json)
                    if isinstance(metadata, dict):
                        if "tool_call_id" in metadata:
                            entry["tool_call_id"] = metadata["tool_call_id"]
                        elif "id" in metadata:
                            entry["tool_call_id"] = metadata["id"]
                out.append(entry)
        return out

    async def _run_tool_loop(
        self,
        session_id: str,
        user_content: str,
        *,
        read_only: bool,
        system_prompt: str,
        max_iterations: int = 5,
        source_tools: set[str] | None = None,
    ) -> ToolLoopResult:
        source_tools = source_tools or set()
        history = self._load_history(session_id, self.history_limit)
        history_messages = self._history_to_messages(history)
        # The most recent message is the user one we just appended; remove it
        # so we don't double-include it after we add it as the final user turn.
        history_messages = [
            m
            for m in history_messages
            if not (m.get("role") == "user" and m.get("content") == user_content)
        ]
        messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
        messages.extend(history_messages)
        messages.append({"role": "user", "content": user_content})

        tools = self.tools.definitions(read_only=read_only)
        sources: list[dict[str, Any]] = []
        tools_used: list[dict[str, Any]] = []
        final_text = ""
        iterations = 0
        finish_reason = "stop"

        # If cancellation was requested before the run, honor it immediately.
        if self._is_cancelled(session_id):
            return ToolLoopResult(
                final_text="Cancelled by user.",
                iterations=0,
                tools_used=[],
                sources=[],
                finish_reason="cancelled",
            )

        for iteration in range(max_iterations):
            iterations = iteration + 1
            if self._is_cancelled(session_id):
                finish_reason = "cancelled"
                final_text = "Cancelled by user."
                break
            response = await self.llm.complete(
                LLMRequest(
                    purpose="chat_tool" if read_only else "agent_tool",
                    messages=list(messages),
                    tools=tools,
                    tool_choice="auto",
                    session_id=session_id,
                    max_tool_iterations=max_iterations,
                )
            )
            tool_calls = response.tool_calls or []
            if not tool_calls:
                final_text = response.response or ""
                finish_reason = response.finish_reason or "stop"
                break
            # Append the assistant's tool-call message so the next iteration sees it.
            messages.append(
                {
                    "role": "assistant",
                    "content": response.response or "",
                    "tool_calls": [
                        {
                            "id": call.id,
                            "type": "function",
                            "function": {
                                "name": call.name,
                                "arguments": json.dumps(call.arguments or {}),
                            },
                        }
                        for call in tool_calls
                    ],
                }
            )
            tool_context = self._tool_context(session_id)
            try:
                for call in tool_calls:
                    summary = self._summarize_tool_call(call)
                    tools_used.append(summary)
                    result = self.tools.execute(call.name, call.arguments or {}, tool_context)
                    if call.name in source_tools:
                        for hit in result.get("results") or []:
                            sources.append(hit)
                    payload = json.dumps(result, ensure_ascii=False, default=str)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.id,
                            "content": payload,
                        }
                    )
                    self.add_message(
                        session_id,
                        "tool",
                        payload,
                        {
                            "id": call.id,
                            "name": call.name,
                            "arguments": call.arguments,
                            "result_summary": _summarize_result(result),
                        },
                    )
            finally:
                tool_context.db.close()
        else:
            finish_reason = "max_iterations"
            if not final_text:
                final_text = "Tool loop reached its iteration limit without a final answer."

        return ToolLoopResult(
            final_text=final_text,
            iterations=iterations,
            tools_used=tools_used,
            sources=_dedupe_sources(sources),
            finish_reason=finish_reason,
        )

    @staticmethod
    def _summarize_tool_call(call: ToolCall) -> dict[str, Any]:
        args = call.arguments or {}
        preview = ""
        for key in ("query", "path", "id", "id_or_title", "id_or_name", "name", "topic", "title"):
            if key in args and isinstance(args[key], (str, int, float)):
                preview = f"{key}={args[key]!s}"
                break
        return {
            "id": call.id,
            "name": call.name,
            "preview": preview,
            "arguments": args,
        }

    async def _send_chat(self, session_id: str, content: str) -> dict[str, Any]:
        result = await self._run_tool_loop(
            session_id,
            content,
            read_only=True,
            system_prompt=CHAT_SYSTEM_PROMPT,
            source_tools={"obsidian_search"},
        )
        # Fallback: if the LLM didn't use any tools, the answer may not be
        # grounded in the vault. Run the legacy one-shot RAG path to make
        # sure the user still gets a sourced answer. Skip when cancelled.
        fallback_sources: list[dict[str, Any]] = []
        fallback_answer: str | None = None
        fallback_provider: str | None = None
        fallback_model: str | None = None
        if not result.tools_used and result.finish_reason != "cancelled":
            from nina_core.search.indexer import ask_obsidian

            ask_result = await ask_obsidian(
                self.db_path,
                str(self.vault_path),
                content,
                limit=5,
                session_id=session_id,
            )
            fallback_answer = ask_result.get("answer", "")
            fallback_sources = ask_result.get("sources", []) or []
            fallback_provider = ask_result.get("provider")
            fallback_model = ask_result.get("model")
        final_text = result.final_text
        sources = result.sources or fallback_sources
        metadata: dict[str, Any] = {
            "mode": "chat",
            "tools_used": result.tools_used,
            "sources": sources,
            "iterations": result.iterations,
            "finish_reason": result.finish_reason,
        }
        if fallback_provider:
            metadata["provider"] = fallback_provider
        if fallback_model:
            metadata["model"] = fallback_model
        if fallback_answer and (not final_text.strip() or not result.tools_used):
            final_text = fallback_answer
        if not final_text and result.finish_reason == "cancelled":
            final_text = "Cancelled by user."
        assistant = self.add_message(
            session_id,
            "assistant",
            final_text,
            metadata,
        )
        return {
            "session": self.get_session(session_id),
            "assistant": self._serialize_message(assistant),
            "sources": sources,
            "tools_used": result.tools_used,
        }

    async def _send_agent(self, session_id: str, content: str) -> dict[str, Any]:
        # First try the tool loop with the full tool set (including write tools
        # if registered). If the LLM doesn't emit any tool calls, fall back to
        # the legacy text-based command parser for backward compatibility.
        tools = self.tools.definitions(read_only=False)
        if tools:
            try:
                result = await self._run_tool_loop(
                    session_id,
                    content,
                    read_only=False,
                    system_prompt=AGENT_SYSTEM_PROMPT,
                    max_iterations=6,
                )
                if result.tools_used:
                    final_response = result.final_text.strip() or "Done."
                    assistant = self.add_message(
                        session_id,
                        "assistant",
                        final_response,
                        {
                            "mode": "agent",
                            "tools_used": result.tools_used,
                            "iterations": result.iterations,
                            "finish_reason": result.finish_reason,
                        },
                    )
                    return {
                        "session": self.get_session(session_id),
                        "assistant": self._serialize_message(assistant),
                        "tools_used": result.tools_used,
                    }
            except Exception as exc:
                # Fall through to text-based path so the agent still does *something* useful.
                LOGGER.debug("agent tool loop failed, falling back: %s", exc)
        # Fallback path
        plan = self._build_agent_plan(session_id, content)
        results: list[dict[str, Any]] = []
        last_created_id: str | None = None
        for command in plan.commands:
            resolved = command.replace(LAST_CREATED_ID_PLACEHOLDER, last_created_id or "")
            if LAST_CREATED_ID_PLACEHOLDER in command and not last_created_id:
                raise RuntimeError(
                    "Agent plan referenced a created ID before any creation command succeeded"
                )
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

    def _build_agent_plan(self, session_id: str, content: str) -> AgentPlan:
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
        response = self._run_agent_plan_sync(prompt)
        commands = _extract_commands(response.response)
        assistant_text = _strip_commands(response.response) or response.response.strip()
        if not commands:
            commands = self._fallback_agent_commands(content)
        if not assistant_text:
            assistant_text = "Done."
        return AgentPlan(response=assistant_text, commands=commands)

    def _run_agent_plan_sync(self, prompt: str) -> LLMResponse:
        """Run the legacy agent plan prompt synchronously.

        Used as a fallback when the LLM doesn't emit tool calls. Synchronous
        because the legacy path was originally sync; we delegate to the same
        provider used by the tool loop.
        """

        import asyncio

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.llm.complete(LLMRequest(purpose="agent_plan", prompt=prompt)))
        # We're inside a running loop; fall back to a thread so the legacy
        # path still works when called from async contexts (e.g. tests).
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                asyncio.run,
                self.llm.complete(LLMRequest(purpose="agent_plan", prompt=prompt)),
            )
            return future.result()

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

    def _serialize_session(
        self, session: ConversationSession, messages: list[ConversationMessage]
    ) -> dict[str, Any]:
        return {
            "id": session.id,
            "mode": session.mode,
            "title": session.title,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
            "completed_at": session.completed_at,
            "cancel_requested": bool(session.cancel_requested),
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


def _summarize_result(result: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(result, dict):
        return {"type": str(type(result).__name__)}
    summary: dict[str, Any] = {"keys": sorted(result.keys())}
    if "results" in result and isinstance(result["results"], list):
        summary["results_count"] = len(result["results"])
    if "notes" in result and isinstance(result["notes"], list):
        summary["notes_count"] = len(result["notes"])
    if "tickets" in result and isinstance(result["tickets"], list):
        summary["tickets_count"] = len(result["tickets"])
    if "ticket" in result and isinstance(result["ticket"], dict):
        summary["ticket_id"] = result["ticket"].get("id")
    if "project" in result and isinstance(result["project"], dict):
        summary["project_id"] = result["project"].get("id")
    if "note" in result and isinstance(result["note"], dict):
        summary["note_path"] = result["note"].get("path")
    if "error" in result:
        summary["error"] = result["error"]
    return summary


def _dedupe_sources(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, Any]] = []
    for source in sources:
        path = source.get("path") or ""
        title = source.get("title") or ""
        key = (path, title)
        if key in seen:
            continue
        seen.add(key)
        out.append(source)
    return out
