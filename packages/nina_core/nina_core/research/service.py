from __future__ import annotations

import asyncio
import json
import re
import tempfile
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlparse

from pydantic import BaseModel

from nina_core.codex.client import CodexClient
from nina_core.config.settings import ResearchConfig  # type: ignore[reportMissingTypeStubs]
from nina_core.notes.service import NoteService  # type: ignore[reportMissingTypeStubs]
from nina_core.obsidian.service import ObsidianService  # type: ignore[reportMissingTypeStubs]


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
    provider: str | None = None
    model: str | None = None
    search_mode: str | None = None


class ResearchProvider:
    def research(
        self,
        topic: str,
        *,
        search_mode: str | None = None,
        context: str | None = None,
    ) -> ResearchReport:  # pragma: no cover - interface
        raise NotImplementedError


class FakeResearchProvider(ResearchProvider):
    def research(
        self,
        topic: str,
        *,
        search_mode: str | None = None,
        context: str | None = None,
    ) -> ResearchReport:
        del context
        slug = topic.lower().replace(" ", "-")
        return ResearchReport(
            topic=topic,
            summary=f"Fake research summary for {topic}.",
            sources=[ResearchSource(title=f"{topic} reference", url=f"https://example.com/{slug}")],
            provider="fake",
            model="fake",
            search_mode=search_mode,
        )


class CodexCliResearchProvider(ResearchProvider):
    def __init__(
        self,
        model: str | None = None,
        timeout: float = 240.0,
        binary_path: str | None = None,
        search_mode: str = "live",
    ) -> None:
        self.model = model or "codex-cli"
        self.timeout = timeout
        self.search_mode = search_mode
        self.client = CodexClient(
            "127.0.0.1",
            0,
            "",
            "",
            timeout=timeout,
            binary_path=binary_path,
        )

    def research(
        self,
        topic: str,
        *,
        search_mode: str | None = None,
        context: str | None = None,
    ) -> ResearchReport:
        mode = search_mode or self.search_mode
        prompt_parts = [
            "You are Nina Research running through the local Codex CLI.",
            "Research the topic with Codex web search and produce a concise markdown summary.",
            "Favor current, authoritative primary sources where possible.",
            "Return only the structured JSON object required by the output schema.",
            "If you cannot verify external sources, return an empty sources list and say what is uncertain in the summary.",
            f"Topic: {topic}",
        ]
        if context:
            prompt_parts.extend(["Additional user context:", context])
        prompt = "\n".join(prompt_parts)
        schema_path = _write_research_schema()
        try:
            result = _run_codex_sync(
                self.client.exec(
                    prompt,
                    timeout=self.timeout,
                    output_last_message=True,
                    model=None if self.model == "codex-cli" else self.model,
                    web_search=mode,
                    output_schema=schema_path,
                )
            )
        finally:
            schema_path.unlink(missing_ok=True)
        text = (result.last_message or result.stdout or "").strip()
        payload = _extract_json_object(text) or {}
        summary = payload.get("summary")
        raw_sources = payload.get("sources")
        return ResearchReport(
            topic=topic,
            summary=str(summary or text),
            sources=_normalize_sources(raw_sources),
            provider="codex",
            model=self.model,
            search_mode=mode,
        )


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
                timeout=self.config.timeout_seconds,
                binary_path=self.codex_binary_path,
                search_mode=self.config.search_mode,
            )
        raise RuntimeError(f"Unsupported research provider: {provider}")

    def run(
        self,
        topic: str,
        workflow_run_id: str | None = None,
        created_at: str | None = None,
        search_mode: str | None = None,
        context: str | None = None,
    ) -> dict[str, Any]:
        resolved_search_mode = _normalize_search_mode(search_mode or self.config.search_mode)
        report = self.provider.research(topic, search_mode=resolved_search_mode, context=context)
        created_at = created_at or report.created_at or _now()
        report.provider = report.provider or self.config.provider
        report.model = report.model or self.config.model
        report.search_mode = report.search_mode or resolved_search_mode
        note_path = self.obsidian.create_research_note(
            topic=topic,
            summary=report.summary,
            sources=[source.model_dump() for source in report.sources],
            workflow_run_id=workflow_run_id,
            created_at=created_at,
            provider=report.provider,
            model=report.model,
            search_mode=report.search_mode,
        )
        NoteService(self.db_path, self.vault_path).index_existing_note(
            note_path,
            nina_type="research_report",
        )
        report.note_path = note_path
        report.workflow_run_id = workflow_run_id
        report.created_at = created_at
        return report.model_dump()


def _normalize_search_mode(value: str) -> str:
    mode = (value or "live").strip().lower()
    if mode not in {"live", "cached", "disabled"}:
        raise ValueError("research search_mode must be one of: live, cached, disabled")
    return mode


def _write_research_schema() -> Path:
    schema = {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "sources": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "url": {"type": "string"},
                    },
                    "required": ["title", "url"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["summary", "sources"],
        "additionalProperties": False,
    }
    with tempfile.NamedTemporaryFile(
        "w",
        prefix="nina-research-schema-",
        suffix=".json",
        delete=False,
        encoding="utf-8",
    ) as handle:
        json.dump(schema, handle)
        return Path(handle.name)


def _normalize_sources(raw_sources: Any) -> list[ResearchSource]:
    sources: list[ResearchSource] = []
    seen: set[str] = set()
    if not isinstance(raw_sources, list):
        return sources
    for raw in cast(list[Any], raw_sources):
        if not isinstance(raw, dict):
            continue
        item = cast(dict[str, Any], raw)
        title = item.get("title")
        url = item.get("url")
        if not isinstance(url, str):
            continue
        cleaned_url = url.strip()
        parsed = urlparse(cleaned_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            continue
        if cleaned_url in seen:
            continue
        seen.add(cleaned_url)
        cleaned_title = title.strip() if isinstance(title, str) else ""
        sources.append(ResearchSource(title=cleaned_title or cleaned_url, url=cleaned_url))
    return sources


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
            return cast(dict[str, Any], payload)
    return None


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
