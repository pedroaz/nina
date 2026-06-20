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


class ObsidianService:
    def __init__(self, vault_path: Path | str) -> None:
        self.vault_path = Path(vault_path)

    def write_note(self, relative_path: str | Path, body: str, metadata: Mapping[str, Any]) -> Path:
        path = self.vault_path / Path(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        post = frontmatter.Post(body, **dict(metadata))
        path.write_text(frontmatter.dumps(post))
        return path

    def _task_path(self, task: Task) -> Path:
        return self.vault_path / "Tasks" / f"{task.title.replace(' ', '-').lower()}.md"

    def create_task_note(self, task: Task) -> None:
        path = self._task_path(task)
        post = frontmatter.Post(
            f"""# {task.title}

## Description

{task.description}
""",
            nina_type="task",
            nina_id=task.id,
            task_type=task.task_type,
            status=task.status,
            opencode_project_id=task.opencode_project_id,
            classified_at=task.classified_at,
            classification_reason=task.classification_reason,
            classification_model=task.classification_model,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(frontmatter.dumps(post))
        task.note_path = str(path.relative_to(self.vault_path))

    def update_task_note(self, task: Task) -> None:
        path = self._task_path(task)
        if path.exists():
            post = frontmatter.loads(path.read_text())
            post.content = f"""# {task.title}

## Description

{task.description}
"""
            post.metadata["task_type"] = task.task_type
            post.metadata["status"] = task.status
            post.metadata["opencode_project_id"] = task.opencode_project_id
            post.metadata["classified_at"] = task.classified_at
            post.metadata["classification_reason"] = task.classification_reason
            post.metadata["classification_model"] = task.classification_model
            post.metadata["updated_at"] = task.updated_at
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
            task.note_path = str((archived_dir / path.name).relative_to(self.vault_path))

    def unarchive_task_note(self, task: Task) -> None:
        archived_path = (
            self.vault_path / "System" / "Archived" / f"{task.title.replace(' ', '-').lower()}.md"
        )
        if archived_path.exists():
            task_path = self._task_path(task)
            task_path.parent.mkdir(parents=True, exist_ok=True)
            os.rename(archived_path, task_path)
            task.note_path = str(task_path.relative_to(self.vault_path))

    def create_research_note(
        self,
        topic: str,
        summary: str,
        sources: Iterable[Mapping[str, str]],
        workflow_run_id: str | None,
        created_at: str,
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
        self.write_note(relative_path, body, metadata)
        return str(relative_path)

    def _meeting_path(self, title: str, started_at: str) -> Path:
        date = started_at[:10]
        return Path("Meetings") / f"{date} - {_slugify(title)}.md"

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
    pattern = re.compile(
        rf"^##\s+{re.escape(heading)}\s*$\n(?P<content>.*?)(?=^##\s+|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(body)
    if match is None:
        return ""
    return match.group("content").strip()
