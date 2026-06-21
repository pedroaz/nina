from __future__ import annotations

from pathlib import Path

from nina_core.config import get_database_path, get_vault_path
from nina_core.obsidian.service import ObsidianService
from nina_core.tasks.service import TaskService
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def test_task_archive_creates_archived_folder_when_missing(isolated_config: Path) -> None:
    db_path = str(get_database_path(isolated_config))
    vault = get_vault_path(isolated_config)
    archived_dir = vault / "System" / "Archived"
    archived_dir.rmdir()
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    session_local = sessionmaker(bind=engine)
    db = session_local()
    try:
        service = TaskService(db, ObsidianService(vault), background_classify=False)
        task = service.create("Archive me", auto_classify=False)

        archived = service.archive(task.id)

        assert archived is not None
        assert (archived_dir / f"{task.id}.md").is_file()
    finally:
        db.close()
