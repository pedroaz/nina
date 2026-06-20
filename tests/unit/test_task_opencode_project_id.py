"""Schema and service tests for `tasks.opencode_project_id`."""

from __future__ import annotations

from pathlib import Path

from nina_core.config import get_database_path, get_vault_path
from nina_core.obsidian.service import ObsidianService
from nina_core.tasks.service import TaskService
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker


def test_tasks_table_has_opencode_project_id(isolated_config: Path) -> None:
    """The new column is present and old `project_id` is gone."""

    db_path = str(get_database_path(isolated_config))
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    inspector = inspect(engine)
    columns = {c["name"] for c in inspector.get_columns("tasks")}
    assert "opencode_project_id" in columns
    assert "project_id" not in columns


def test_task_create_persists_opencode_project_id(isolated_config: Path) -> None:
    db_path = str(get_database_path(isolated_config))
    vault = get_vault_path(isolated_config)
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    SessionLocal = sessionmaker(bind=engine)  # noqa: N806
    db = SessionLocal()
    try:
        service = TaskService(db, ObsidianService(vault), background_classify=False)
        task = service.create(
            "wire opencode to daemon",
            description="supervise opencode serve",
            opencode_project_id="abc123",
        )
        assert task.opencode_project_id == "abc123"

        # Filter by project id via the service.
        rows = service.list(opencode_project_id="abc123")
        assert len(rows) == 1
        assert rows[0].id == task.id
    finally:
        db.close()


def test_task_update_can_clear_opencode_project_id(isolated_config: Path) -> None:
    db_path = str(get_database_path(isolated_config))
    vault = get_vault_path(isolated_config)
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    SessionLocal = sessionmaker(bind=engine)  # noqa: N806
    db = SessionLocal()
    try:
        service = TaskService(db, ObsidianService(vault), background_classify=False)
        task = service.create("x", opencode_project_id="proj-1")
        assert task.opencode_project_id == "proj-1"

        service.update(task.id, opencode_project_id="")
        refreshed = service.get(task.id)
        assert refreshed is not None
        assert refreshed.opencode_project_id in (None, "")
    finally:
        db.close()
