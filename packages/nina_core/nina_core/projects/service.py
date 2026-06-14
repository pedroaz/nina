import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from nina_core.models.models import Project, Task

from nina_core.obsidian.service import ObsidianService


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ProjectService:
    def __init__(self, db: Session, obsidian: ObsidianService) -> None:
        self.db = db
        self.obsidian = obsidian

    def create(self, name: str, description: str = "") -> Project:
        project = Project(
            id=str(uuid.uuid4()),
            name=name,
            description=description,
            status="active",
            created_at=_now(),
            updated_at=_now(),
        )
        self.db.add(project)
        self.db.commit()
        self.obsidian.create_project_note(project)
        self.db.commit()
        return project

    def list(self) -> list[Project]:
        return self.db.query(Project).filter(Project.status != "deleted").all()

    def get(self, project_id: str) -> Project | None:
        return self.db.query(Project).filter(Project.id == project_id).first()

    def update(
        self,
        project_id: str,
        name: str | None = None,
        description: str | None = None,
        status: str | None = None,
    ) -> Project | None:
        project = self.get(project_id)
        if not project:
            return None
        if name is not None:
            project.name = name
        if description is not None:
            project.description = description
        if status is not None:
            project.status = status
        project.updated_at = _now()
        self.db.commit()
        self.obsidian.update_project_note(project)
        return project

    def delete(self, project_id: str) -> bool:
        project = self.get(project_id)
        if not project:
            return False
        project.status = "deleted"
        project.updated_at = _now()
        self.db.commit()
        self.obsidian.delete_project_note(project)
        return True


class TaskService:
    def __init__(self, db: Session, obsidian: ObsidianService) -> None:
        self.db = db
        self.obsidian = obsidian

    def create(self, title: str, description: str = "", project_id: str | None = None) -> Task:
        position = self.db.query(Task).filter(Task.kanban_column == "Todo").count()
        task = Task(
            id=str(uuid.uuid4()),
            title=title,
            description=description,
            project_id=project_id,
            status="todo",
            kanban_column="Todo",
            kanban_position=position,
            created_at=_now(),
            updated_at=_now(),
        )
        self.db.add(task)
        self.db.commit()
        self.obsidian.create_task_note(task)
        self.db.commit()
        return task

    def list(self, project_id: str | None = None, status: str | None = None) -> list[Task]:
        query = self.db.query(Task).filter(Task.status != "deleted")
        if project_id:
            query = query.filter(Task.project_id == project_id)
        if status:
            query = query.filter(Task.status == status)
        return query.all()

    def get(self, task_id: str) -> Task | None:
        return self.db.query(Task).filter(Task.id == task_id).first()

    def update(
        self,
        task_id: str,
        title: str | None = None,
        description: str | None = None,
        status: str | None = None,
        kanban_column: str | None = None,
        kanban_position: int | None = None,
    ) -> Task | None:
        task = self.get(task_id)
        if not task:
            return None
        if title is not None:
            task.title = title
        if description is not None:
            task.description = description
        if status is not None:
            task.status = status
        if kanban_column is not None:
            task.kanban_column = kanban_column
        if kanban_position is not None:
            task.kanban_position = kanban_position
        task.updated_at = _now()
        self.db.commit()
        self.obsidian.update_task_note(task)
        return task

    def delete(self, task_id: str) -> bool:
        task = self.get(task_id)
        if not task:
            return False
        task.status = "deleted"
        task.updated_at = _now()
        self.db.commit()
        self.obsidian.delete_task_note(task)
        return True
