import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import frontmatter

from nina_core.models.models import Project, Task


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

    def _project_path(self, project: Project) -> Path:
        return self.vault_path / "Projects" / f"{project.name.replace(' ', '-').lower()}.md"

    def _task_path(self, task: Task) -> Path:
        return self.vault_path / "Tasks" / f"{task.title.replace(' ', '-').lower()}.md"

    def create_project_note(self, project: Project) -> None:
        path = self._project_path(project)
        post = frontmatter.Post(
            f"""# {project.name}

## Description

{project.description}
""",
            nina_type="project",
            nina_id=project.id,
            status=project.status,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(frontmatter.dumps(post))
        project.note_path = str(path.relative_to(self.vault_path))

    def update_project_note(self, project: Project) -> None:
        path = self._project_path(project)
        if path.exists():
            post = frontmatter.loads(path.read_text())
            post.content = f"""# {project.name}

## Description

{project.description}
"""
            post.metadata["status"] = project.status
            post.metadata["updated_at"] = project.updated_at
            path.write_text(frontmatter.dumps(post))

    def delete_project_note(self, project: Project) -> None:
        path = self._project_path(project)
        if path.exists():
            deleted_dir = self.vault_path / "System" / "Deleted"
            deleted_dir.mkdir(parents=True, exist_ok=True)
            os.rename(path, deleted_dir / path.name)

    def create_task_note(self, task: Task) -> None:
        path = self._task_path(task)
        post = frontmatter.Post(
            f"""# {task.title}

## Description

{task.description}
""",
            nina_type="task",
            nina_id=task.id,
            status=task.status,
            project_id=task.project_id,
            kanban_column=task.kanban_column,
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
            post.metadata["status"] = task.status
            post.metadata["project_id"] = task.project_id
            post.metadata["kanban_column"] = task.kanban_column
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

    def _meeting_body(
        self,
        title: str,
        started_at: str,
        ended_at: str | None,
        duration_seconds: int | None,
        source: str,
        transcript_section: str,
        summary_section: str,
        action_items: str,
        decisions: str,
    ) -> str:
        duration_minutes = ""
        if duration_seconds is not None:
            duration_minutes = (
                f" ({int(duration_seconds) // 60}m {int(duration_seconds) % 60:02d}s)"
            )
        date_part = started_at[:10]
        return "\n".join(
            [
                f"# {title}",
                "",
                "## Notes",
                "",
                f"Recording captured on {date_part} from `{source}` input{duration_minutes}.",
                "",
                "## Transcript",
                "",
                transcript_section.strip() or "_Transcription pending._",
                "",
                "## Summary",
                "",
                summary_section.strip() or "_Summary pending._",
                "",
                "## Action items",
                "",
                action_items.strip() or "- _none yet_",
                "",
                "## Decisions",
                "",
                decisions.strip() or "- _none yet_",
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
        body = self._meeting_body(
            title=title,
            started_at=started_at,
            ended_at=ended_at,
            duration_seconds=duration_seconds,
            source=source,
            transcript_section="",
            summary_section="",
            action_items="",
            decisions="",
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
    ) -> str | None:
        relative_path = self._meeting_path(title, started_at)
        full_path = self.vault_path / relative_path
        if not full_path.is_file():
            return None
        post = frontmatter.loads(full_path.read_text())
        existing_transcript_section = _extract_section(post.content, "Transcript")
        existing_summary_section = _extract_section(post.content, "Summary")
        existing_action_items = _extract_section(post.content, "Action items")
        existing_decisions = _extract_section(post.content, "Decisions")
        body = self._meeting_body(
            title=title,
            started_at=started_at,
            ended_at=ended_at,
            duration_seconds=duration_seconds,
            source=source,
            transcript_section=transcript
            if transcript is not None
            else existing_transcript_section,
            summary_section=summary if summary is not None else existing_summary_section,
            action_items=action_items if action_items is not None else existing_action_items,
            decisions=decisions if decisions is not None else existing_decisions,
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
        post.metadata["updated_at"] = datetime.now(timezone.utc).isoformat()
        full_path.write_text(frontmatter.dumps(post))
        return str(relative_path)

    def soft_delete_meeting_note(self, meeting_id: str, title: str, started_at: str) -> str | None:
        relative_path = self._meeting_path(title, started_at)
        full_path = self.vault_path / relative_path
        if not full_path.is_file():
            return None
        deleted_dir = self.vault_path / "System" / "Deleted"
        deleted_dir.mkdir(parents=True, exist_ok=True)
        os.rename(full_path, deleted_dir / full_path.name)
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
