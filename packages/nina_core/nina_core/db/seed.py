import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from nina_core.models.models import ScheduledJob  # type: ignore[import-untyped]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


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
    if "reindex-vault" not in existing:
        db.add(
            ScheduledJob(
                id=str(uuid.uuid4()),
                name="reindex-vault",
                workflow_name="reindex-vault",
                schedule_kind="cron",
                schedule_value="*/15 * * * *",
                enabled=1,
                created_at=now,
                updated_at=now,
            )
        )
