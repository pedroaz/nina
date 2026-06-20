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
        "the TUI's meeting page (the `Ctrl+E` hotkey in the TUI hits this)."
    ),
    "classify-task": (
        "Reads a freshly-created task (title + description), calls the LLM "
        "to pick one of `reminder | research | coding | blocked | human | done`, "
        "and patches the task's `task_type`, `classified_at`, "
        "`classification_reason`, and `classification_model`. Falls back to "
        "`human` when the model output is unparseable."
    ),
    "run-task": (
        "Routing stub for the 'AI decides if it will work on it' flow. Refuses "
        "to do anything for `human`/`reminder`/`blocked` tasks. For "
        "`coding` and `research` tasks it flips the task's `status` to "
        "`working`, records a routing decision, and flips it back to `idle`."
    ),
}


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

        Each stage writes its own step on the same WorkflowRun, so the TUI can
        see the progress via `/events/stream` and a single banner covers both
        operations. The TUI's `Ctrl+E` hotkey hits this entry point.
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
        """Run the LLM classifier on a single task and patch the row.

        Inputs: `{"task_id": "<id>"}`. The task must already exist. On
        success the task's `task_type`, `classified_at`, `classification_reason`,
        and `classification_model` fields are written and the Obsidian note
        frontmatter is updated.
        """

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

        step = self._create_step(db, run, "load_task")
        title = task.title or ""
        description = task.description or ""
        self._complete_step(
            db,
            step,
            {"title_chars": len(title), "description_chars": len(description)},
        )

        step = self._create_step(db, run, "classify")
        prompt = (
            CLASSIFY_PROMPT
            + f"\n\nTask title: {title}\nTask description: {description or '(none)'}"
        )
        llm = LLMService(self.db_path, config=self.config.llm)
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
        service.update(task_id, task_type=result.task_type)
        now = _now()
        task = service.get(task_id)
        if task is not None:
            task.classified_at = now
            task.classification_reason = result.reason or (
                f"auto-classified as {result.task_type} by {response.model}"
            )
            task.classification_model = response.model
            db.commit()
            ObsidianService(vault_path).update_task_note(task)
        self._complete_step(
            db,
            step,
            {"task_id": task_id, "task_type": result.task_type},
        )

        return {
            "task_id": task_id,
            "task_type": result.task_type,
            "reason": result.reason,
            "model": response.model,
        }

    def _run_run_task(
        self, db: Session, run: WorkflowRun, input_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Routing stub: decide which workflow should handle this task and
        flip the agent status accordingly. No real agent work happens here.

        Inputs: `{"task_id": "<id>"}`. Refuses for `human`, `reminder`, and
        `blocked` tasks. For `coding` and `research` it briefly flips the
        task's `status` to `working` and back to `idle`. For `done` it's a
        no-op success.
        """

        from nina_core.obsidian.service import ObsidianService
        from nina_core.tasks.service import TaskService

        task_id = self._extract_task_id(input_data)
        vault_path = str(self.vault_path)

        service = TaskService(db, ObsidianService(vault_path))
        task = service.get(task_id)
        if task is None:
            raise RuntimeError(f"Task not found: {task_id}")

        task_type = task.task_type

        if task_type in ("human", "reminder", "blocked"):
            return {
                "task_id": task_id,
                "task_type": task_type,
                "status": "skipped",
                "reason": f"AI does not work on {task_type} tasks",
                "would_route_to": None,
            }

        if task_type == "done":
            return {
                "task_id": task_id,
                "task_type": task_type,
                "status": "noop",
                "reason": "task is already done",
                "would_route_to": None,
            }

        would_route_to = "agent" if task_type == "coding" else "research-topic"

        step = self._create_step(db, run, "flip_to_working")
        service.set_agent_status(task_id, "working")
        self._complete_step(db, step, {"status": "working"})

        step = self._create_step(db, run, "flip_to_idle")
        service.set_agent_status(task_id, "idle")
        self._complete_step(
            db,
            step,
            {"would_route_to": would_route_to, "status": "idle"},
        )

        return {
            "task_id": task_id,
            "task_type": task_type,
            "status": "completed",
            "reason": "routing stub; no real agent action",
            "would_route_to": would_route_to,
        }

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
