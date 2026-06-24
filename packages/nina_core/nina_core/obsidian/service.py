import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import frontmatter

from nina_core.models.models import Task


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "note"


TASK_DESCRIPTION_HEADING = "## Description"
TASK_PROMPT_HEADING = "## Prompt"
TASK_STATUS_HEADING = "## Status"
TASK_SUMMARY_HEADING = "## Summary"
TASK_NOTES_HEADING = "## Notes"
TASK_ACTIVITY_HEADING = "## Nina Activity"


def _format_status_line(label: str, value: str | None) -> str:
    return f"- {label}: {value}" if value is not None and value != "" else f"- {label}: none"


class ObsidianService:
    def __init__(self, vault_path: Path | str) -> None:
        self.vault_path = Path(vault_path)

    def write_note(self, relative_path: str | Path, body: str, metadata: Mapping[str, Any]) -> Path:
        path = self.vault_path / Path(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        post = frontmatter.Post(body, **dict(metadata))
        path.write_text(frontmatter.dumps(post))
        return path

    def _default_task_path(self, task: Task) -> Path:
        return self.vault_path / "Tasks" / f"{task.id}.md"

    def _task_path(self, task: Task) -> Path:
        return self._default_task_path(task)

    def _task_metadata(self, task: Task) -> dict[str, Any]:
        return {
            "nina_type": "task",
            "nina_id": task.id,
            "task_type": task.task_type,
            "status": task.status,
            "pipeline_stage": task.pipeline_stage,
            "pipeline_error": task.pipeline_error,
            "pipeline_rework_count": task.pipeline_rework_count,
            "repository_id": task.repository_id,
            "classified_at": task.classified_at,
            "classification_reason": task.classification_reason,
            "classification_model": task.classification_model,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
        }

    def _task_status_block(self, task: Task) -> str:
        return "\n".join(
            [
                _format_status_line("task_type", task.task_type),
                _format_status_line("status", task.status),
                _format_status_line("pipeline_stage", task.pipeline_stage),
                f"- pipeline_rework_count: {task.pipeline_rework_count}",
                f"- pipeline_error: {task.pipeline_error if task.pipeline_error is not None else 'none'}",
                _format_status_line("last_updated", task.updated_at),
            ]
        )

    def _task_note_sections(self, task: Task, existing_content: str) -> dict[str, str]:
        prompt = _extract_section(existing_content, TASK_PROMPT_HEADING)
        summary = _extract_section(existing_content, TASK_SUMMARY_HEADING)
        notes = _extract_section(existing_content, TASK_NOTES_HEADING)
        activity = _extract_section(existing_content, TASK_ACTIVITY_HEADING)

        return {
            TASK_DESCRIPTION_HEADING: task.description or "",
            TASK_PROMPT_HEADING: prompt,
            TASK_STATUS_HEADING: self._task_status_block(task),
            TASK_SUMMARY_HEADING: summary,
            TASK_NOTES_HEADING: notes,
            TASK_ACTIVITY_HEADING: activity,
        }

    def _task_body(
        self,
        task: Task,
        existing_content: str | None = None,
        *,
        prompt: str | None = None,
        summary: str | None = None,
        notes: str | None = None,
        activity_message: str | None = None,
    ) -> str:
        existing = existing_content or ""
        sections = self._task_note_sections(task, existing)

        if prompt is not None:
            sections[TASK_PROMPT_HEADING] = prompt
        if summary is not None:
            sections[TASK_SUMMARY_HEADING] = summary
        if notes is not None:
            sections[TASK_NOTES_HEADING] = notes

        if not sections[TASK_NOTES_HEADING]:
            sections[TASK_NOTES_HEADING] = "- No notes yet."

        if activity_message is not None:
            existing_activity = sections[TASK_ACTIVITY_HEADING] or ""
            timestamp = datetime.now(timezone.utc).isoformat()
            line = f"- {timestamp}: {activity_message.strip()}"
            if existing_activity.strip():
                sections[TASK_ACTIVITY_HEADING] = f"{existing_activity.rstrip()}\n{line}"
            else:
                sections[TASK_ACTIVITY_HEADING] = line
        elif not sections[TASK_ACTIVITY_HEADING].strip():
            sections[TASK_ACTIVITY_HEADING] = "- No activity yet."

        parts = [
            f"# {task.title}",
            "",
            TASK_DESCRIPTION_HEADING,
            "",
            sections[TASK_DESCRIPTION_HEADING] or "",
            "",
            TASK_PROMPT_HEADING,
            "",
            sections[TASK_PROMPT_HEADING] or "No prompt captured yet.",
            "",
            TASK_STATUS_HEADING,
            "",
            sections[TASK_STATUS_HEADING],
            "",
            TASK_SUMMARY_HEADING,
            "",
            sections[TASK_SUMMARY_HEADING] or "No summary yet.",
            "",
            TASK_NOTES_HEADING,
            "",
            sections[TASK_NOTES_HEADING],
            "",
            TASK_ACTIVITY_HEADING,
            "",
            sections[TASK_ACTIVITY_HEADING],
            "",
        ]
        return "\n".join(parts)

    def create_task_note(self, task: Task) -> None:
        path = self._task_path(task)
        post = frontmatter.Post(self._task_body(task), **self._task_metadata(task))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(frontmatter.dumps(post))

    def update_task_note(self, task: Task) -> None:
        path = self._task_path(task)
        if path.exists():
            post = frontmatter.loads(path.read_text())
            post.content = self._task_body(task, post.content)
            post.metadata.update(self._task_metadata(task))
            path.write_text(frontmatter.dumps(post))

    def set_task_prompt(self, task: Task, prompt: str) -> None:
        path = self._task_path(task)
        if not path.exists():
            self.create_task_note(task)
        post = frontmatter.loads(path.read_text())
        post.content = self._task_body(task, post.content, prompt=prompt or "")
        post.metadata.update(self._task_metadata(task))
        path.write_text(frontmatter.dumps(post))

    def set_task_summary(self, task: Task, summary: str) -> None:
        path = self._task_path(task)
        if not path.exists():
            self.create_task_note(task)
        post = frontmatter.loads(path.read_text())
        post.content = self._task_body(task, post.content, summary=summary or "")
        post.metadata.update(self._task_metadata(task))
        path.write_text(frontmatter.dumps(post))

    def append_task_activity(self, task: Task, message: str) -> None:
        path = self._task_path(task)
        if not path.exists():
            self.create_task_note(task)
        post = frontmatter.loads(path.read_text())
        post.metadata.update(self._task_metadata(task))
        post.content = self._task_body(task, post.content, activity_message=message)
        path.write_text(frontmatter.dumps(post))

    def delete_task_note(self, task: Task) -> None:
        path = self._task_path(task)
        if path.exists():
            deleted_dir = self.vault_path / "System" / "Deleted"
            deleted_dir.mkdir(parents=True, exist_ok=True)
            os.rename(path, deleted_dir / path.name)

    def archive_task_note(self, task: Task) -> None:
        path = self._task_path(task)
        if path.exists():
            archived_dir = self.vault_path / "System" / "Archived"
            archived_dir.mkdir(parents=True, exist_ok=True)
            os.rename(path, archived_dir / path.name)

    def unarchive_task_note(self, task: Task) -> None:
        archived_path = self.vault_path / "System" / "Archived" / f"{task.id}.md"
        if archived_path.exists():
            task_path = self._default_task_path(task)
            task_path.parent.mkdir(parents=True, exist_ok=True)
            os.rename(archived_path, task_path)

    def create_research_note(
        self,
        topic: str,
        summary: str,
        sources: Iterable[Mapping[str, str]],
        workflow_run_id: str | None,
        created_at: str,
        provider: str | None = None,
        model: str | None = None,
        search_mode: str | None = None,
    ) -> str:
        created_date = created_at[:10]
        relative_path = Path("Research") / f"{created_date} - {_slugify(topic)}.md"
        source_list = list(sources)
        source_lines = (
            "\n".join(
                f"- [{source.get('title') or source['url']}]({source['url']})"
                for source in source_list
            )
            or "- No external sources were captured."
        )
        body = "\n".join(
            [
                f"# Research - {topic}",
                "",
                "## Summary",
                "",
                summary.strip() or "No summary available.",
                "",
                "## Sources",
                "",
                source_lines,
                "",
            ]
        )
        metadata = {
            "nina_type": "research_report",
            "topic": topic,
            "workflow_run_id": workflow_run_id,
            "created_at": created_at,
            "sources": source_list,
        }
        if provider:
            metadata["provider"] = provider
        if model:
            metadata["model"] = model
        if search_mode:
            metadata["search_mode"] = search_mode
        self.write_note(relative_path, body, metadata)
        return str(relative_path)

    def _meeting_path(self, title: str, started_at: str) -> Path:
        date = started_at[:10]
        return Path("Meetings") / f"{date} - {_slugify(title)}.md"

    def _voice_path(self, title: str, started_at: str) -> Path:
        date = started_at[:10]
        return Path("Voice") / f"{date} - {_slugify(title)}.md"

    def write_voice_capture_note(
        self,
        capture_id: str,
        title: str,
        started_at: str,
        source: str,
        audio_path: str,
        transcript: str,
        *,
        language: str | None = None,
        model: str | None = None,
    ) -> str:
        relative_path = self._voice_path(title, started_at)
        body = "\n".join(
            [
                f"# {title}",
                "",
                "## Transcript",
                "",
                transcript.rstrip() or "_No transcript text returned._",
                "",
            ]
        )
        metadata = {
            "nina_type": "voice_capture",
            "nina_id": capture_id,
            "title": title,
            "started_at": started_at,
            "source": source,
            "audio_path": audio_path,
            "language": language,
            "model": model,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self.write_note(relative_path, body, metadata)
        return str(relative_path)

    def _transcript_path(self, title: str, started_at: str) -> Path:
        date = started_at[:10]
        return Path("Meetings") / f"{date} - {_slugify(title)} - Transcript.md"

    def _summary_path(self, title: str, started_at: str) -> Path:
        date = started_at[:10]
        return Path("Meetings") / f"{date} - {_slugify(title)} - Summary.md"

    def _hub_body(
        self,
        title: str,
        started_at: str,
        ended_at: str | None,
        duration_seconds: int | None,
        source: str,
        transcript_note_path: str | None = None,
        summary_note_path: str | None = None,
    ) -> str:
        duration_part = ""
        if duration_seconds is not None:
            duration_part = f" ({int(duration_seconds) // 60}m {int(duration_seconds) % 60:02d}s)"
        date_part = started_at[:10]
        transcript_link = (
            f"[[{Path(transcript_note_path).stem}]]"
            if transcript_note_path
            else "_Transcription pending._"
        )
        summary_link = (
            f"[[{Path(summary_note_path).stem}]]" if summary_note_path else "_Summary pending._"
        )
        return "\n".join(
            [
                f"# {title}",
                "",
                "## Notes",
                "",
                f"Recording captured on {date_part} from `{source}` input{duration_part}.",
                "",
                "## Linked artifacts",
                "",
                f"- Transcript: {transcript_link}",
                f"- Summary: {summary_link}",
                "",
            ]
        )

    def create_meeting_note(
        self,
        meeting_id: str,
        title: str,
        started_at: str,
        ended_at: str | None,
        duration_seconds: int | None,
        source: str,
        audio_path: str,
        transcript_status: str = "pending",
        summary_status: str = "pending",
        workflow_run_id: str | None = None,
    ) -> str:
        relative_path = self._meeting_path(title, started_at)
        body = self._hub_body(
            title=title,
            started_at=started_at,
            ended_at=ended_at,
            duration_seconds=duration_seconds,
            source=source,
        )
        metadata = {
            "nina_type": "meeting",
            "nina_id": meeting_id,
            "title": title,
            "started_at": started_at,
            "ended_at": ended_at,
            "duration_seconds": duration_seconds,
            "source": source,
            "audio_path": audio_path,
            "transcript_status": transcript_status,
            "summary_status": summary_status,
            "workflow_run_id": workflow_run_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self.write_note(relative_path, body, metadata)
        return str(relative_path)

    def write_transcript_note(
        self,
        meeting_id: str,
        title: str,
        started_at: str,
        transcript: str,
        *,
        language: str | None = None,
        model: str | None = None,
        workflow_run_id: str | None = None,
    ) -> str:
        """Write the dedicated transcript note. Body is the full transcript
        text plus a wikilink back to the hub. Returns the vault-relative path.
        """
        relative_path = self._transcript_path(title, started_at)
        hub_stem = self._meeting_path(title, started_at).stem
        body = "\n".join(
            [
                transcript.rstrip(),
                "",
                "## Linked artifacts",
                "",
                f"- Hub: [[{hub_stem}]]",
                "",
            ]
        )
        metadata = {
            "nina_type": "meeting_transcript",
            "nina_id": meeting_id,
            "title": f"{title} - Transcript",
            "meeting_title": title,
            "started_at": started_at,
            "language": language,
            "model": model,
            "workflow_run_id": workflow_run_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self.write_note(relative_path, body, metadata)
        return str(relative_path)

    def write_summary_note(
        self,
        meeting_id: str,
        title: str,
        started_at: str,
        *,
        summary: str,
        action_items: str,
        decisions: str,
        model: str | None = None,
        provider: str | None = None,
        workflow_run_id: str | None = None,
    ) -> str:
        """Write the dedicated summary note. Body has the three sections plus
        a wikilink back to the hub. Returns the vault-relative path.
        """
        relative_path = self._summary_path(title, started_at)
        hub_stem = self._meeting_path(title, started_at).stem
        transcript_stem = self._transcript_path(title, started_at).stem
        body = "\n".join(
            [
                "## Summary",
                "",
                summary.strip() or "_No summary available._",
                "",
                "## Action items",
                "",
                action_items.strip() or "- _none yet_",
                "",
                "## Decisions",
                "",
                decisions.strip() or "- _none yet_",
                "",
                "## Linked artifacts",
                "",
                f"- Hub: [[{hub_stem}]]",
                f"- Transcript: [[{transcript_stem}]]",
                "",
            ]
        )
        metadata = {
            "nina_type": "meeting_summary",
            "nina_id": meeting_id,
            "title": f"{title} - Summary",
            "meeting_title": title,
            "started_at": started_at,
            "model": model,
            "provider": provider,
            "workflow_run_id": workflow_run_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self.write_note(relative_path, body, metadata)
        return str(relative_path)

    def update_meeting_note_sections(
        self,
        meeting_id: str,
        title: str,
        started_at: str,
        ended_at: str | None,
        duration_seconds: int | None,
        source: str,
        audio_path: str,
        *,
        transcript: str | None = None,
        transcript_status: str | None = None,
        summary: str | None = None,
        action_items: str | None = None,
        decisions: str | None = None,
        summary_status: str | None = None,
        workflow_run_id: str | None = None,
        transcript_note_path: str | None = None,
        summary_note_path: str | None = None,
    ) -> str | None:
        """Patch the meeting hub. Transcript and summary bodies now live in
        their own files; this method only updates the hub's metadata and
        `## Linked artifacts` wikilink block. Legacy call sites that still pass
        `transcript=...` / `summary=...` are still accepted but ignored for
        content (the wikilink is the source of truth).
        """
        relative_path = self._meeting_path(title, started_at)
        full_path = self.vault_path / relative_path
        if not full_path.is_file():
            return None
        post = frontmatter.loads(full_path.read_text())
        body = self._hub_body(
            title=title,
            started_at=started_at,
            ended_at=ended_at,
            duration_seconds=duration_seconds,
            source=source,
            transcript_note_path=transcript_note_path or post.metadata.get("transcript_note_path"),
            summary_note_path=summary_note_path or post.metadata.get("summary_note_path"),
        )
        post.content = body
        if transcript_status is not None:
            post.metadata["transcript_status"] = transcript_status
        if summary_status is not None:
            post.metadata["summary_status"] = summary_status
        if workflow_run_id is not None:
            post.metadata["workflow_run_id"] = workflow_run_id
        if ended_at is not None:
            post.metadata["ended_at"] = ended_at
        if duration_seconds is not None:
            post.metadata["duration_seconds"] = duration_seconds
        if audio_path:
            post.metadata["audio_path"] = audio_path
        if transcript_note_path is not None:
            post.metadata["transcript_note_path"] = transcript_note_path
        if summary_note_path is not None:
            post.metadata["summary_note_path"] = summary_note_path
        post.metadata["updated_at"] = datetime.now(timezone.utc).isoformat()
        full_path.write_text(frontmatter.dumps(post))
        return str(relative_path)

    def soft_delete_meeting_note(
        self,
        meeting_id: str,  # noqa: ARG002 - kept for API compatibility
        title: str,
        started_at: str,
    ) -> str | None:
        relative_path = self._meeting_path(title, started_at)
        full_path = self.vault_path / relative_path
        if not full_path.is_file():
            return None
        deleted_dir = self.vault_path / "System" / "Deleted"
        deleted_dir.mkdir(parents=True, exist_ok=True)
        os.rename(full_path, deleted_dir / full_path.name)
        # Best-effort: also move the transcript and summary siblings so the
        # vault stays consistent.
        for sibling in (
            self._transcript_path(title, started_at),
            self._summary_path(title, started_at),
        ):
            sibling_full = self.vault_path / sibling
            if sibling_full.is_file():
                os.rename(sibling_full, deleted_dir / sibling_full.name)
        return str((deleted_dir / full_path.name).relative_to(self.vault_path))


def _extract_section(body: str, heading: str) -> str:
    target = heading.strip()
    prefix = "## " if not target.startswith("##") else ""
    pattern = re.compile(
        rf"^{re.escape(prefix + target)}\s*$\n(?P<content>.*?)(?=^##\s+|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(body)
    if match is None:
        return ""
    return match.group("content").strip()
