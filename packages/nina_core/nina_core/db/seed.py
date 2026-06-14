import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from nina_core.models.models import KanbanColumn, ScheduledJob  # type: ignore[import-untyped]

KANBAN_COLUMNS = [
    ("Backlog", 0),
    ("Todo", 1),
    ("Doing", 2),
    ("Review", 3),
    ("Done", 4),
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def seed_kanban_columns(db: Session) -> None:
    existing = {c.name for c in db.query(KanbanColumn).all()}
    now = _now()
    for name, position in KANBAN_COLUMNS:
        if name not in existing:
            db.add(
                KanbanColumn(
                    id=str(uuid.uuid4()),
                    name=name,
                    position=position,
                    created_at=now,
                    updated_at=now,
                )
            )


def seed_scheduled_jobs(db: Session) -> None:
    existing = {j.name for j in db.query(ScheduledJob).all()}
    now = _now()
    if "daily-summary" not in existing:
        db.add(
            ScheduledJob(
                id=str(uuid.uuid4()),
                name="daily-summary",
                workflow_name="summarize-last-day",
                schedule_kind="cron",
                schedule_value="0 7 * * *",
                enabled=1,
                created_at=now,
                updated_at=now,
            )
        )
