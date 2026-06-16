from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest
from nina_core.llm import provider as provider_module
from nina_core.llm.provider import CodexAuthProvider, LLMRequest, LLMService, OpenAIProvider


class FakeChatCompletions:
    def __init__(self, captured: dict[str, object]) -> None:
        self.captured = captured
        self.captured["chat_tool_calls"] = []

    def create(self, model: str, messages: list[dict[str, str]], **kwargs: object):
        self.captured["chat_model"] = model
        self.captured["chat_messages"] = messages
        self.captured["chat_kwargs"] = kwargs
        outer = self

        class Message:
            content = "ok"
            tool_calls = outer.captured.get("chat_tool_calls") or []

        class Choice:
            message = Message()
            finish_reason = "tool_calls" if outer.captured.get("chat_tool_calls") else "stop"

        class Response:
            choices = [Choice()]

        return Response()


class FakeResponses:
    def __init__(self, captured: dict[str, object]) -> None:
        self.captured = captured

    def create(self, **kwargs):
        self.captured["responses_create"] = kwargs

        class Response:
            output_text = "codex ok"
            output = []

        return Response()

    def stream(self, **kwargs):
        self.captured["responses_stream"] = kwargs

        class Response:
            output_text = "codex ok"
            output = []

        class Event:
            def __init__(self, event_type: str, delta: str | None = None):
                self.type = event_type
                self.delta = delta
                self.response = Response()

        class Stream:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return None

            def __iter__(self):
                yield Event("response.created")
                yield Event("response.in_progress")
                yield Event("response.output_text.delta", "codex ok")
                yield Event("response.output_text.done")
                yield Event("response.completed")

            def get_final_response(self):
                return Response()

        return Stream()


class FakeOpenAI:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.captured: dict[str, object] = kwargs
        self.chat = type("Chat", (), {"completions": FakeChatCompletions(self.captured)})()
        self.responses = FakeResponses(self.captured)


@pytest.mark.asyncio
async def test_openai_provider_uses_explicit_api_key_and_configured_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "openai-api-key")
    monkeypatch.setenv("NINA_LLM_MODEL", "gpt-5.4-mini")
    monkeypatch.setattr(provider_module, "OpenAI", FakeOpenAI)

    provider = OpenAIProvider()
    response = await provider.complete(LLMRequest(purpose="chat", prompt="Hello"))

    assert provider.api_key == "openai-api-key"
    assert provider.client.kwargs["api_key"] == "openai-api-key"
    assert provider.model == "gpt-5.4-mini"
    assert provider.client.captured["chat_model"] == "gpt-5.4-mini"
    assert provider.client.captured["chat_messages"] == [{"role": "user", "content": "Hello"}]
    assert response.model == "gpt-5.4-mini"
    assert response.provider == "openai"
    assert response.response == "ok"


@pytest.mark.asyncio
async def test_openai_provider_passes_tools_and_parses_tool_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "openai-api-key")
    monkeypatch.setattr(provider_module, "OpenAI", FakeOpenAI)

    provider = OpenAIProvider()
    request = LLMRequest(
        purpose="chat",
        messages=[{"role": "user", "content": "Find auth docs"}],
        tools=[
            provider_module.ToolDefinition(
                name="obsidian_search",
                description="Search the vault",
                parameters={
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
            )
        ],
        tool_choice="auto",
    )
    provider.client.captured["chat_tool_calls"] = [
        type(
            "Call",
            (),
            {
                "id": "call-1",
                "function": type(
                    "Fn",
                    (),
                    {"name": "obsidian_search", "arguments": '{"query": "codex"}'},
                )(),
            },
        )()
    ]
    response = await provider.complete(request)

    kwargs = provider.client.captured["chat_kwargs"]
    assert kwargs["tool_choice"] == "auto"
    assert kwargs["tools"][0]["function"]["name"] == "obsidian_search"
    assert provider.client.captured["chat_messages"] == [
        {"role": "user", "content": "Find auth docs"}
    ]
    assert response.tool_calls[0].name == "obsidian_search"
    assert response.tool_calls[0].arguments == {"query": "codex"}


@pytest.mark.asyncio
async def test_codex_provider_passes_tools_and_translates_messages(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    auth_path = tmp_path / "auth.json"
    auth_path.write_text(
        json.dumps(
            {
                "auth_mode": "chatgptAuthTokens",
                "tokens": {
                    "access_token": _jwt({"chatgpt_account_id": "acc-123"}),
                    "refresh_token": "refresh-old",
                    "expires_at": 9999999999999,
                },
            }
        )
    )
    monkeypatch.setenv("CODEX_AUTH_FILE", str(auth_path))
    monkeypatch.setattr(provider_module, "OpenAI", FakeOpenAI)

    request = LLMRequest(
        purpose="chat",
        prompt="",
        messages=[
            {"role": "system", "content": "be terse"},
            {"role": "user", "content": "hi"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call-1",
                        "function": {
                            "name": "obsidian_search",
                            "arguments": '{"query": "x"}',
                        },
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "call-1", "content": '{"results":[]}'},
        ],
        tools=[
            provider_module.ToolDefinition(
                name="obsidian_search",
                description="Search",
                parameters={"type": "object", "properties": {"query": {"type": "string"}}},
            )
        ],
    )

    provider = CodexAuthProvider()
    await provider.complete(request)

    stream_kwargs = provider.client.captured["responses_stream"]
    assert stream_kwargs["tools"][0]["name"] == "obsidian_search"
    assert stream_kwargs["tool_choice"] == "auto"
    items = stream_kwargs["input"]
    # system is dropped; user message present; function_call and function_call_output present
    assert any(item.get("type") == "message" and item.get("role") == "user" for item in items)
    assert any(item.get("type") == "function_call" for item in items)
    assert any(item.get("type") == "function_call_output" for item in items)


@pytest.mark.asyncio
async def test_fake_provider_returns_queued_tool_calls() -> None:
    provider = provider_module.FakeProvider()
    call = provider_module.ToolCall(id="c1", name="echo", arguments={"value": "hi"})
    provider.queue_tool_calls([call], "done")
    provider.queue_text("plain")
    response1 = await provider.complete(LLMRequest(purpose="chat", prompt="x"))
    response2 = await provider.complete(LLMRequest(purpose="chat", prompt="x"))
    assert response1.tool_calls[0].name == "echo"
    assert response1.finish_reason == "tool_calls"
    assert response2.tool_calls == []
    assert response2.finish_reason == "stop"


def test_openai_provider_requires_api_key_even_with_codex_auth(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    auth_path = tmp_path / "auth.json"
    auth_path.write_text(
        json.dumps(
            {
                "auth_mode": "chatgptAuthTokens",
                "tokens": {"access_token": "codex-oauth-token"},
            }
        )
    )
    monkeypatch.setenv("CODEX_AUTH_FILE", str(auth_path))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY is required"):
        OpenAIProvider()


@pytest.mark.asyncio
async def test_codex_auth_provider_uses_codex_auth_file_and_chatgpt_backend(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    auth_path = tmp_path / "auth.json"
    auth_path.write_text(
        json.dumps(
            {
                "auth_mode": "chatgptAuthTokens",
                "tokens": {
                    "access_token": _jwt({"chatgpt_account_id": "acc-123"}),
                    "refresh_token": "refresh-old",
                    "expires_at": 9999999999999,
                },
            }
        )
    )
    monkeypatch.setenv("CODEX_AUTH_FILE", str(auth_path))
    monkeypatch.setenv("NINA_LLM_MODEL", "gpt-5.4-mini")
    monkeypatch.setattr(provider_module, "OpenAI", FakeOpenAI)

    provider = CodexAuthProvider()
    response = await provider.complete(LLMRequest(purpose="chat", prompt="Explain codex auth"))

    assert provider.auth.access_token == _jwt({"chatgpt_account_id": "acc-123"})
    assert provider.client.kwargs["api_key"] == _jwt({"chatgpt_account_id": "acc-123"})
    assert provider.client.kwargs["base_url"] == provider_module.CODEX_BASE_URL
    assert provider.client.kwargs["default_headers"]["originator"] == "nina"
    assert provider.client.kwargs["default_headers"]["ChatGPT-Account-Id"] == "acc-123"
    assert provider.client.captured["responses_stream"]["model"] == "gpt-5.4-mini"
    assert provider.client.captured["responses_stream"]["store"] is False
    assert provider.client.captured["responses_stream"]["instructions"].startswith("You are Nina")
    assert provider.client.captured["responses_stream"]["input"] == [
        {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": "Explain codex auth"}],
        }
    ]
    assert response.provider == "codex"
    assert response.response == "codex ok"


@pytest.mark.asyncio
async def test_codex_auth_provider_refreshes_expired_tokens(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    auth_path = tmp_path / "auth.json"
    auth_path.write_text(
        json.dumps(
            {
                "auth_mode": "chatgptAuthTokens",
                "tokens": {
                    "access_token": "expired-access",
                    "refresh_token": "refresh-old",
                    "expires_at": 1,
                },
            }
        )
    )
    monkeypatch.setenv("CODEX_AUTH_FILE", str(auth_path))
    monkeypatch.setattr(provider_module, "OpenAI", FakeOpenAI)
    monkeypatch.setattr(
        provider_module,
        "_refresh_codex_auth",
        lambda refresh_token: {
            "access_token": "fresh-access",
            "refresh_token": f"next-{refresh_token}",
            "expires_at": 9999999999999,
            "account_id": "acc-999",
        },
    )

    provider = CodexAuthProvider()

    assert provider.auth.access_token == "fresh-access"
    assert provider.client.kwargs["api_key"] == "fresh-access"
    stored = json.loads(auth_path.read_text())
    assert stored["tokens"]["access_token"] == "fresh-access"
    assert stored["tokens"]["refresh_token"] == "next-refresh-old"
    assert stored["tokens"]["account_id"] == "acc-999"


def test_llm_service_defaults_to_codex_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("NINA_LLM_PROVIDER", raising=False)
    monkeypatch.setenv(
        "CODEX_AUTH_FILE",
        str(tmp_path / "auth.json"),
    )
    (tmp_path / "auth.json").write_text(
        json.dumps(
            {
                "auth_mode": "chatgptAuthTokens",
                "tokens": {
                    "access_token": _jwt({"chatgpt_account_id": "acc-123"}),
                    "refresh_token": "refresh-old",
                    "expires_at": 9999999999999,
                },
            }
        )
    )
    monkeypatch.setattr(provider_module, "OpenAI", FakeOpenAI)

    service = LLMService(str(tmp_path / "nina.db"))

    assert isinstance(service.provider, CodexAuthProvider)


def _jwt(claims: dict[str, object]) -> str:
    header = (
        base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode())
        .decode()
        .rstrip("=")
    )
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    return f"{header}.{payload}.signature"


# --- Local / openai_compatible providers ------------------------------------


class _FakeChat:
    def __init__(self, captured: dict[str, object]) -> None:
        self.captured = captured
        self.completions = _FakeCompletions(captured)


class _FakeCompletions:
    def __init__(self, captured: dict[str, object]) -> None:
        self.captured = captured

    def create(self, model: str, messages: list[dict[str, str]], **kwargs: object):
        self.captured["model"] = model
        self.captured["messages"] = messages
        self.captured["kwargs"] = kwargs

        class _Choice:
            class message:  # noqa: N801 - mirroring SDK shape
                content = "ok"
                tool_calls = None

        class _Resp:
            choices = [_Choice()]

        return _Resp()


def test_ollama_provider_defaults_to_localhost() -> None:
    from nina_core.llm.provider import OllamaProvider

    provider = OllamaProvider()
    assert provider.base_url == "http://localhost:11434/v1"
    assert provider.model == "gemma3:4b"


def test_ollama_provider_passes_request_model_through() -> None:
    from nina_core.llm.provider import OllamaProvider

    captured: dict[str, object] = {}
    provider = OllamaProvider()
    provider.client = type(  # type: ignore[assignment]
        "C",
        (),
        {"chat": _FakeChat(captured)},
    )()
    import asyncio

    resp = asyncio.run(
        provider.complete(LLMRequest(purpose="test", prompt="hi", model="custom-7b"))
    )
    assert resp.response == "ok"
    assert resp.provider == "ollama"
    assert captured["model"] == "custom-7b"


def test_openai_compatible_provider_requires_base_url() -> None:
    from nina_core.llm.provider import OpenAICompatibleProvider

    with pytest.raises(RuntimeError, match="base_url is required"):
        OpenAICompatibleProvider()


def test_llm_service_routes_ollama_to_ollama_provider() -> None:
    from nina_core.llm.provider import OllamaProvider

    config = __import__("nina_core.config.settings", fromlist=["LLMConfig"]).LLMConfig(
        provider="ollama", model="gemma3:4b", base_url="http://localhost:9999/v1"
    )
    service = LLMService(":memory:", config=config)
    assert isinstance(service.provider, OllamaProvider)
    assert service.provider.base_url == "http://localhost:9999/v1"


def test_llm_service_routes_openai_compatible_to_generic_provider() -> None:
    from nina_core.llm.provider import OpenAICompatibleProvider

    config = __import__("nina_core.config.settings", fromlist=["LLMConfig"]).LLMConfig(
        provider="openai_compatible",
        model="local",
        base_url="http://localhost:8080/v1",
    )
    service = LLMService(":memory:", config=config)
    assert isinstance(service.provider, OpenAICompatibleProvider)


def test_check_provider_status_reports_ollama_reachable_via_http(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from nina_core.llm.provider import check_provider_status

    def fake_get(url: str, timeout: float = 0.0) -> object:
        class _Resp:
            status_code = 200

            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict[str, object]:
                return {"models": [{"name": "gemma3:4b"}, {"name": "llama3.2:3b"}]}

        return _Resp()

    monkeypatch.setattr(provider_module.httpx, "get", fake_get)
    status = check_provider_status(
        __import__("nina_core.config.settings", fromlist=["LLMConfig"]).LLMConfig(
            provider="ollama", model="gemma3:4b"
        ),
        timeout=1.0,
    )
    assert status.reachable is True
    assert status.model_present is True
    assert "gemma3:4b" in (status.available_models or [])


def test_check_provider_status_reports_missing_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from nina_core.llm.provider import check_provider_status

    def fake_get(url: str, timeout: float = 0.0) -> object:
        class _Resp:
            status_code = 200

            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict[str, object]:
                return {"models": [{"name": "some-other-model:7b"}]}

        return _Resp()

    monkeypatch.setattr(provider_module.httpx, "get", fake_get)
    status = check_provider_status(
        __import__("nina_core.config.settings", fromlist=["LLMConfig"]).LLMConfig(
            provider="ollama", model="gemma3:4b"
        ),
        timeout=1.0,
    )
    assert status.reachable is True
    assert status.model_present is False
    assert "ollama pull" in (status.detail or "")


def test_check_provider_status_reports_unreachable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from nina_core.llm.provider import check_provider_status

    def fake_get(url: str, timeout: float = 0.0) -> object:
        raise ConnectionError("refused")

    monkeypatch.setattr(provider_module.httpx, "get", fake_get)
    status = check_provider_status(
        __import__("nina_core.config.settings", fromlist=["LLMConfig"]).LLMConfig(
            provider="ollama", model="gemma3:4b"
        ),
        timeout=1.0,
    )
    assert status.reachable is False
    assert status.model_present is False


def test_check_transcription_status_reports_no_faster_whisper() -> None:
    """If faster-whisper isn't installed, status should say so and point at
    the install command.
    """
    from nina_core.llm.transcription import (
        FasterWhisperProvider,
        check_transcription_status,
    )

    # faster-whisper is not installed in this env, so this should report
    # unavailable with a useful hint.
    status = check_transcription_status(
        __import__(
            "nina_core.config.settings", fromlist=["TranscriptionConfig"]
        ).TranscriptionConfig()
    )
    if not status.available:
        assert "faster-whisper" in (status.detail or "")
    else:  # pragma: no cover - environment-specific
        assert status.provider_class == FasterWhisperProvider.__name__


def test_check_transcription_status_fake_is_available() -> None:
    from nina_core.llm.transcription import check_transcription_status

    status = check_transcription_status(
        __import__(
            "nina_core.config.settings", fromlist=["TranscriptionConfig"]
        ).TranscriptionConfig(backend="null")
    )
    assert status.available is True
