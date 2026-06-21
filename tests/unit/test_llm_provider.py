from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from nina_core.llm import provider as provider_module
from nina_core.llm.provider import CodexCliProvider, LLMRequest, LLMService


@pytest.mark.asyncio
async def test_codex_cli_provider_returns_plain_text_when_no_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    async def fake_exec(self, prompt: str, **kwargs: object) -> object:
        captured["prompt"] = prompt
        captured["kwargs"] = kwargs
        return SimpleNamespace(stdout="", last_message="plain answer", json_payload=None)

    monkeypatch.setattr("nina_core.codex.client.CodexClient.exec", fake_exec)

    provider = CodexCliProvider(model="codex-cli")
    response = await provider.complete(LLMRequest(purpose="chat", prompt="Hello"))

    assert response.provider == "codex"
    assert response.model == "codex-cli"
    assert response.response == "plain answer"
    assert response.tool_calls == []
    assert response.finish_reason == "stop"
    assert "Messages JSON:" in str(captured["prompt"])
    assert captured["kwargs"]["output_last_message"] is True  # type: ignore[index]


@pytest.mark.asyncio
async def test_codex_cli_provider_parses_tool_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_exec(self, prompt: str, **kwargs: object) -> object:
        assert "obsidian_search" in prompt
        payload = {
            "response": "",
            "tool_calls": [
                {"id": "call-1", "name": "obsidian_search", "arguments": {"query": "codex"}}
            ],
            "finish_reason": "tool_calls",
        }
        return SimpleNamespace(stdout=json.dumps(payload), last_message=json.dumps(payload))

    monkeypatch.setattr("nina_core.codex.client.CodexClient.exec", fake_exec)

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
    response = await CodexCliProvider().complete(request)

    assert response.response == ""
    assert response.finish_reason == "tool_calls"
    assert response.tool_calls[0].name == "obsidian_search"
    assert response.tool_calls[0].arguments == {"query": "codex"}


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


def test_llm_service_defaults_to_codex_cli_provider(tmp_path: Path) -> None:
    service = LLMService(str(tmp_path / "nina.db"))

    assert isinstance(service.provider, CodexCliProvider)


def test_llm_service_passes_configured_codex_binary_path(tmp_path: Path) -> None:
    service = LLMService(str(tmp_path / "nina.db"), codex_binary_path="/opt/codex")

    assert isinstance(service.provider, CodexCliProvider)
    assert service.provider.client.binary_path == "/opt/codex"


def test_llm_service_treats_legacy_openai_provider_as_codex_cli(tmp_path: Path) -> None:
    config = __import__("nina_core.config.settings", fromlist=["LLMConfig"]).LLMConfig(
        provider="openai", model="codex-cli"
    )
    service = LLMService(str(tmp_path / "nina.db"), config=config)

    assert isinstance(service.provider, CodexCliProvider)


# --- Local / openai_compatible providers ------------------------------------


def test_ollama_provider_defaults_to_localhost() -> None:
    from nina_core.llm.provider import OllamaProvider

    provider = OllamaProvider()
    assert provider.base_url == "http://localhost:11434/v1"
    assert provider.model == "gemma3:4b"


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


def test_check_provider_status_reports_codex_binary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from nina_core.llm.provider import check_provider_status

    monkeypatch.setattr(provider_module.shutil, "which", lambda name: "/usr/bin/codex")

    def fake_run(command: list[str], **_kwargs: object) -> object:
        assert command == ["/usr/bin/codex", "--version"]
        return SimpleNamespace(returncode=0, stdout="codex-cli 1.0\n", stderr="")

    monkeypatch.setattr(provider_module.subprocess, "run", fake_run)
    status = check_provider_status(
        __import__("nina_core.config.settings", fromlist=["LLMConfig"]).LLMConfig(),
        timeout=1.0,
    )
    assert status.provider == "codex"
    assert status.reachable is True
    assert status.model_present is True
    assert status.detail == "codex-cli 1.0"


def test_check_provider_status_reports_missing_codex_binary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from nina_core.llm.provider import check_provider_status

    monkeypatch.delenv("NINA_CODEX_BINARY", raising=False)
    monkeypatch.setattr(provider_module.shutil, "which", lambda name: None)
    status = check_provider_status(
        __import__("nina_core.config.settings", fromlist=["LLMConfig"]).LLMConfig(),
        timeout=1.0,
    )
    assert status.provider == "codex"
    assert status.reachable is False
    assert "codex binary not found" in (status.detail or "")


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
    from nina_core.llm.transcription import (
        FasterWhisperProvider,
        check_transcription_status,
    )

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
