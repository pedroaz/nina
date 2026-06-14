import json
import os
import shlex
import subprocess
import uuid
from datetime import datetime, timezone
from typing import Any

from openai import OpenAI
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from nina_core.models.models import LLMInteraction


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_codex_auth() -> dict[str, Any]:
    path = os.path.expanduser(os.environ.get("CODEX_AUTH_FILE", "~/.codex/auth.json"))
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


def _get_api_key() -> str | None:
    env_key = os.environ.get("OPENAI_API_KEY", "")
    if env_key:
        return env_key
    auth = _load_codex_auth()
    auth_mode = auth.get("auth_mode", "")
    if auth_mode == "apiKey":
        return auth.get("OPENAI_API_KEY", "")
    return None


def _has_codex_oauth_session() -> bool:
    auth = _load_codex_auth()
    auth_mode = auth.get("auth_mode", "")
    if auth_mode in ("chatgpt", "chatgptAuthTokens"):
        tokens = auth.get("tokens", {})
        return bool(tokens.get("access_token"))
    return False


class LLMRequest(BaseModel):
    purpose: str
    prompt: str
    model: str = "gpt-5"
    workflow_run_id: str | None = None


class LLMResponse(BaseModel):
    response: str
    model: str
    provider: str


class LLMProvider:
    async def complete(self, request: LLMRequest) -> LLMResponse:
        raise NotImplementedError


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or _get_api_key()
        if not self.api_key:
            raise RuntimeError(
                "OpenAI API key not found. Set OPENAI_API_KEY or run codex login --api-key."
            )
        self.client = OpenAI(api_key=self.api_key)
        self.model = os.environ.get("NINA_LLM_MODEL", "gpt-5")

    async def complete(self, request: LLMRequest) -> LLMResponse:
        model = request.model or self.model
        response = self.client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": request.prompt}],
        )
        content = response.choices[0].message.content or ""
        return LLMResponse(response=content, model=model, provider="openai")


class CodexCliProvider(LLMProvider):
    def __init__(self) -> None:
        self.model = os.environ.get("NINA_LLM_MODEL", "gpt-5")
        self.command = shlex.split(
            os.environ.get("NINA_CODEX_COMMAND", "codex exec --skip-git-repo-check --sandbox read-only")
        )

    async def complete(self, request: LLMRequest) -> LLMResponse:
        timeout = int(os.environ.get("NINA_CODEX_TIMEOUT_SECONDS", "120"))
        completed = subprocess.run(
            [*self.command, request.prompt],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if completed.returncode != 0:
            error = completed.stderr.strip() or completed.stdout.strip()
            raise RuntimeError(f"Codex CLI failed: {error}")
        return LLMResponse(
            response=completed.stdout.strip(),
            model=request.model or self.model,
            provider="codex",
        )


class FakeProvider(LLMProvider):
    model = "fake"

    async def complete(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(
            response=f"Fake response for: {request.prompt[:50]}...",
            model="fake",
            provider="fake",
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
            return CodexCliProvider()
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
        model = getattr(self.provider, "model", request.model)
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
