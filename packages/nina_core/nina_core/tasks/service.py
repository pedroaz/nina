import atexit
import os
import threading
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from nina_core.models.models import TASK_AGENT_STATUSES, TASK_TYPES, Repository, Task

from nina_core.obsidian.service import ObsidianService


_CLASSIFICATION_THREADS: list[threading.Thread] = []
_CLASSIFICATION_LOCK = threading.Lock()


def _background_classify_enabled() -> bool:
    """Whether TaskService.create should run the AI classifier in a thread."""

    return os.environ.get("NINA_BACKGROUND_CLASSIFY", "1") != "0"


def _register_classification_thread(thread: threading.Thread) -> None:
    with _CLASSIFICATION_LOCK:
        _CLASSIFICATION_THREADS.append(thread)


def _drain_classification_threads(timeout: float = 0.0) -> None:
    """Wait briefly for any in-flight classification threads. Used by tests."""

    import time

    deadline = time.time() + timeout
    with _CLASSIFICATION_LOCK:
        threads = list(_CLASSIFICATION_THREADS)
    for thread in threads:
        remaining = max(0.0, deadline - time.time())
        thread.join(timeout=remaining)
        with _CLASSIFICATION_LOCK:
            if thread in _CLASSIFICATION_THREADS:
                _CLASSIFICATION_THREADS.remove(thread)


atexit.register(_drain_classification_threads)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_task_type(value: str | None) -> str | None:
    if value is None:
        return None
    if value not in TASK_TYPES:
        allowed = ", ".join(TASK_TYPES)
        raise ValueError(f"Invalid task_type {value!r}. Expected one of: {allowed}")
    return value


def _validate_status(value: str | None) -> str | None:
    if value is None:
        return None
    if value not in TASK_AGENT_STATUSES:
        raise ValueError(f"status {value!r} is invalid")
    return value


NO_REPOSITORY_TASK_TYPES = {"unclassified", "reminder", "research", "blocked", "human", "done"}


def _task_type_allows_missing_repository(task_type: str) -> bool:
    return task_type in NO_REPOSITORY_TASK_TYPES


def _repository_required_message(task_type: str) -> str:
    return f"task_type {task_type!r} requires a registered repository"


class TaskService:
    def __init__(
        self,
        db: Session,
        obsidian: ObsidianService,
        *,
        background_classify: bool | None = None,
    ) -> None:
        self.db = db
        self.obsidian = obsidian
        self._classification_threads: list[threading.Thread] = []
        if background_classify is None:
            background_classify = _background_classify_enabled()
        self._background_classify = background_classify

    def create(
        self,
        title: str,
        description: str = "",
        repository_id: str | None = None,
        task_type: str = "unclassified",
        auto_classify: bool = True,
    ) -> Task:
        normalized_type = _validate_task_type(task_type) or "unclassified"
        normalized_repository_id = self._normalize_repository_id(repository_id)
        self._validate_repository_for_task_type(normalized_type, normalized_repository_id)
        task = Task(
            id=str(uuid.uuid4()),
            title=title,
            description=description,
            repository_id=normalized_repository_id,
            task_type=normalized_type,
            status="idle",
            created_at=_now(),
            updated_at=_now(),
        )
        self.db.add(task)
        self.db.commit()
        self.obsidian.create_task_note(task)
        self.db.commit()
        if auto_classify and normalized_type == "unclassified":
            if self._background_classify:
                self._enqueue_classification(task.id)
            else:
                self._classify_synchronously(task.id)
        return task

    def _normalize_repository_id(self, repository_id: str | None) -> str | None:
        if repository_id is None or repository_id == "":
            return None
        repo = self.db.query(Repository).filter(Repository.id == repository_id).first()
        if repo is None:
            raise ValueError(f"Repository not found: {repository_id}")
        return repo.id

    def _validate_repository_for_task_type(
        self, task_type: str, repository_id: str | None
    ) -> None:
        if not repository_id and not _task_type_allows_missing_repository(task_type):
            raise ValueError(_repository_required_message(task_type))

    def _classify_synchronously(self, task_id: str) -> None:
        from nina_core.workflows.runner import WorkflowRunner

        db_path = _resolve_db_path(self.db)
        config = _resolve_config()
        try:
            WorkflowRunner(db_path, config=config).run("classify-task", {"task_id": task_id})
        except Exception:
            pass

    def wait_for_classifications(self, timeout: float = 5.0) -> None:
        """Block until all background classification threads finish."""

        import time

        deadline = time.time() + timeout
        for thread in list(self._classification_threads):
            remaining = max(0.0, deadline - time.time())
            thread.join(timeout=remaining)
            self._classification_threads.remove(thread)

    def list(
        self,
        task_type: str | None = None,
        status: str | None = None,
        include_archived: bool = False,
        repository_id: str | None = None,
    ) -> list[Task]:
        query = self.db.query(Task).filter(Task.task_type != "deleted")
        if not include_archived:
            query = query.filter(Task.task_type != "archived")
        if task_type:
            query = query.filter(Task.task_type == task_type)
        if status:
            query = query.filter(Task.status == status)
        if repository_id:
            query = query.filter(Task.repository_id == repository_id)
        query = query.order_by(Task.created_at.desc())
        return query.all()

    def get(self, task_id: str) -> Task | None:
        return self.db.query(Task).filter(Task.id == task_id).first()

    def update(
        self,
        task_id: str,
        title: str | None = None,
        description: str | None = None,
        task_type: str | None = None,
        status: str | None = None,
        repository_id: str | None = None,
    ) -> Task | None:
        task = self.get(task_id)
        if not task:
            return None
        target_type = task.task_type
        if task_type is not None:
            target_type = _validate_task_type(task_type) or task.task_type
        target_repository_id = task.repository_id
        if repository_id is not None:
            target_repository_id = self._normalize_repository_id(repository_id)
        if task_type is not None or repository_id is not None:
            self._validate_repository_for_task_type(target_type, target_repository_id)
        if title is not None:
            task.title = title
        if description is not None:
            task.description = description
        if task_type is not None:
            normalized = _validate_task_type(task_type)
            if normalized is None:
                raise ValueError(f"task_type {task_type!r} is invalid")
            task.task_type = normalized
        if status is not None:
            task.status = _validate_status(status) or task.status
        if repository_id is not None:
            task.repository_id = target_repository_id
        task.updated_at = _now()
        self.db.commit()
        self.obsidian.update_task_note(task)
        return task

    def delete(self, task_id: str) -> bool:
        task = self.get(task_id)
        if not task:
            return False
        task.task_type = "deleted"
        task.updated_at = _now()
        self.db.commit()
        self.obsidian.delete_task_note(task)
        return True

    def archive(self, task_id: str) -> Task | None:
        task = self.get(task_id)
        if not task:
            return None
        task.task_type = "archived"
        task.updated_at = _now()
        self.db.commit()
        self.obsidian.archive_task_note(task)
        return task

    def unarchive(self, task_id: str) -> Task | None:
        task = self.get(task_id)
        if not task:
            return None
        task.task_type = "unclassified"
        task.updated_at = _now()
        self.db.commit()
        self.obsidian.unarchive_task_note(task)
        return task

    def set_agent_status(self, task_id: str, status: str) -> Task | None:
        return self.update(task_id, status=_validate_status(status))

    def add_activity(self, task_id: str, message: str) -> Task | None:
        task = self.get(task_id)
        if task is None:
            return None
        self.obsidian.append_task_activity(task, message)
        return task

    def _enqueue_classification(self, task_id: str) -> None:
        """Run the classify-task workflow on a background thread.

        The POST /tasks call returns immediately; the workflow updates the
        row in-place when it completes. If the daemon dies mid-classification
        the task simply stays as unclassified (no persistent queue yet).
        """

        from nina_core.workflows.runner import WorkflowRunner

        db_path = _resolve_db_path(self.db)
        config = _resolve_config()

        def _runner() -> None:
            try:
                runner = WorkflowRunner(db_path, config=config)
                runner.run("classify-task", {"task_id": task_id})
            except Exception:
                pass

        thread = threading.Thread(target=_runner, name=f"classify-task-{task_id}", daemon=True)
        thread.start()
        _register_classification_thread(thread)
        self._classification_threads.append(thread)


def _resolve_db_path(db: Session) -> str:
    bind = db.get_bind()
    url = getattr(bind, "url", None)
    if url is not None and getattr(url, "database", None):
        return str(url.database)
    return ""


def _resolve_config():
    from nina_core.config import load_effective_config
    from nina_core.workflows.runner import _resolve_config_dir

    try:
        return load_effective_config(_resolve_config_dir())
    except Exception:
        return None
