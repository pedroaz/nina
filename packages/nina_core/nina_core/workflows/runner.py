from __future__ import annotations

import asyncio
import concurrent.futures
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from nina_core.config import NinaConfig, get_codex_task_logs_dir, load_effective_config
from nina_core.models.models import TASK_PIPELINE_STAGES, WorkflowRun, WorkflowStep
from nina_core.research.service import ResearchService


logger = logging.getLogger(__name__)


WORKFLOW_DESCRIPTIONS: dict[str, str] = {
    "summarize-last-day": (
        "Builds a daily summary note for the configured target date: collects "
        "tasks touched and completed on that day, workflow and job events, and "
        "Markdown notes created or updated, then calls the LLM to write "
        "`Daily/YYYY-MM-DD.md` with a summary, completed items, open loops, and "
        "suggested next actions. (Currently scaffolded — the LLM call is a "
        "no-op stub.)"
    ),
    "research-topic": (
        "Plans a research brief on the given topic, runs web research via the "
        "configured provider, and writes a structured `Research/<topic>.md` "
        "note into Obsidian with cited sources and a written answer."
    ),
    "reindex-vault": (
        "Rebuilds both the FTS5 full-text search index and the embedding index "
        "for every Markdown note in the vault, so search and semantic recall "
        "reflect the current on-disk state."
    ),
    "transcribe-meeting": (
        "Loads the meeting's audio file, transcribes it through the configured "
        "transcription backend (default: local faster-whisper, 16 kHz mono, VAD "
        "on), writes `<recording>.txt` and `<recording>.segments.json` next to "
        "the audio, updates the meeting note's `## Transcript` section, and "
        "logs the interaction to the LLM log."
    ),
    "summarize-meeting": (
        "Loads the meeting's transcript, asks the configured LLM to produce a "
        "3–6 bullet summary plus `## Action items` and `## Decisions` blocks, "
        "and writes a sibling summary note linked from the meeting hub note."
    ),
    "meeting-pipeline": (
        "Runs `transcribe-meeting` and `summarize-meeting` back-to-back on a "
        "single meeting inside one workflow run, streaming progress events to "
        "daemon clients."
    ),
    "classify-task": (
        "Reads a freshly-created task (title + description), calls the LLM "
        "to pick one of `reminder | research | coding | reviewing | blocked | done`, "
        "and patches the task's `task_type`, `classified_at`, "
        "`classification_reason`, and `classification_model`. Repository-backed "
        "coding/reviewing tasks are left idle for explicit execution. Falls "
        "back to `reminder` when the model output is unparseable."
    ),
    "run-task": (
        "Routes a task to its handler. Unclassified tasks are classified first; "
        "coding and reviewing tasks run one Codex session. Refuses `reminder` "
        "and `blocked`; research tasks run the research workflow and write an "
        "Obsidian report note."
    ),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_log_value(value: Any, limit: int = 500) -> str:
    text = str(value or "").replace("\n", " ").replace("\r", " ").strip()
    return text[:limit]


def _log_task_event(
    *,
    task_id: str,
    workflow_id: str,
    event: str,
    codex_run_id: str | None = None,
    status: str | None = None,
    worktree: str | None = None,
    message: str | None = None,
) -> None:
    parts = [
        "nina.task",
        f"task={_safe_log_value(task_id)}",
        f"workflow={_safe_log_value(workflow_id)}",
        f"event={_safe_log_value(event)}",
    ]
    if codex_run_id:
        parts.append(f"run={_safe_log_value(codex_run_id)}")
    if status:
        parts.append(f"status={_safe_log_value(status)}")
    if worktree:
        parts.append(f"worktree={_safe_log_value(worktree)}")
    if message:
        parts.append(f"message={_safe_log_value(message)}")
    logger.info(" ".join(parts))


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
            elif workflow_name == "meeting-pipeline":
                output = self._run_meeting_pipeline(db, run, input_data)
            elif workflow_name == "classify-task":
                output = self._run_classify_task(db, run, input_data)
            elif workflow_name == "run-task":
                output = self._run_run_task(db, run, input_data)
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
        search_mode = input_data.get("search_mode")
        if search_mode is not None:
            search_mode = str(search_mode)
        context = str(input_data.get("context") or "").strip() or None

        plan_step = self._create_step(db, run, "plan")
        self._complete_step(db, plan_step, {"topic": topic})

        research_step = self._create_step(db, run, "research")
        service = ResearchService(
            self.db_path,
            str(self.vault_path),
            config=self.config.research,
            codex_binary_path=self.config.codex.binary_path,
        )
        report = service.run(
            topic,
            workflow_run_id=run.id,
            created_at=run.created_at,
            search_mode=search_mode,
            context=context,
        )
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
        transcript_note_rel = obsidian.write_transcript_note(
            meeting_id=meeting_id,
            title=meeting["title"],
            started_at=meeting["started_at"],
            transcript=result.text,
            language=result.language,
            model=result.model,
            workflow_run_id=run.id,
        )
        hub_rel = obsidian.update_meeting_note_sections(
            meeting_id=meeting_id,
            title=meeting["title"],
            started_at=meeting["started_at"],
            ended_at=meeting.get("ended_at"),
            duration_seconds=meeting.get("duration_seconds"),
            source=meeting.get("source") or "mic",
            audio_path=meeting.get("audio_path") or "",
            transcript_status="done",
            workflow_run_id=run.id,
            transcript_note_path=transcript_note_rel,
            summary_note_path=meeting.get("summary_note_path"),
        )
        self._complete_step(
            db,
            step,
            {"note_path": hub_rel, "transcript_note_path": transcript_note_rel},
        )

        service.update_status(
            meeting_id,
            status="transcribed",
            transcript_path=str(transcript_path),
            transcript_note_path=transcript_note_rel,
            workflow_run_id=run.id,
        )

        return {
            "meeting_id": meeting_id,
            "transcript_path": str(transcript_path),
            "transcript_note_path": transcript_note_rel,
            "note_path": hub_rel,
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
        llm = LLMService(self.db_path, config=self.config.llm, codex_binary_path=self.config.codex.binary_path)
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
        summary_note_rel = obsidian.write_summary_note(
            meeting_id=meeting_id,
            title=meeting["title"],
            started_at=meeting["started_at"],
            summary=summary_text,
            action_items=action_items,
            decisions=decisions,
            model=response.model,
            provider=response.provider,
            workflow_run_id=run.id,
        )
        hub_rel = obsidian.update_meeting_note_sections(
            meeting_id=meeting_id,
            title=meeting["title"],
            started_at=meeting["started_at"],
            ended_at=meeting.get("ended_at"),
            duration_seconds=meeting.get("duration_seconds"),
            source=meeting.get("source") or "mic",
            audio_path=meeting.get("audio_path") or "",
            summary_status="done",
            workflow_run_id=run.id,
            transcript_note_path=meeting.get("transcript_note_path"),
            summary_note_path=summary_note_rel,
        )
        self._complete_step(
            db,
            step,
            {"note_path": hub_rel, "summary_note_path": summary_note_rel},
        )

        service.update_status(
            meeting_id,
            status="summarized",
            summary_path=summary_note_rel,
            summary_note_path=summary_note_rel,
            workflow_run_id=run.id,
        )

        return {
            "meeting_id": meeting_id,
            "note_path": hub_rel,
            "summary_note_path": summary_note_rel,
            "model": response.model,
            "provider": response.provider,
        }

    def _run_meeting_pipeline(
        self, db: Session, run: WorkflowRun, input_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Run transcribe and summarize back-to-back in a single workflow run.

        Each stage writes its own step on the same WorkflowRun, so clients can
        see the progress via `/events/stream` and a single status surface can
        cover both operations.
        """
        # Reuse the existing per-meeting workflows but as steps on the same
        # run. We delegate by calling the runners directly; they manage their
        # own DB session and status updates.
        from nina_core.meetings.service import MeetingService

        meeting_id = self._extract_meeting_id(input_data)
        service = MeetingService(self.db_path, self.config_dir / "recordings", self.vault_path)
        meeting = service.get(meeting_id)
        if meeting is None:
            raise RuntimeError(f"Meeting not found: {meeting_id}")
        if not Path(meeting["audio_path"]).is_file():
            raise RuntimeError(f"Audio file missing: {meeting['audio_path']}")

        step = self._create_step(db, run, "transcribe")
        try:
            transcribe_output = self._run_transcribe_meeting(db, run, input_data)
        except Exception as exc:
            self._fail_step(db, step, str(exc))
            raise
        self._complete_step(db, step, transcribe_output)

        step = self._create_step(db, run, "summarize")
        try:
            summarize_output = self._run_summarize_meeting(db, run, input_data)
        except Exception as exc:
            self._fail_step(db, step, str(exc))
            raise
        self._complete_step(db, step, summarize_output)

        return {
            "meeting_id": meeting_id,
            "transcribe": transcribe_output,
            "summarize": summarize_output,
            "transcript_note_path": transcribe_output.get("transcript_note_path"),
            "summary_note_path": summarize_output.get("summary_note_path"),
            "note_path": summarize_output.get("note_path"),
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

    def _run_classify_task(
        self, db: Session, run: WorkflowRun, input_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Run the LLM classifier on a single task and patch the row."""

        from nina_core.llm.provider import LLMRequest, LLMService
        from nina_core.obsidian.service import ObsidianService
        from nina_core.tasks.service import TaskService
        from nina_core.tasks.classifier import CLASSIFY_PROMPT, parse_classify_response

        task_id = self._extract_task_id(input_data)
        vault_path = str(self.vault_path)

        service = TaskService(db, ObsidianService(vault_path))
        task = service.get(task_id)
        if task is None:
            raise RuntimeError(f"Task not found: {task_id}")
        _log_task_event(task_id=task_id, workflow_id=run.id, event="classify_started")

        step = self._create_step(db, run, "load_task")
        title = task.title or ""
        description = task.description or ""
        self._complete_step(
            db,
            step,
            {"title_chars": len(title), "description_chars": len(description)},
        )

        step = self._create_step(db, run, "classify")
        prompt_description = description or "(none)"
        prompt = CLASSIFY_PROMPT + (
            f"\n\nTask title: {title}\nTask description: {prompt_description}"
        )
        llm = LLMService(self.db_path, config=self.config.llm, codex_binary_path=self.config.codex.binary_path)
        request = LLMRequest(
            purpose="task_classification",
            prompt=prompt,
            workflow_run_id=run.id,
        )
        response = self._run_async(llm.complete(request))
        result = parse_classify_response(response.response)
        self._complete_step(
            db,
            step,
            {
                "task_type": result.task_type,
                "reason_chars": len(result.reason),
                "model": response.model,
            },
        )

        step = self._create_step(db, run, "patch_task")
        repository_required = result.task_type not in {
            "unclassified",
            "reminder",
            "research",
            "blocked",
            "done",
        } and not task.repository_id
        if repository_required:
            service.update(task_id, status="error")
        else:
            service.update(task_id, task_type=result.task_type, status="idle")
        now = _now()
        task = service.get(task_id)
        if task is not None:
            task.classified_at = now
            task.classification_reason = result.reason or (
                f"auto-classified as {result.task_type} by {response.model}"
            )
            task.classification_model = response.model
            db.commit()
            obsidian = ObsidianService(vault_path)
            obsidian.update_task_note(task)
            if repository_required:
                service.add_activity(
                    task_id,
                    f"Classifier selected {result.task_type}, but no repository is attached. "
                    "Attach a repository or change the task type.",
                )
            else:
                service.add_activity(task_id, f"Classifier set task_type={result.task_type}.")
        refreshed = service.get(task_id)
        self._complete_step(
            db,
            step,
            {
                "task_id": task_id,
                "task_type": result.task_type,
                "applied_task_type": getattr(refreshed, "task_type", None),
                "requires_repository": repository_required,
            },
        )
        _log_task_event(
            task_id=task_id,
            workflow_id=run.id,
            event="classify_done",
            status=result.task_type,
            message=result.reason,
        )

        return {
            "task_id": task_id,
            "task_type": result.task_type,
            "applied_task_type": getattr(refreshed, "task_type", None),
            "requires_repository": repository_required,
            "reason": result.reason,
            "model": response.model,
        }

    def _run_run_task(
        self, db: Session, run: WorkflowRun, input_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Route and run a task through its task-type handler."""

        from nina_core.obsidian.service import ObsidianService
        from nina_core.tasks.service import TaskService

        task_id = self._extract_task_id(input_data)
        vault_path = str(self.vault_path)

        service = TaskService(db, ObsidianService(vault_path))
        task = service.get(task_id)
        if task is None:
            raise RuntimeError(f"Task not found: {task_id}")

        task_type = task.task_type
        if task_type == "unclassified":
            _log_task_event(task_id=task_id, workflow_id=run.id, event="classify_before_run")
            classification = self._run_classify_task(db, run, {"task_id": task_id})
            if classification.get("requires_repository"):
                selected_type = str(classification.get("task_type") or "coding")
                reason = (
                    f"Classifier selected {selected_type}, but no repository is attached. "
                    "Attach a repository or change the task type."
                )
                _log_task_event(
                    task_id=task_id,
                    workflow_id=run.id,
                    event="repository_required",
                    status="error",
                    message=reason,
                )
                return {
                    "task_id": task_id,
                    "task_type": selected_type,
                    "applied_task_type": classification.get("applied_task_type"),
                    "status": "error",
                    "reason": reason,
                    "requires_repository": True,
                    "would_route_to": None,
                }
            task = service.get(task_id)
            if task is None:
                raise RuntimeError(f"Task not found: {task_id}")
            task_type = task.task_type
            _log_task_event(
                task_id=task_id,
                workflow_id=run.id,
                event="classified_for_run",
                status=task_type,
            )

        if task_type in {"reminder", "blocked"}:
            service.update(task_id, status="idle")
            _log_task_event(task_id=task_id, workflow_id=run.id, event="skipped", status=task_type)
            return {
                "task_id": task_id,
                "task_type": task_type,
                "status": "skipped",
                "reason": f"AI does not work on {task_type} tasks",
                "would_route_to": None,
            }

        if task_type == "done":
            service.update(task_id, status="idle")
            _log_task_event(task_id=task_id, workflow_id=run.id, event="noop", status="done")
            return {
                "task_id": task_id,
                "task_type": task_type,
                "status": "noop",
                "reason": "task is already done",
                "would_route_to": None,
            }

        if task_type == "research":
            return self._run_research_task(db, run, service, task, input_data)

        if task_type not in {"coding", "reviewing"}:
            service.update(task_id, status="idle")
            _log_task_event(task_id=task_id, workflow_id=run.id, event="routed", status=task_type)
            step = self._create_step(db, run, "route_task")
            self._complete_step(
                db,
                step,
                {"would_route_to": task_type, "status": "idle"},
            )
            return {
                "task_id": task_id,
                "task_type": task_type,
                "status": "completed",
                "reason": f"{task_type} routing placeholder",
                "would_route_to": task_type,
            }

        return self._run_codex_task(db, run, service, task, input_data)

    def _run_research_task(
        self,
        db: Session,
        run: WorkflowRun,
        service: Any,
        task: Any,
        input_data: dict[str, Any],
    ) -> dict[str, Any]:
        topic = str(input_data.get("topic") or task.title or "").strip()
        if not topic:
            return {
                "task_id": task.id,
                "task_type": task.task_type,
                "status": "error",
                "reason": "research task requires a title or topic",
                "would_route_to": None,
            }
        search_mode = input_data.get("search_mode")
        if search_mode is not None:
            search_mode = str(search_mode)
        context = str(input_data.get("context") or task.description or "").strip() or None
        service.update(task.id, status="working")
        service.add_activity(task.id, f"Research started for: {topic}")
        _log_task_event(
            task_id=task.id,
            workflow_id=run.id,
            event="research_start",
            status="working",
        )
        step = self._create_step(db, run, "research_task")
        research = ResearchService(
            self.db_path,
            str(self.vault_path),
            config=self.config.research,
            codex_binary_path=self.config.codex.binary_path,
        )
        try:
            report = research.run(
                topic,
                workflow_run_id=run.id,
                created_at=run.created_at,
                search_mode=search_mode,
                context=context,
            )
        except Exception as exc:
            message = str(exc)
            self._fail_step(db, step, message)
            service.update(task.id, status="error")
            service.add_activity(task.id, f"Research failed: {message}")
            _log_task_event(
                task_id=task.id,
                workflow_id=run.id,
                event="research_error",
                status="error",
                message=message,
            )
            return {
                "task_id": task.id,
                "task_type": task.task_type,
                "status": "error",
                "reason": message,
                "would_route_to": "research",
            }
        self._complete_step(db, step, report)
        service.update(task.id, status="idle")
        service.add_activity(task.id, f"Research note written: {report.get('note_path')}")
        _log_task_event(
            task_id=task.id,
            workflow_id=run.id,
            event="research_done",
            status="idle",
            message=str(report.get("note_path") or ""),
        )
        return {
            "task_id": task.id,
            "task_type": task.task_type,
            "status": "completed",
            "reason": "research completed",
            "would_route_to": "research",
            "note_path": report.get("note_path"),
            "source_count": len(report.get("sources", [])),
            "search_mode": report.get("search_mode"),
        }

    def _run_codex_task(
        self,
        db: Session,
        run: WorkflowRun,
        service: Any,
        task: Any,
        input_data: dict[str, Any],
    ) -> dict[str, Any]:
        from nina_core.codex import CodexClient, CodexError

        try:
            worktree = self._resolve_task_worktree(db, task)
        except ValueError as exc:
            message = str(exc)
            service.update(task.id, status="error")
            service.add_activity(task.id, message)
            _log_task_event(
                task_id=task.id,
                workflow_id=run.id,
                event="repository_required",
                status="error",
                message=message,
            )
            return {
                "task_id": task.id,
                "task_type": task.task_type,
                "status": "error",
                "reason": message,
                "would_route_to": None,
            }

        client = CodexClient(
            host=self.config.codex.host,
            port=self.config.codex.port,
            username=self.config.codex.username,
            password="",
            timeout=5.0,
            binary_path=self.config.codex.binary_path,
        )
        _log_task_event(
            task_id=task.id,
            workflow_id=run.id,
            event="codex_ready",
            status=client.binary_path or "missing",
            worktree=worktree,
        )

        run_id = f"{task.id}-{task.task_type}-{uuid.uuid4().hex[:8]}"
        log_path = self._codex_task_log_path(task.id, run_id)
        normalized_stage = self._normalize_pipeline_stage(task.pipeline_stage, task.task_type)
        prompt = self._build_codex_task_prompt(task, run_id, worktree, normalized_stage)
        env = self._build_codex_task_env(input_data, task.id, run_id, task.task_type, normalized_stage)
        service.obsidian.set_task_prompt(task, prompt)

        step = self._create_step(db, run, f"codex_{task.task_type}")
        _log_task_event(
            task_id=task.id,
            workflow_id=run.id,
            event="task_started",
            codex_run_id=run_id,
            status=task.task_type,
            worktree=worktree,
        )
        service.update(task.id, status="working")
        service.add_activity(task.id, f"Codex {task.task_type} started (run {run_id}). Log: {log_path}")
        try:
            result = self._run_async(
                client.exec_task(
                    prompt,
                    cwd=worktree,
                    env=env,
                    timeout=float(input_data.get("codex_timeout_seconds") or 1800.0),
                    log_path=log_path,
                )
            )
        except CodexError as exc:
            message = str(exc)
            _log_task_event(
                task_id=task.id,
                workflow_id=run.id,
                event="error",
                codex_run_id=run_id,
                status="codex_error",
                worktree=worktree,
                message=message,
            )
            service.update(task.id, status="error")
            service.add_activity(task.id, f"Codex {task.task_type} failed (run {run_id}): {message}. Log: {log_path}")
            self._fail_step(db, step, message)
            raise

        _log_task_event(
            task_id=task.id,
            workflow_id=run.id,
            event="codex_exit",
            codex_run_id=run_id,
            status=str(result.exit_code),
            worktree=worktree,
            message=f"stdout_chars={len(result.stdout)} stderr_chars={len(result.stderr)}",
        )
        self._complete_step(
            db,
            step,
            {
                "task_type": task.task_type,
                "run_id": run_id,
                "exit_code": result.exit_code,
                "worktree": worktree,
                "log_path": str(log_path),
            },
        )
        current = service.get(task.id)
        return {
            "task_id": task.id,
            "task_type": getattr(current, "task_type", task.task_type),
            "status": "completed",
            "task_status": getattr(current, "status", None),
            "reason": "Codex run finished; task state is managed by hooks.",
            "would_route_to": f"codex:{task.task_type}",
            "run_id": run_id,
            "log_path": str(log_path),
        }

    def _resolve_task_worktree(self, db: Session, task: Any) -> str:
        from nina_core.repositories.service import RepositoryService

        if not task.repository_id:
            raise ValueError(
                f"Repository required: {task.task_type} tasks must be attached to a registered repository."
            )
        repository = RepositoryService(db).get(task.repository_id)
        if repository is None:
            raise ValueError(f"Repository not found for task: {task.repository_id}")
        path = Path(str(repository.path)).expanduser().resolve()
        if not path.is_dir():
            raise ValueError(f"Repository path does not exist: {path}")
        return str(path)

    def _codex_task_log_path(self, task_id: str, run_id: str) -> Path:
        def safe(value: str) -> str:
            return value.replace(os.sep, "_").replace("/", "_").replace(chr(92), "_")

        return get_codex_task_logs_dir(self.config_dir) / safe(task_id) / f"{safe(run_id)}.log"

    def _normalize_pipeline_stage(self, pipeline_stage: str | None, task_type: str) -> str:
        if isinstance(pipeline_stage, str):
            cleaned = pipeline_stage.strip().lower()
            if cleaned in TASK_PIPELINE_STAGES and not (task_type == "reviewing" and cleaned == "created"):
                return cleaned
        if task_type == "reviewing":
            return "reviewing"
        if task_type == "coding":
            return "coding"
        return "created"

    def _build_codex_task_env(
        self,
        input_data: dict[str, Any],
        task_id: str,
        run_id: str,
        task_type: str,
        pipeline_stage: str | None = None,
    ) -> dict[str, str]:
        token = str(input_data.get("nina_token") or os.environ.get("NINA_TOKEN") or "")
        base_url = str(
            input_data.get("nina_base_url") or os.environ.get("NINA_BASE_URL") or self._default_nina_base_url()
        )
        normalized_stage = self._normalize_pipeline_stage(pipeline_stage, task_type)
        return {
            "NINA_TASK_ID": task_id,
            "NINA_RUN_ID": run_id,
            "NINA_TASK_TYPE": task_type,
            "NINA_PIPELINE_STAGE": normalized_stage,
            "NINA_BASE_URL": base_url,
            "NINA_TOKEN": token,
            "NINA_HOOK_TIMEOUT_MS": str(input_data.get("nina_hook_timeout_ms") or "5000"),
        }

    def _default_nina_base_url(self) -> str:
        host = str(self.config.daemon_host or "127.0.0.1")
        if host in {"0.0.0.0", "::"}:
            host = "127.0.0.1"
        return f"http://{host}:{int(self.config.daemon_port)}"

    def _build_codex_task_prompt(
        self,
        task: Any,
        run_id: str,
        worktree: str,
        pipeline_stage: str | None = None,
    ) -> str:
        title = task.title or "(untitled)"
        description = task.description or "(none)"
        stage = self._normalize_pipeline_stage(pipeline_stage, task.task_type)

        stage_instructions: dict[str, str] = {
            "created": (
                "Do discovery first. Read related files, run quick checks, and define the safest implementation"
                " approach. Do not implement yet unless there is obvious context from existing code."
            ),
            "exploration": (
                "Explore the ticket end-to-end: inspect current behavior, identify affected files, and propose"
                " a coding plan with file-level changes, risk and rollback notes. If enough context is found,"
                " include concrete first implementation steps."
            ),
            "coding": (
                "Implement the requested change with minimal, focused edits. Keep changes limited to this task and"
                " preserve existing behavior outside the scope. If uncertainty remains, stop and report blockers clearly."
            ),
            "testing": (
                "Validate the change: run the most relevant checks (unit tests, lint/typing commands, and"
                " targeted build/test commands). If you cannot run checks, state exactly what is missing."
            ),
            "reviewing": (
                "Review the changes as an independent reviewer. Verify requirement coverage and edge cases."
                " Include explicit go/no-go assessment and provide a Decision line with"
                " 'approved', 'rejected', or 'blocked'."
            ),
            "done": "Finalize with a concise summary, references to evidence, and any remaining risks.",
            "blocked": "Capture clear blockers and why work is blocked. Propose a concrete next unblock step.",
        }
        final_report_lines = [
            "- Outcome: completed, partially completed, or blocked",
            "- Files: key files touched or inspected",
            "- Checks: commands run or checks not run",
            "- Blockers: any blocker, or none",
        ]

        if stage == "reviewing":
            final_report_lines.insert(1, "- Decision: approved, rejected, or blocked")
        elif stage == "exploration":
            final_report_lines.insert(1, "- Proposed next step: stage name")
        elif stage == "testing":
            final_report_lines.insert(1, "- Result: pass/fail per check")

        stage_to_next = {
            "created": "exploration",
            "exploration": "coding",
            "coding": "testing",
            "testing": "reviewing",
            "reviewing": "done",
            "done": "done",
            "blocked": "exploration",
        }
        next_stage = stage_to_next.get(stage, "created")
        self_prompt_templates: dict[str, list[str]] = {
            "created": [
                "- Goal: define scope, constraints, and acceptance criteria from the ticket.",
                "- Report these clearly in your outcome.",
                "- Include a proposed handoff prompt (concise) for the next stage.",
            ],
            "exploration": [
                "- Goal: produce a minimal, file-level implementation plan that can be executed next stage.",
                "- Include a concrete next-stage prompt for coding with changed files, risk notes, and rollback idea.",
            ],
            "coding": [
                "- Goal: ship minimal edits tied directly to the ticket objective.",
                "- Include a concrete next-stage prompt for testing with exact commands or checks to run.",
            ],
            "testing": [
                "- Goal: validate behavior and regressions; capture test commands and results.",
                "- Include any blocked checks and the reason when checks cannot run.",
                "- Include a concrete next-stage prompt for review with findings and risks.",
            ],
            "reviewing": [
                "- Goal: judge go/no-go confidence and required follow-up.",
                "- Include an explicit Decision line and a concise reviewer summary.",
                "- If not approved, include one paragraph of required fixes before re-run.",
            ],
            "done": [
                "- Goal: summarize what was achieved and what remains open.",
                "- Include references to evidence and explicit residual risks.",
            ],
            "blocked": [
                "- Goal: explain why execution is blocked and list exact unblock actions.",
                "- Include the highest-confidence next attempt once blockers are removed.",
            ],
        }
        template_lines = self_prompt_templates.get(stage, self_prompt_templates["created"])

        return "\n".join(
            [
                "Use @nina-task.",
                "",
                f"Nina task id: {task.id}",
                f"Nina run id: {run_id}",
                f"Nina task type: {task.task_type}",
                f"Nina pipeline stage: {stage}",
                f"Worktree: {worktree}",
                "",
                "Task:",
                f"Title: {title}",
                f"Description: {description}",
                "",
                "Stage guidance:",
                stage_instructions.get(stage, stage_instructions["created"]),
                "",
                "Execution order:",
                "1. Do only what this stage requires.",
                "2. Prefer minimal edits and explicit file-level justifications.",
                "3. Report a final structured update using the sections below.",
                "4. For handoff stages, also include the self-prompting lines below.",
                "",
                "Final report format:",
                *final_report_lines,
                "",
                f"Self-prompt template (next stage: {next_stage}):",
                *template_lines,
            ]
        ).strip()


    def _extract_task_id(self, input_data: dict[str, Any]) -> str:
        task_id = input_data.get("task_id") if isinstance(input_data, dict) else None
        if not task_id:
            inner = input_data.get("input") if isinstance(input_data, dict) else None
            if isinstance(inner, dict):
                task_id = inner.get("task_id")
        if not task_id:
            raise ValueError("Workflow requires a 'task_id' field")
        return str(task_id)


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
