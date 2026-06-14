from __future__ import annotations

import base64
import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import httpx
from openai import OpenAI
from pydantic import BaseModel, Field
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from nina_core.models.models import LLMInteraction

CODEX_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
CODEX_ISSUER = "https://auth.openai.com"
CODEX_BASE_URL = "https://chatgpt.com/backend-api/codex"
CODEX_AUTH_FILE_DEFAULT = "~/.codex/auth.json"
CODEX_REFRESH_LEEWAY_MS = 5 * 60 * 1000


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_millis() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


class ToolDefinition(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class LLMRequest(BaseModel):
    purpose: str
    prompt: str = ""
    messages: list[dict[str, Any]] | None = None
    tools: list[ToolDefinition] | None = None
    tool_choice: Literal["auto", "required", "none"] | None = "auto"
    model: str | None = None
    workflow_run_id: str | None = None
    session_id: str | None = None
    max_tool_iterations: int = 5


class LLMResponse(BaseModel):
    response: str
    model: str
    provider: str
    tool_calls: list[ToolCall] = Field(default_factory=list)
    finish_reason: str | None = None


class LLMProvider:
    async def complete(self, request: LLMRequest) -> LLMResponse:
        raise NotImplementedError


@dataclass
class CodexAuth:
    path: Path
    raw: dict[str, Any]
    access_token: str
    refresh_token: str | None
    expires_at: int | None
    account_id: str | None

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return self.expires_at <= _now_millis() + CODEX_REFRESH_LEEWAY_MS


@dataclass
class CodexAuthStatus:
    connected: bool
    account_id: str | None
    expires_at: int | None
    detail: str | None = None


def codex_auth_status() -> CodexAuthStatus:
    try:
        auth = _load_codex_auth()
    except Exception as exc:
        return CodexAuthStatus(connected=False, account_id=None, expires_at=None, detail=str(exc))
    return CodexAuthStatus(connected=True, account_id=auth.account_id, expires_at=auth.expires_at)


def _load_codex_auth() -> CodexAuth:
    path = Path(os.path.expanduser(os.environ.get("CODEX_AUTH_FILE", CODEX_AUTH_FILE_DEFAULT)))
    if not path.exists():
        raise RuntimeError(f"Codex auth file not found: {path}")
    try:
        raw = json.loads(path.read_text())
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Failed to read Codex auth file: {path}") from exc
    if not isinstance(raw, dict):
        raise RuntimeError(f"Invalid Codex auth file: {path}")

    auth = _parse_codex_auth(path, raw)
    if auth.access_token and auth.refresh_token and auth.is_expired():
        refreshed = _refresh_codex_auth(auth.refresh_token)
        auth = _store_codex_auth(auth, refreshed)
    return auth


def _parse_codex_auth(path: Path, raw: dict[str, Any]) -> CodexAuth:
    has_tokens = isinstance(raw.get("tokens"), dict)
    tokens = raw.get("tokens") if has_tokens else {}
    if raw.get("auth_mode") in {"chatgpt", "chatgptAuthTokens"} or has_tokens:
        access_token = _string_or_none(tokens.get("access_token"))
        refresh_token = _string_or_none(tokens.get("refresh_token"))
        expires_at = _int_or_none(tokens.get("expires_at") or tokens.get("expires"))
        account_id = _string_or_none(tokens.get("account_id") or tokens.get("accountId"))
    elif raw.get("type") == "oauth":
        access_token = _string_or_none(raw.get("access") or raw.get("access_token"))
        refresh_token = _string_or_none(raw.get("refresh") or raw.get("refresh_token"))
        expires_at = _int_or_none(raw.get("expires") or raw.get("expires_at"))
        account_id = _string_or_none(raw.get("account_id") or raw.get("accountId"))
    else:
        raise RuntimeError(f"Unsupported Codex auth file format: {path}")

    if not access_token:
        raise RuntimeError(f"Codex auth file does not contain an access token: {path}")
    if account_id is None:
        account_id = _extract_account_id(access_token)
    return CodexAuth(
        path=path,
        raw=raw,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=expires_at,
        account_id=account_id,
    )


def _store_codex_auth(auth: CodexAuth, tokens: dict[str, Any]) -> CodexAuth:
    raw = dict(auth.raw)
    if raw.get("auth_mode") in {"chatgpt", "chatgptAuthTokens"} or isinstance(
        raw.get("tokens"), dict
    ):
        current = dict(raw.get("tokens") or {})
        current["access_token"] = tokens["access_token"]
        current["refresh_token"] = tokens["refresh_token"]
        current["expires_at"] = tokens["expires_at"]
        if tokens.get("account_id") is not None:
            current["account_id"] = tokens["account_id"]
        raw["tokens"] = current
    else:
        raw["type"] = "oauth"
        raw["access"] = tokens["access_token"]
        raw["refresh"] = tokens["refresh_token"]
        raw["expires"] = tokens["expires_at"]
        if tokens.get("account_id") is not None:
            raw["accountId"] = tokens["account_id"]
    auth.path.write_text(json.dumps(raw, indent=2, sort_keys=False))
    return CodexAuth(
        path=auth.path,
        raw=raw,
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        expires_at=tokens["expires_at"],
        account_id=tokens.get("account_id") or auth.account_id,
    )


def _refresh_codex_auth(refresh_token: str) -> dict[str, Any]:
    response = httpx.post(
        f"{CODEX_ISSUER}/oauth/token",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": CODEX_CLIENT_ID,
        },
        timeout=30,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"Codex token refresh failed: {response.status_code}")
    payload = response.json()
    access_token = _string_or_none(payload.get("access_token"))
    refresh_token = _string_or_none(payload.get("refresh_token")) or refresh_token
    expires_in = _int_or_none(payload.get("expires_in")) or 3600
    if not access_token:
        raise RuntimeError("Codex token refresh response did not include an access token")
    account_id = _extract_account_id(access_token)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": _now_millis() + (expires_in * 1000),
        "account_id": account_id,
    }


def _string_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _extract_account_id(token: str) -> str | None:
    parts = token.split(".")
    if len(parts) != 3:
        return None
    try:
        payload = json.loads(_base64url_decode(parts[1]))
    except (ValueError, TypeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    account_id = payload.get("chatgpt_account_id")
    if isinstance(account_id, str) and account_id:
        return account_id
    api_auth = payload.get("https://api.openai.com/auth")
    if isinstance(api_auth, dict):
        account_id = api_auth.get("chatgpt_account_id")
        if isinstance(account_id, str) and account_id:
            return account_id
    organizations = payload.get("organizations")
    if isinstance(organizations, list) and organizations:
        first = organizations[0]
        if isinstance(first, dict):
            account_id = first.get("id")
            if isinstance(account_id, str) and account_id:
                return account_id
    return None


def _base64url_decode(value: str) -> str:
    remainder = len(value) % 4
    if remainder:
        value += "=" * (4 - remainder)
    return base64.urlsafe_b64decode(value.encode()).decode()


class CodexAuthProvider(LLMProvider):
    def __init__(self) -> None:
        self.model = os.environ.get("NINA_LLM_MODEL", "gpt-5")
        self.auth = _load_codex_auth()
        self.client = OpenAI(
            api_key=self.auth.access_token,
            base_url=CODEX_BASE_URL,
            default_headers=self._default_headers(),
        )

    def _default_headers(self, session_id: str | None = None) -> dict[str, str]:
        headers = {"originator": "nina"}
        if self.auth.account_id:
            headers["ChatGPT-Account-Id"] = self.auth.account_id
        if session_id:
            headers["session-id"] = session_id
        return headers

    def _build_input(self, request: LLMRequest) -> Any:
        if request.messages:
            return _messages_to_responses_input(request.messages, request.prompt)
        return [
            {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": request.prompt or ""}],
            }
        ]

    def _build_tools(self, request: LLMRequest) -> list[dict[str, Any]] | None:
        if not request.tools:
            return None
        return [
            {
                "type": "function",
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters or {"type": "object", "properties": {}},
            }
            for tool in request.tools
        ]

    async def complete(self, request: LLMRequest) -> LLMResponse:
        model = request.model or self.model
        parts: list[str] = []
        tool_calls: dict[str, dict[str, Any]] = {}
        finish_reason: str | None = None
        stream_kwargs: dict[str, Any] = {
            "model": model,
            "store": False,
            "extra_headers": self._default_headers(request.session_id),
            "instructions": (
                "You are Nina, a local-first assistant for notes, tasks, and workflows. "
                "Answer clearly and concisely."
            ),
            "input": self._build_input(request),
        }
        tools = self._build_tools(request)
        if tools:
            stream_kwargs["tools"] = tools
            stream_kwargs["tool_choice"] = request.tool_choice or "auto"
        with self.client.responses.stream(**stream_kwargs) as stream:
            for event in stream:
                event_type = getattr(event, "type", None)
                if event_type == "response.output_text.delta":
                    delta = getattr(event, "delta", None)
                    if isinstance(delta, str) and delta:
                        parts.append(delta)
                elif event_type == "response.output_item.added":
                    item = getattr(event, "item", None)
                    if item is not None and getattr(item, "type", None) == "function_call":
                        call_id = getattr(item, "call_id", None) or getattr(item, "id", None) or ""
                        tool_calls[call_id] = {
                            "id": call_id,
                            "name": getattr(item, "name", "") or "",
                            "arguments": "",
                        }
                elif event_type == "response.function_call_arguments.delta":
                    call_id = (
                        getattr(event, "call_id", None) or getattr(event, "item_id", None) or ""
                    )
                    delta = getattr(event, "delta", None)
                    if call_id in tool_calls and isinstance(delta, str):
                        tool_calls[call_id]["arguments"] = (
                            tool_calls[call_id].get("arguments", "") + delta
                        )
                elif event_type == "response.function_call_arguments.done":
                    call_id = (
                        getattr(event, "call_id", None) or getattr(event, "item_id", None) or ""
                    )
                    final_args = getattr(event, "arguments", None)
                    if call_id in tool_calls and isinstance(final_args, str):
                        tool_calls[call_id]["arguments"] = final_args
                elif event_type == "response.completed":
                    response = getattr(event, "response", None)
                    if response is not None:
                        finish_reason = getattr(response, "status", None) or getattr(
                            response, "finish_reason", None
                        )
                        if not parts and response is not None:
                            fallback = getattr(response, "output_text", "") or ""
                            if fallback:
                                parts.append(fallback)
                            else:
                                extracted = _extract_response_text(response)
                                if extracted:
                                    parts.append(extracted)
                        for item in getattr(response, "output", []) or []:
                            if getattr(item, "type", None) != "function_call":
                                continue
                            call_id = (
                                getattr(item, "call_id", None) or getattr(item, "id", None) or ""
                            )
                            arguments = getattr(item, "arguments", "")
                            if call_id in tool_calls:
                                if isinstance(arguments, str):
                                    tool_calls[call_id]["arguments"] = arguments
                                tool_calls[call_id]["name"] = (
                                    getattr(item, "name", "") or tool_calls[call_id]["name"]
                                )
        content = "".join(parts)
        parsed_calls: list[ToolCall] = []
        for raw in tool_calls.values():
            args = raw.get("arguments") or ""
            try:
                parsed = json.loads(args) if isinstance(args, str) and args else {}
            except json.JSONDecodeError:
                parsed = {"_raw": args}
            parsed_calls.append(
                ToolCall(
                    id=str(raw.get("id") or ""), name=str(raw.get("name") or ""), arguments=parsed
                )
            )
        return LLMResponse(
            response=content,
            model=model,
            provider="codex",
            tool_calls=parsed_calls,
            finish_reason=finish_reason,
        )


CodexCliProvider = CodexAuthProvider


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is required for the OpenAI provider")
        self.client = OpenAI(api_key=self.api_key)
        self.model = os.environ.get("NINA_LLM_MODEL", "gpt-5")

    async def complete(self, request: LLMRequest) -> LLMResponse:
        model = request.model or self.model
        messages = request.messages or [{"role": "user", "content": request.prompt or ""}]
        kwargs: dict[str, Any] = {"model": model, "messages": messages}
        if request.tools:
            kwargs["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters or {"type": "object", "properties": {}},
                    },
                }
                for tool in request.tools
            ]
            kwargs["tool_choice"] = request.tool_choice or "auto"
        response = self.client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        content = choice.message.content or ""
        tool_calls: list[ToolCall] = []
        for call in getattr(choice.message, "tool_calls", None) or []:
            arguments: Any = {}
            raw = getattr(call.function, "arguments", "") or ""
            try:
                arguments = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                arguments = {"_raw": raw}
            tool_calls.append(
                ToolCall(
                    id=str(getattr(call, "id", "") or ""),
                    name=str(getattr(call.function, "name", "") or ""),
                    arguments=arguments,
                )
            )
        finish_reason = getattr(choice, "finish_reason", None)
        return LLMResponse(
            response=content,
            model=model,
            provider="openai",
            tool_calls=tool_calls,
            finish_reason=finish_reason,
        )


class FakeProvider(LLMProvider):
    model = "fake"

    def __init__(self) -> None:
        self.queued_tool_calls: list[list[ToolCall]] = []
        self.queued_responses: list[str] = []
        self.call_count = 0

    def queue_tool_calls(self, tool_calls: list[ToolCall], final_text: str) -> None:
        self.queued_tool_calls.append(tool_calls)
        self.queued_responses.append(final_text)

    def queue_text(self, text: str) -> None:
        self.queued_tool_calls.append([])
        self.queued_responses.append(text)

    async def complete(self, request: LLMRequest) -> LLMResponse:
        index = min(
            self.call_count, max(len(self.queued_tool_calls), len(self.queued_responses)) - 1
        )
        tool_calls = self.queued_tool_calls[index] if self.queued_tool_calls else []
        response_text = (
            self.queued_responses[index]
            if self.queued_responses
            else f"Fake response for: {(request.prompt or '')[:50]}..."
        )
        self.call_count += 1
        return LLMResponse(
            response=response_text,
            model="fake",
            provider="fake",
            tool_calls=list(tool_calls),
            finish_reason="tool_calls" if tool_calls else "stop",
        )


class LLMService:
    def __init__(self, db_path: str, provider: LLMProvider | None = None) -> None:
        self.db_path = db_path
        self.provider: LLMProvider = provider or self._build_provider()

    def _build_provider(self) -> LLMProvider:
        provider = os.environ.get("NINA_LLM_PROVIDER", "codex").lower()
        if provider == "fake":
            return FakeProvider()
        if provider == "openai":
            return OpenAIProvider()
        if provider == "codex":
            return CodexAuthProvider()
        raise RuntimeError(f"Unsupported LLM provider: {provider}")

    def _session(self) -> Session:
        engine = create_engine(f"sqlite:///{self.db_path}", echo=False)
        SessionLocal = sessionmaker(bind=engine)
        return SessionLocal()

    def log_interaction(self, interaction: LLMInteraction) -> None:
        db = self._session()
        db.merge(interaction)
        db.commit()
        db.close()

    async def complete(self, request: LLMRequest) -> LLMResponse:
        provider_name = os.environ.get("NINA_LLM_PROVIDER", "codex")
        model = request.model or getattr(self.provider, "model", request.model)
        interaction = LLMInteraction(
            id=str(uuid.uuid4()),
            provider=provider_name,
            model=model,
            purpose=request.purpose,
            prompt=request.prompt,
            status="pending",
            workflow_run_id=request.workflow_run_id,
            created_at=_now(),
        )
        self.log_interaction(interaction)
        try:
            response = await self.provider.complete(request)
            interaction.provider = response.provider
            interaction.model = response.model
            interaction.response = response.response
            interaction.status = "completed"
            interaction.completed_at = _now()
        except Exception as e:
            interaction.status = "failed"
            interaction.error = str(e)
            self.log_interaction(interaction)
            raise
        self.log_interaction(interaction)
        return response


def _extract_response_text(response: Any) -> str:
    parts: list[str] = []
    for item in getattr(response, "output", []) or []:
        if getattr(item, "type", None) != "message":
            continue
        for content in getattr(item, "content", []) or []:
            if getattr(content, "type", None) != "output_text":
                continue
            text = getattr(content, "text", None)
            if isinstance(text, str) and text:
                parts.append(text)
    return "".join(parts)


def _messages_to_responses_input(
    messages: list[dict[str, Any]], fallback_prompt: str
) -> list[dict[str, Any]]:
    """Translate OpenAI chat-style messages into the Responses API input shape.

    System messages are dropped (Responses uses the `instructions` argument).
    Assistant tool_calls are converted into the Responses function_call items
    with the matching call_id, and role=tool messages are converted into
    function_call_output items referencing the call_id.
    """

    converted: list[dict[str, Any]] = []
    for message in messages:
        role = message.get("role")
        if role == "system":
            continue
        if role == "user":
            content = message.get("content", "")
            if isinstance(content, list):
                converted.append({"type": "message", "role": "user", "content": content})
            else:
                converted.append(
                    {
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_text", "text": str(content)}],
                    }
                )
        elif role == "assistant":
            tool_calls = message.get("tool_calls") or []
            if tool_calls:
                for call in tool_calls:
                    function = call.get("function", {}) if isinstance(call, dict) else {}
                    call_id = call.get("id") or call.get("call_id") or ""
                    name = function.get("name", "") if isinstance(function, dict) else ""
                    arguments = function.get("arguments", "") if isinstance(function, dict) else ""
                    if isinstance(arguments, dict):
                        arguments = json.dumps(arguments)
                    converted.append(
                        {
                            "type": "function_call",
                            "name": name,
                            "arguments": arguments or "",
                            "call_id": call_id,
                        }
                    )
            content = message.get("content", "")
            if content:
                if isinstance(content, list):
                    converted.append({"type": "message", "role": "assistant", "content": content})
                else:
                    converted.append(
                        {
                            "type": "message",
                            "role": "assistant",
                            "content": [{"type": "output_text", "text": str(content)}],
                        }
                    )
        elif role == "tool":
            call_id = (
                message.get("tool_call_id") or message.get("call_id") or message.get("id") or ""
            )
            output = message.get("content", "")
            if not isinstance(output, str):
                output = json.dumps(output)
            converted.append(
                {
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": output,
                }
            )
    if not converted and fallback_prompt:
        converted.append(
            {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": fallback_prompt}],
            }
        )
    return converted
