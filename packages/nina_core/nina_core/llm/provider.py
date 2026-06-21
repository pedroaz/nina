from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import subprocess
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from nina_core.codex.client import CodexClient
from nina_core.config.settings import LLMConfig
from nina_core.models.models import LLMInteraction


CODEX_DEFAULT_MODEL = "codex-cli"
CODEX_DEFAULT_TIMEOUT_SECONDS = 180.0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


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
class CodexAuthStatus:
    connected: bool
    account_id: str | None
    expires_at: int | None
    detail: str | None = None


def _codex_binary() -> str:
    configured = os.environ.get("NINA_CODEX_BINARY", "").strip()
    return configured or (shutil.which("codex") or "")


def codex_auth_status() -> CodexAuthStatus:
    """Compatibility status object for callers that used to check Codex OAuth directly.

    Nina no longer reads Codex auth tokens or calls ChatGPT/OpenAI endpoints itself.
    Authentication is owned by the local Codex CLI process.
    """

    binary = _codex_binary()
    if not binary:
        return CodexAuthStatus(
            connected=False,
            account_id=None,
            expires_at=None,
            detail="codex binary not found on PATH",
        )
    return CodexAuthStatus(
        connected=True,
        account_id=None,
        expires_at=None,
        detail=f"Codex CLI: {binary}",
    )


class CodexCliProvider(LLMProvider):
    """LLM provider backed only by `codex exec`.

    The Codex CLI is the sole AI boundary. Tool calls are requested via a small
    JSON envelope so the existing Nina chat/agent tool loop can stay provider
    independent.
    """

    def __init__(
        self,
        model: str | None = None,
        *,
        timeout: float = CODEX_DEFAULT_TIMEOUT_SECONDS,
        binary_path: str | None = None,
    ) -> None:
        self.model = model or os.environ.get("NINA_LLM_MODEL", CODEX_DEFAULT_MODEL)
        self.timeout = timeout
        self.client = CodexClient(
            "127.0.0.1",
            0,
            "",
            "",
            timeout=timeout,
            binary_path=binary_path or os.environ.get("NINA_CODEX_BINARY"),
        )

    async def complete(self, request: LLMRequest) -> LLMResponse:
        prompt = self._build_prompt(request)
        result = await self.client.exec(
            prompt,
            json_mode=False,
            timeout=self.timeout,
            output_last_message=True,
        )
        text = (result.last_message or result.stdout or "").strip()
        return self._parse_result(text, request)

    def _build_prompt(self, request: LLMRequest) -> str:
        messages = request.messages or [{"role": "user", "content": request.prompt or ""}]
        tools = [tool.model_dump() for tool in request.tools or []]
        return "\n".join(
            [
                "You are Nina, a local-first assistant for notes, tasks, and workflows.",
                "You are running through the local Codex CLI. Do not assume direct API access.",
                "Return exactly one JSON object and no markdown fences.",
                "Schema:",
                '{"response":"text for the user","tool_calls":[{"id":"call_1","name":"tool_name","arguments":{}}],"finish_reason":"stop|tool_calls"}',
                "Use tool_calls only when a listed tool is needed. If calling tools, keep response empty or brief.",
                "If no tool is needed, return an empty tool_calls list and finish_reason stop.",
                f"Purpose: {request.purpose}",
                f"Preferred model label for logging only: {request.model or self.model}",
                f"Tool choice: {request.tool_choice or 'auto'}",
                "Messages JSON:",
                json.dumps(messages, ensure_ascii=False, default=str),
                "Tools JSON:",
                json.dumps(tools, ensure_ascii=False, default=str),
            ]
        )

    def _parse_result(self, text: str, request: LLMRequest) -> LLMResponse:
        payload = _extract_json_object(text)
        if payload is None:
            return LLMResponse(
                response=text,
                model=request.model or self.model,
                provider="codex",
                tool_calls=[],
                finish_reason="stop",
            )

        raw_calls = payload.get("tool_calls") or []
        parsed_calls: list[ToolCall] = []
        if isinstance(raw_calls, list):
            for index, raw in enumerate(raw_calls, start=1):
                if not isinstance(raw, dict):
                    continue
                name = raw.get("name")
                if not isinstance(name, str) or not name:
                    continue
                arguments = raw.get("arguments") or {}
                if isinstance(arguments, str):
                    try:
                        arguments = json.loads(arguments) if arguments else {}
                    except json.JSONDecodeError:
                        arguments = {"_raw": arguments}
                if not isinstance(arguments, dict):
                    arguments = {"value": arguments}
                call_id = raw.get("id")
                parsed_calls.append(
                    ToolCall(
                        id=str(call_id or f"call_{index}"),
                        name=name,
                        arguments=arguments,
                    )
                )
        response_text = payload.get("response")
        if not isinstance(response_text, str):
            response_text = ""
        finish_reason = payload.get("finish_reason")
        if not isinstance(finish_reason, str) or not finish_reason:
            finish_reason = "tool_calls" if parsed_calls else "stop"
        return LLMResponse(
            response=response_text,
            model=request.model or self.model,
            provider="codex",
            tool_calls=parsed_calls,
            finish_reason=finish_reason,
        )


class OpenAICompatibleProvider(LLMProvider):
    """Talk to a local OpenAI-compatible HTTP server without API keys.

    This is kept only for local runtimes such as llama.cpp/vLLM/LM Studio. Nina's
    default and cloud-backed path is Codex CLI.
    """

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        if not base_url:
            raise RuntimeError(
                "base_url is required for the openai_compatible provider. "
                "Set llm.base_url in config (e.g. http://localhost:11434/v1)."
            )
        self.base_url = base_url.rstrip("/")
        self.model = model or "local-model"

    async def complete(self, request: LLMRequest) -> LLMResponse:
        model = request.model or self.model
        messages = request.messages or [{"role": "user", "content": request.prompt or ""}]
        payload: dict[str, Any] = {"model": model, "messages": messages}
        if request.tools:
            payload["tools"] = [
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
            payload["tool_choice"] = request.tool_choice or "auto"
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(f"{self.base_url}/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()
        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        content = message.get("content") or ""
        tool_calls: list[ToolCall] = []
        for call in message.get("tool_calls") or []:
            function = call.get("function") or {}
            raw_args = function.get("arguments") or "{}"
            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            except json.JSONDecodeError:
                args = {"_raw": raw_args}
            if not isinstance(args, dict):
                args = {"value": args}
            tool_calls.append(
                ToolCall(
                    id=str(call.get("id") or ""),
                    name=str(function.get("name") or ""),
                    arguments=args,
                )
            )
        return LLMResponse(
            response=str(content),
            model=model,
            provider="openai_compatible",
            tool_calls=tool_calls,
            finish_reason=choice.get("finish_reason"),
        )


class OllamaProvider(OpenAICompatibleProvider):
    DEFAULT_BASE_URL = "http://localhost:11434/v1"
    DEFAULT_MODEL = "gemma3:4b"

    def __init__(self, base_url: str | None = None, model: str | None = None) -> None:
        super().__init__(base_url=base_url or self.DEFAULT_BASE_URL, model=model or self.DEFAULT_MODEL)

    async def complete(self, request: LLMRequest) -> LLMResponse:
        response = await super().complete(request)
        response.provider = "ollama"
        return response


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
    def __init__(
        self,
        db_path: str,
        provider: LLMProvider | None = None,
        config: LLMConfig | None = None,
        codex_binary_path: str | None = None,
    ) -> None:
        self.db_path = db_path
        self.config = config or LLMConfig()
        self.codex_binary_path = codex_binary_path
        self.provider: LLMProvider = provider or self._build_provider()

    def _build_provider(self) -> LLMProvider:
        provider = (self.config.provider or "codex").lower()
        if provider == "fake":
            return FakeProvider()
        if provider in {"codex", "openai", "openai_web", "web"}:
            return CodexCliProvider(model=self.config.model, binary_path=self.codex_binary_path)
        if provider == "ollama":
            return OllamaProvider(base_url=self.config.base_url, model=self.config.model)
        if provider in {"openai_compatible", "llamacpp", "vllm", "lmstudio"}:
            return OpenAICompatibleProvider(base_url=self.config.base_url, model=self.config.model)
        raise RuntimeError(
            f"Unsupported LLM provider: {provider}. Expected one of: codex, ollama, openai_compatible, fake."
        )

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
        provider_name = self.config.provider
        model = request.model or self.config.model or getattr(self.provider, "model", None)
        interaction = LLMInteraction(
            id=str(uuid.uuid4()),
            provider=provider_name,
            model=model or "",
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


def _extract_json_object(text: str) -> dict[str, Any] | None:
    stripped = text.strip()
    if not stripped:
        return None
    candidates = [stripped]
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, flags=re.DOTALL)
    if fence:
        candidates.append(fence.group(1))
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end > start:
        candidates.append(stripped[start : end + 1])
    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return None


@dataclass
class LLMProviderStatus:
    provider: str
    model: str
    base_url: str | None
    reachable: bool
    model_present: bool
    detail: str | None = None
    available_models: list[str] | None = None


def check_provider_status(config: LLMConfig, *, timeout: float = 3.0) -> LLMProviderStatus:
    provider = (config.provider or "codex").lower()
    base_url = config.base_url
    model = config.model
    try:
        if provider == "ollama":
            return _check_ollama(base_url, model, timeout=timeout)
        if provider in {"openai_compatible", "llamacpp", "vllm", "lmstudio"}:
            return _check_openai_compatible(base_url, model, timeout=timeout)
        if provider in {"codex", "openai", "openai_web", "web"}:
            binary = _codex_binary()
            if not binary:
                return LLMProviderStatus(
                    provider="codex",
                    model=model,
                    base_url=None,
                    reachable=False,
                    model_present=False,
                    detail="codex binary not found on PATH",
                )
            result = subprocess.run(
                [binary, "--version"],
                text=True,
                capture_output=True,
                timeout=timeout,
                check=False,
            )
            version = (result.stdout or result.stderr or "").strip().splitlines()
            detail = version[0] if version else None
            return LLMProviderStatus(
                provider="codex",
                model=model,
                base_url=None,
                reachable=result.returncode == 0,
                model_present=True,
                detail=detail if result.returncode == 0 else (detail or "codex --version failed"),
            )
        if provider == "fake":
            return LLMProviderStatus(
                provider=provider,
                model=model,
                base_url=None,
                reachable=True,
                model_present=True,
                detail="fake provider is for tests/CI",
            )
    except Exception as exc:  # noqa: BLE001
        return LLMProviderStatus(
            provider=provider or "unknown",
            model=model,
            base_url=base_url,
            reachable=False,
            model_present=False,
            detail=str(exc),
        )
    return LLMProviderStatus(
        provider=provider or "unknown",
        model=model,
        base_url=base_url,
        reachable=False,
        model_present=False,
        detail=f"Unknown provider: {provider!r}",
    )


def _check_ollama(base_url: str | None, model: str | None, *, timeout: float) -> LLMProviderStatus:
    url = (base_url or OllamaProvider.DEFAULT_BASE_URL).rstrip("/")
    ollama_root = url[:-3] if url.endswith("/v1") else url
    tags_url = f"{ollama_root}/api/tags"
    response = httpx.get(tags_url, timeout=timeout)
    response.raise_for_status()
    models = [item.get("name", "") for item in response.json().get("models", [])]
    present = bool(model and model in models)
    return LLMProviderStatus(
        provider="ollama",
        model=model or "",
        base_url=url,
        reachable=True,
        model_present=present,
        available_models=models,
        detail=None if present else f"Model not found. Run: ollama pull {model}" if model else None,
    )


def _check_openai_compatible(
    base_url: str | None,
    model: str | None,
    *,
    timeout: float,
) -> LLMProviderStatus:
    if not base_url:
        return LLMProviderStatus(
            provider="openai_compatible",
            model=model or "",
            base_url=None,
            reachable=False,
            model_present=False,
            detail="llm.base_url is not set",
        )
    url = base_url.rstrip("/")
    response = httpx.get(f"{url}/models", timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    raw_models = payload.get("data") or payload.get("models") or []
    models = [str(item.get("id") or item.get("name") or item) for item in raw_models]
    present = bool(model and (not models or model in models))
    return LLMProviderStatus(
        provider="openai_compatible",
        model=model or "",
        base_url=url,
        reachable=True,
        model_present=present,
        available_models=models,
        detail=None if present else f"Model {model!r} was not reported by {url}",
    )
