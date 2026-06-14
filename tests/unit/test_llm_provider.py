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

    def create(self, model: str, messages: list[dict[str, str]]):
        self.captured["chat_model"] = model
        self.captured["chat_messages"] = messages

        class Response:
            choices = [type("Choice", (), {"message": type("Message", (), {"content": "ok"})()})()]

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
async def test_openai_provider_uses_explicit_api_key_and_configured_model(monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_llm_service_defaults_to_codex_provider(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NINA_LLM_PROVIDER", raising=False)
    monkeypatch.setenv(
        "CODEX_AUTH_FILE",
        str(
            tmp_path / "auth.json"
        ),
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
    header = base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode()).decode().rstrip("=")
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    return f"{header}.{payload}.signature"
