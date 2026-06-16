from __future__ import annotations

import asyncio
import concurrent.futures
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from nina_core.config import NinaConfig, load_effective_config
from nina_core.models.models import WorkflowRun, WorkflowStep
from nina_core.research.service import ResearchService


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_config_dir() -> Path:
    """Bootstrap-only: the daemon subprocess needs to know which config dir
    to load. Everything else comes from the loaded `NinaConfig`."""
    env_dir = os.environ.get("NINA_CONFIG_DIR")
    if env_dir:
        return Path(env_dir)
    return Path.home() / ".nina" / "default"


class WorkflowRunner:
    def __init__(
        self,
        db_path: str,
        config: NinaConfig | None = None,
    ) -> None:
        self.db_path = db_path
        # Load the active Nina config eagerly. Workflow settings come from
        # the typed `NinaConfig`, not from a hidden env channel.
        if config is None:
            config = load_effective_config(_resolve_config_dir())
        self.config = config

    @property
    def vault_path(self) -> Path:
        return Path(self.config.vault_path)

    @property
    def config_dir(self) -> Path:
        return _resolve_config_dir()

    def _session(self) -> Session:
        engine = create_engine(f"sqlite:///{self.db_path}", echo=False)
        SessionLocal = sessionmaker(bind=engine)
        return SessionLocal()

    def run(self, workflow_name: str, input_data: dict[str, Any]) -> dict[str, Any]:
        db = self._session()
        run = WorkflowRun(
            id=str(uuid.uuid4()),
            workflow_name=workflow_name,
            status="running",
            input_json=json.dumps(input_data),
            created_at=_now(),
            updated_at=_now(),
        )
        db.add(run)
        db.commit()
        output: dict[str, Any] = {}
        try:
            if workflow_name == "summarize-last-day":
                output = self._run_summarize(db, run)
            elif workflow_name == "research-topic":
                output = self._run_research(db, run, input_data)
            elif workflow_name == "reindex-vault":
                output = self._run_reindex(db, run)
            elif workflow_name == "transcribe-meeting":
                output = self._run_transcribe_meeting(db, run, input_data)
            elif workflow_name == "summarize-meeting":
                output = self._run_summarize_meeting(db, run, input_data)
            else:
                raise ValueError(f"Unknown workflow '{workflow_name}'")
            run.output_json = json.dumps(output)
            run.status = "completed"
            run.completed_at = _now()
        except Exception as exc:
            run.status = "failed"
            run.error = str(exc)
            output = {"error": str(exc)}
        run.updated_at = _now()
        db.commit()
        result = {
            "id": run.id,
            "workflow_name": run.workflow_name,
            "status": run.status,
            "created_at": run.created_at,
            "output": output,
        }
        db.close()
        return result

    def _create_step(self, db: Session, run: WorkflowRun, step_name: str) -> WorkflowStep:
        step = WorkflowStep(
            id=str(uuid.uuid4()),
            workflow_run_id=run.id,
            step_name=step_name,
            status="running",
            attempt_count=1,
            created_at=_now(),
            updated_at=_now(),
        )
        db.add(step)
        db.commit()
        return step

    def _complete_step(
        self, db: Session, step: WorkflowStep, output: dict[str, Any] | None = None
    ) -> None:
        step.status = "completed"
        step.output_json = json.dumps(output or {})
        step.completed_at = _now()
        step.updated_at = _now()
        db.commit()

    def _fail_step(self, db: Session, step: WorkflowStep, error: str) -> None:
        step.status = "failed"
        step.error = error
        step.updated_at = _now()
        db.commit()

    def _run_summarize(self, db: Session, run: WorkflowRun) -> dict[str, Any]:
        step = self._create_step(db, run, "build_context")
        self._complete_step(db, step, {"message": "Daily summary workflow is scaffolded."})
        run.status = "completed"
        run.completed_at = _now()
        run.updated_at = _now()
        db.commit()
        return {"message": "Daily summary workflow is scaffolded."}

    def _run_research(
        self, db: Session, run: WorkflowRun, input_data: dict[str, Any]
    ) -> dict[str, Any]:
        topic = str(input_data.get("topic", "")).strip()
        if not topic:
            raise ValueError("Workflow 'research-topic' requires a 'topic' field")

        plan_step = self._create_step(db, run, "plan")
        self._complete_step(db, plan_step, {"topic": topic})

        research_step = self._create_step(db, run, "research")
        service = ResearchService(
            self.db_path,
            str(self.vault_path),
            config=self.config.research,
        )
        report = service.run(topic, workflow_run_id=run.id, created_at=run.created_at)
        self._complete_step(db, research_step, report)

        finish_step = self._create_step(db, run, "finalize")
        finish_payload = {
            "note_path": report.get("note_path"),
            "source_count": len(report.get("sources", [])),
        }
        self._complete_step(db, finish_step, finish_payload)
        run.output_json = json.dumps(report)
        run.status = "completed"
        run.completed_at = _now()
        run.updated_at = _now()
        db.commit()
        return report

    def _run_reindex(self, db: Session, run: WorkflowRun) -> dict[str, Any]:
        from nina_core.search.embeddings import reindex_embeddings
        from nina_core.search.indexer import index_notes

        vault_path = str(self.vault_path)
        step = self._create_step(db, run, "reindex_fts")
        index_notes(self.db_path, vault_path)
        self._complete_step(db, step, {"vault": vault_path})

        step = self._create_step(db, run, "reindex_embeddings")
        embedded = reindex_embeddings(self.db_path, vault_path, config=self.config.search)
        self._complete_step(db, step, {"embedded": embedded})

        return {"vault": vault_path, "embedded": embedded}

    def _run_transcribe_meeting(
        self, db: Session, run: WorkflowRun, input_data: dict[str, Any]
    ) -> dict[str, Any]:
        from nina_core.llm.transcription import (
            build_transcription_provider,
            log_transcription_interaction,
            write_transcript_files,
        )
        from nina_core.meetings.service import MeetingService
        from nina_core.obsidian.service import ObsidianService

        meeting_id = self._extract_meeting_id(input_data)
        vault_path = str(self.vault_path)
        config_dir = self.config_dir

        service = MeetingService(self.db_path, config_dir / "recordings", vault_path)
        meeting = service.get(meeting_id)
        if meeting is None:
            raise RuntimeError(f"Meeting not found: {meeting_id}")

        service.update_status(meeting_id, status="transcribing", workflow_run_id=run.id)

        step = self._create_step(db, run, "load_meeting")
        audio_path = Path(meeting["audio_path"])
        if not audio_path.is_file():
            service.update_status(meeting_id, status="failed", error=f"Missing audio: {audio_path}")
            raise RuntimeError(f"Audio file missing: {audio_path}")
        self._complete_step(db, step, {"audio_path": str(audio_path)})

        step = self._create_step(db, run, "transcribe")
        provider = build_transcription_provider(config=self.config.transcription)
        try:
            result = provider.transcribe(audio_path)
        except Exception as exc:
            log_transcription_interaction(
                self.db_path,
                provider_name=type(provider).__name__,
                model=getattr(provider, "model", "unknown"),
                audio_path=str(audio_path),
                result=type("R", (), {"text": "", "language": None, "duration_seconds": None})(),
                workflow_run_id=run.id,
                status="failed",
                error=str(exc),
            )
            service.update_status(meeting_id, status="failed", error=str(exc))
            raise

        transcript_path = audio_path.with_suffix(".txt")
        segments_path = audio_path.with_suffix(".segments.json")
        write_transcript_files(result, transcript_path, segments_path)
        self._complete_step(
            db,
            step,
            {
                "transcript_path": str(transcript_path),
                "segments_path": str(segments_path),
                "language": result.language,
                "model": result.model,
                "char_count": len(result.text),
            },
        )

        log_transcription_interaction(
            self.db_path,
            provider_name=type(provider).__name__,
            model=result.model,
            audio_path=str(audio_path),
            result=result,
            workflow_run_id=run.id,
            status="completed",
        )

        step = self._create_step(db, run, "update_note")
        obsidian = ObsidianService(vault_path)
        vault_rel = obsidian.update_meeting_note_sections(
            meeting_id=meeting_id,
            title=meeting["title"],
            started_at=meeting["started_at"],
            ended_at=meeting.get("ended_at"),
            duration_seconds=meeting.get("duration_seconds"),
            source=meeting.get("source") or "mic",
            audio_path=meeting.get("audio_path") or "",
            transcript=result.text,
            transcript_status="done",
            workflow_run_id=run.id,
        )
        self._complete_step(db, step, {"note_path": vault_rel})

        service.update_status(
            meeting_id,
            status="transcribed",
            transcript_path=str(transcript_path),
            workflow_run_id=run.id,
        )

        return {
            "meeting_id": meeting_id,
            "transcript_path": str(transcript_path),
            "note_path": vault_rel,
            "language": result.language,
            "model": result.model,
            "char_count": len(result.text),
        }

    def _run_summarize_meeting(
        self, db: Session, run: WorkflowRun, input_data: dict[str, Any]
    ) -> dict[str, Any]:
        from nina_core.llm.provider import LLMRequest, LLMService
        from nina_core.meetings.service import MeetingService
        from nina_core.obsidian.service import ObsidianService

        meeting_id = self._extract_meeting_id(input_data)
        vault_path = str(self.vault_path)
        config_dir = self.config_dir

        service = MeetingService(self.db_path, config_dir / "recordings", vault_path)
        meeting = service.get(meeting_id)
        if meeting is None:
            raise RuntimeError(f"Meeting not found: {meeting_id}")

        service.update_status(meeting_id, status="summarizing", workflow_run_id=run.id)

        step = self._create_step(db, run, "load_meeting")
        self._complete_step(db, step, {"title": meeting.get("title")})

        step = self._create_step(db, run, "build_context")
        transcript_text = self._read_transcript(meeting)
        context_lines = [
            f"Title: {meeting.get('title', '')}",
            f"Started at: {meeting.get('started_at', '')}",
            f"Duration: {meeting.get('duration_seconds') or 'unknown'} seconds",
            f"Source: {meeting.get('source') or 'mic'}",
            "",
            "Transcript:",
            transcript_text or "(no transcript available)",
        ]
        context = "\n".join(context_lines)
        self._complete_step(db, step, {"context_chars": len(context)})

        step = self._create_step(db, run, "summarize")
        prompt = (
            "You are summarizing a meeting transcript. Produce exactly three sections:\n\n"
            "## Summary\n"
            "3-6 short bullet points covering the main discussion.\n\n"
            "## Action items\n"
            "Bullet list of concrete next steps, with owners if mentioned.\n\n"
            "## Decisions\n"
            "Bullet list of decisions that were made during the meeting.\n\n"
            "Be concise. Use the transcript verbatim where useful.\n\n"
            f"Meeting context:\n{context}"
        )
        llm = LLMService(self.db_path, config=self.config.llm)
        request = LLMRequest(
            purpose="meeting_summary",
            prompt=prompt,
            workflow_run_id=run.id,
        )
        response = self._run_async(llm.complete(request))
        summary_text, action_items, decisions = _split_summary_sections(response.response)
        self._complete_step(
            db,
            step,
            {
                "model": response.model,
                "provider": response.provider,
                "summary_chars": len(summary_text),
            },
        )

        step = self._create_step(db, run, "update_note")
        obsidian = ObsidianService(vault_path)
        vault_rel = obsidian.update_meeting_note_sections(
            meeting_id=meeting_id,
            title=meeting["title"],
            started_at=meeting["started_at"],
            ended_at=meeting.get("ended_at"),
            duration_seconds=meeting.get("duration_seconds"),
            source=meeting.get("source") or "mic",
            audio_path=meeting.get("audio_path") or "",
            summary=summary_text,
            action_items=action_items,
            decisions=decisions,
            summary_status="done",
            workflow_run_id=run.id,
        )
        self._complete_step(db, step, {"note_path": vault_rel})

        service.update_status(
            meeting_id,
            status="summarized",
            summary_path=vault_rel,
            workflow_run_id=run.id,
        )

        return {
            "meeting_id": meeting_id,
            "note_path": vault_rel,
            "model": response.model,
            "provider": response.provider,
        }

    def _run_async(self, coro: Any) -> Any:
        """Run an async coroutine to completion even if a loop is already running.

        The workflow runs in a daemon thread, where `asyncio.run` is safe.
        """
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(asyncio.run, coro)
            return future.result()

    def _extract_meeting_id(self, input_data: dict[str, Any]) -> str:
        meeting_id = input_data.get("meeting_id") if isinstance(input_data, dict) else None
        if not meeting_id:
            inner = input_data.get("input") if isinstance(input_data, dict) else None
            if isinstance(inner, dict):
                meeting_id = inner.get("meeting_id")
        if not meeting_id:
            raise ValueError("Workflow requires a 'meeting_id' field")
        return str(meeting_id)

    def _read_transcript(self, meeting: dict[str, Any]) -> str:
        path_str = meeting.get("transcript_path")
        if not path_str:
            return ""
        path = Path(path_str)
        if not path.is_file():
            return ""
        return path.read_text()


def _split_summary_sections(text: str) -> tuple[str, str, str]:
    """Split a free-form summary response into Summary / Action items / Decisions."""

    import re

    summary_match = re.search(r"##\s*Summary\s*\n(?P<body>.*?)(?=^##\s+|\Z)", text, re.S | re.M)
    actions_match = re.search(
        r"##\s*Action items\s*\n(?P<body>.*?)(?=^##\s+|\Z)", text, re.S | re.M
    )
    decisions_match = re.search(r"##\s*Decisions\s*\n(?P<body>.*?)(?=^##\s+|\Z)", text, re.S | re.M)
    summary = summary_match.group("body").strip() if summary_match else text.strip()
    action_items = actions_match.group("body").strip() if actions_match else ""
    decisions = decisions_match.group("body").strip() if decisions_match else ""
    if not actions_match and not decisions_match:
        summary = text.strip()
    return summary, action_items, decisions
