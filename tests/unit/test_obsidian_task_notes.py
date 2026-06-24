from __future__ import annotations

from pathlib import Path

from nina_core.models.models import Task
from nina_core.obsidian.service import ObsidianService


def _task(task_id: str) -> Task:
    return Task(
        id=task_id,
        title="Task note",
        description="Description",
        task_type="research",
        status="idle",
        pipeline_stage="created",
        pipeline_error=None,
        pipeline_rework_count=0,
        repository_id=None,
        classified_at=None,
        classification_reason=None,
        classification_model=None,
        created_at="2026-06-20T12:00:00+00:00",
        updated_at="2026-06-20T12:00:00+00:00",
    )


def _note_path(vault: Path, task_id: str) -> Path:
    return vault / "Tasks" / f"{task_id}.md"


def test_set_task_prompt_applies_after_recreating_missing_note(tmp_path: Path) -> None:
    obsidian = ObsidianService(tmp_path)
    task = _task("task-prompt")
    obsidian.create_task_note(task)
    _note_path(tmp_path, task.id).unlink()

    obsidian.set_task_prompt(task, "Prompt from Codex")

    content = _note_path(tmp_path, task.id).read_text()
    assert "Prompt from Codex" in content
    assert "No prompt captured yet." not in content


def test_set_task_summary_applies_after_recreating_missing_note(tmp_path: Path) -> None:
    obsidian = ObsidianService(tmp_path)
    task = _task("task-summary")
    obsidian.create_task_note(task)
    _note_path(tmp_path, task.id).unlink()

    obsidian.set_task_summary(task, "Outcome: completed\nSummary: Done.")

    content = _note_path(tmp_path, task.id).read_text()
    assert "Outcome: completed" in content
    assert "No summary yet." not in content
