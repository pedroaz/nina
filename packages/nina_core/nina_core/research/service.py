from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from pydantic import BaseModel

from nina_core.codex.client import CodexClient
from nina_core.config.settings import ResearchConfig  # type: ignore[reportMissingTypeStubs]
from nina_core.obsidian.service import ObsidianService  # type: ignore[reportMissingTypeStubs]
from nina_core.search.indexer import index_notes  # type: ignore[reportMissingTypeStubs]


class ResearchSource(BaseModel):
    title: str
    url: str


class ResearchReport(BaseModel):
    topic: str
    summary: str
    sources: list[ResearchSource]
    note_path: str | None = None
    workflow_run_id: str | None = None
    created_at: str | None = None


class ResearchProvider:
    def research(self, topic: str) -> ResearchReport:  # pragma: no cover - interface
        raise NotImplementedError


class FakeResearchProvider(ResearchProvider):
    def research(self, topic: str) -> ResearchReport:
        slug = topic.lower().replace(" ", "-")
        return ResearchReport(
            topic=topic,
            summary=f"Fake research summary for {topic}.",
            sources=[ResearchSource(title=f"{topic} reference", url=f"https://example.com/{slug}")],
        )


class CodexCliResearchProvider(ResearchProvider):
    def __init__(
        self,
        model: str | None = None,
        timeout: float = 240.0,
        binary_path: str | None = None,
    ) -> None:
        self.model = model or "codex-cli"
        self.timeout = timeout
        self.client = CodexClient(
            "127.0.0.1",
            0,
            "",
            "",
            timeout=timeout,
            binary_path=binary_path,
        )

    def research(self, topic: str) -> ResearchReport:
        prompt = "\n".join(
            [
                "You are Nina Research running through the local Codex CLI.",
                "Research the topic from your available context and produce a concise markdown summary.",
                "Return exactly one JSON object with this schema and no markdown fences:",
                '{"summary":"markdown summary","sources":[{"title":"source title","url":"https://example.com"}]}',
                "If you cannot verify external sources, return an empty sources list and say what is uncertain in the summary.",
                f"Topic: {topic}",
            ]
        )
        result = _run_codex_sync(self.client.exec(prompt, timeout=self.timeout, output_last_message=True))
        text = (result.last_message or result.stdout or "").strip()
        payload = _extract_json_object(text) or {}
        summary = payload.get("summary") if isinstance(payload, dict) else None
        raw_sources = payload.get("sources") if isinstance(payload, dict) else None
        sources: list[ResearchSource] = []
        if isinstance(raw_sources, list):
            for raw in raw_sources:
                if not isinstance(raw, dict):
                    continue
                title = raw.get("title")
                url = raw.get("url")
                if isinstance(title, str) and isinstance(url, str) and url:
                    sources.append(ResearchSource(title=title or url, url=url))
        return ResearchReport(topic=topic, summary=str(summary or text), sources=sources)


class ResearchService:
    def __init__(
        self,
        db_path: str,
        vault_path: str,
        provider: ResearchProvider | None = None,
        obsidian: ObsidianService | None = None,
        config: ResearchConfig | None = None,
        codex_binary_path: str | None = None,
    ) -> None:
        self.db_path = db_path
        self.vault_path = vault_path
        self.config = config or ResearchConfig()
        self.codex_binary_path = codex_binary_path
        self.provider = provider or self._build_provider()
        self.obsidian = obsidian or ObsidianService(vault_path)

    def _build_provider(self) -> ResearchProvider:
        provider = self.config.provider.lower()
        if provider == "fake":
            return FakeResearchProvider()
        if provider in {"codex", "openai", "openai_web", "web"}:
            return CodexCliResearchProvider(
                model=self.config.model,
                binary_path=self.codex_binary_path,
            )
        raise RuntimeError(f"Unsupported research provider: {provider}")

    def run(
        self, topic: str, workflow_run_id: str | None = None, created_at: str | None = None
    ) -> dict[str, Any]:
        report = self.provider.research(topic)
        created_at = created_at or report.created_at or _now()
        note_path = self.obsidian.create_research_note(
            topic=topic,
            summary=report.summary,
            sources=[source.model_dump() for source in report.sources],
            workflow_run_id=workflow_run_id,
            created_at=created_at,
        )
        index_notes(self.db_path, self.vault_path)
        report.note_path = note_path
        report.workflow_run_id = workflow_run_id
        report.created_at = created_at
        return report.model_dump()


def _run_codex_sync(awaitable: Any) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(awaitable)
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(asyncio.run, awaitable).result()


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


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
