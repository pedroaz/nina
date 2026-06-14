import os
import re
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
        source_lines = "\n".join(
            f"- [{source.get('title') or source['url']}]({source['url']})" for source in source_list
        ) or "- No external sources were captured."
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
