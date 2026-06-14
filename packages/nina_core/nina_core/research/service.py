from __future__ import annotations

import os
from typing import Any

from openai import OpenAI
from pydantic import BaseModel

from nina_core.obsidian.service import ObsidianService
from nina_core.search.indexer import index_notes


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


class OpenAIWebResearchProvider(ResearchProvider):
    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is required for web research")
        self.client = OpenAI(api_key=self.api_key)
        self.model = model or os.environ.get("NINA_RESEARCH_MODEL", "gpt-5")

    def research(self, topic: str) -> ResearchReport:
        response = self.client.responses.create(
            model=self.model,
            input="\n\n".join(
                [
                    "Research the topic below and write a concise, useful summary in markdown.",
                    "Focus on current facts, tradeoffs, and caveats. Do not invent sources.",
                    "The application will capture web citations separately.",
                    f"Topic: {topic}",
                ]
            ),
            tools=[{"type": "web_search", "search_context_size": "high"}],
            tool_choice="auto",
            include=["web_search_call.action.sources"],
            max_output_tokens=900,
        )
        sources: list[ResearchSource] = []
        seen: set[str] = set()
        for item in getattr(response, "output", []):
            item_type = getattr(item, "type", None)
            if item_type == "message":
                for content in getattr(item, "content", []):
                    if getattr(content, "type", None) != "output_text":
                        continue
                    for annotation in getattr(content, "annotations", []):
                        if getattr(annotation, "type", None) != "url_citation":
                            continue
                        url = getattr(annotation, "url", None)
                        title = getattr(annotation, "title", None) or url
                        if not url or url in seen:
                            continue
                        seen.add(url)
                        sources.append(ResearchSource(title=title, url=url))
            elif item_type == "web_search_call":
                action = getattr(item, "action", None)
                for source in getattr(action, "sources", []) or []:
                    url = getattr(source, "url", None)
                    if not url or url in seen:
                        continue
                    seen.add(url)
                    sources.append(ResearchSource(title=url, url=url))
        if not sources:
            sources.append(ResearchSource(title=topic, url="https://openai.com"))
        return ResearchReport(topic=topic, summary=(response.output_text or "").strip(), sources=sources)


class ResearchService:
    def __init__(
        self,
        db_path: str,
        vault_path: str,
        provider: ResearchProvider | None = None,
        obsidian: ObsidianService | None = None,
    ) -> None:
        self.db_path = db_path
        self.vault_path = vault_path
        self.provider = provider or self._build_provider()
        self.obsidian = obsidian or ObsidianService(vault_path)

    def _build_provider(self) -> ResearchProvider:
        provider = os.environ.get("NINA_RESEARCH_PROVIDER", "openai_web").lower()
        if provider == "fake":
            return FakeResearchProvider()
        if provider in {"openai", "openai_web", "web"}:
            return OpenAIWebResearchProvider()
        raise RuntimeError(f"Unsupported research provider: {provider}")

    def run(self, topic: str, workflow_run_id: str | None = None, created_at: str | None = None) -> dict[str, Any]:
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


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
