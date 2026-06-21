from __future__ import annotations

from pathlib import Path
import subprocess

import pytest
from nina_core.config import get_database_path, get_vault_path
from nina_core.obsidian.service import ObsidianService
from nina_core.repositories.service import RepositoryService
from nina_core.tasks.service import TaskService
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker


def _init_git_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", str(path)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return path


def _session(isolated_config: Path):
    db_path = str(get_database_path(isolated_config))
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def test_tasks_table_has_simplified_task_columns(isolated_config: Path) -> None:
    db_path = str(get_database_path(isolated_config))
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    inspector = inspect(engine)
    task_columns = {c["name"] for c in inspector.get_columns("tasks")}
    repo_columns = {c["name"] for c in inspector.get_columns("repositories")}

    assert "repository_id" in task_columns
    assert "status" in task_columns
    for removed in (
        "project_id",
        "opencode_project_id",
        "codex_project_id",
        "codex_worktree",
        "phase",
        "phase_status",
        "phase_note",
        "note_path",
    ):
        assert removed not in task_columns
    assert {"id", "name", "path", "created_at", "updated_at"}.issubset(repo_columns)


def test_task_create_and_update_repository_id(isolated_config: Path) -> None:
    db = _session(isolated_config)
    vault = get_vault_path(isolated_config)
    try:
        repo = RepositoryService(db).create(_init_git_repo(isolated_config / "repo"))
        other = RepositoryService(db).create(_init_git_repo(isolated_config / "other-repo"))
        service = TaskService(db, ObsidianService(vault), background_classify=False)
        task = service.create("x", repository_id=repo.id, task_type="coding")
        assert task.repository_id == repo.id

        service.update(task.id, repository_id=other.id)
        refreshed = service.get(task.id)
        assert refreshed is not None
        assert refreshed.repository_id == other.id
    finally:
        db.close()


def test_coding_and_reviewing_tasks_require_repository(isolated_config: Path) -> None:
    db = _session(isolated_config)
    vault = get_vault_path(isolated_config)
    try:
        service = TaskService(db, ObsidianService(vault), background_classify=False)
        for task_type in ("coding", "reviewing"):
            with pytest.raises(ValueError, match="requires a registered repository"):
                service.create(f"{task_type} task", task_type=task_type)

        for task_type in ("research", "reminder", "blocked", "human", "done"):
            task = service.create(f"{task_type} task", task_type=task_type)
            assert task.repository_id is None

        task = service.create("x", task_type="research")
        with pytest.raises(ValueError, match="requires a registered repository"):
            service.update(task.id, task_type="reviewing")
    finally:
        db.close()


def test_task_status_is_idle_working_or_error(isolated_config: Path) -> None:
    db = _session(isolated_config)
    vault = get_vault_path(isolated_config)
    try:
        service = TaskService(db, ObsidianService(vault), background_classify=False)
        task = service.create("status task", auto_classify=False)
        for status in ("idle", "working", "error"):
            updated = service.update(task.id, status=status)
            assert updated is not None
            assert updated.status == status
        with pytest.raises(ValueError, match="status"):
            service.update(task.id, status="blocked")
    finally:
        db.close()
