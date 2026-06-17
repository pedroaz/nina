from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from nina_core.config import get_database_path
from nina_core.models.models import JobRun, ScheduledJob, WorkflowRun
from nina_core.scheduler.service import (
    MAX_ATTEMPTS,
    RETRY_BACKOFFS_SECONDS,
    STALE_RUN_ERROR,
    SchedulerService,
)


def _session_for(db_path: str):
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def _add_job(
    db_path: str,
    name: str,
    schedule: str,
    workflow_name: str = "summarize-last-day",
    last_run_at: str | None = None,
) -> str:
    db = _session_for(db_path)
    try:
        now = datetime.now(timezone.utc).isoformat()
        job = ScheduledJob(
            id=str(uuid.uuid4()),
            name=name,
            workflow_name=workflow_name,
            schedule_kind="cron",
            schedule_value=schedule,
            enabled=1,
            last_run_at=last_run_at,
            created_at=now,
            updated_at=now,
        )
        db.add(job)
        db.commit()
        return job.id
    finally:
        db.close()


def test_sweep_marks_stale_running_runs(isolated_config: Path) -> None:
    db_path = str(get_database_path(isolated_config))
    job_id = _add_job(db_path, "stale-job", "0 7 * * *")
    job_run_id = str(uuid.uuid4())
    workflow_run_id = str(uuid.uuid4())
    db = _session_for(db_path)
    try:
        now = datetime.now(timezone.utc).isoformat()
        db.add(
            JobRun(
                id=job_run_id,
                job_name="stale-job",
                scheduled_job_id=job_id,
                status="running",
                started_at=now,
                created_at=now,
            )
        )
        db.add(
            WorkflowRun(
                id=workflow_run_id,
                workflow_name="summarize-last-day",
                status="running",
                created_at=now,
                updated_at=now,
            )
        )
        db.commit()
    finally:
        db.close()

    scheduler = SchedulerService(db_path)
    try:
        scheduler.start()

        db = _session_for(db_path)
        try:
            refreshed = db.query(JobRun).filter(JobRun.id == job_run_id).one()
            assert refreshed.status == "interrupted"
            assert refreshed.error == STALE_RUN_ERROR
            assert refreshed.completed_at is not None
            refreshed_wf = (
                db.query(WorkflowRun).filter(WorkflowRun.id == workflow_run_id).one()
            )
            assert refreshed_wf.status == "interrupted"
        finally:
            db.close()
    finally:
        scheduler.shutdown()


def test_backfill_fires_missed_run(isolated_config: Path) -> None:
    db_path = str(get_database_path(isolated_config))
    yesterday_six = (datetime.now(timezone.utc) - timedelta(days=1)).replace(
        hour=6, minute=0, second=0, microsecond=0
    )
    _add_job(db_path, "missed-job", "0 7 * * *", last_run_at=yesterday_six.isoformat())

    scheduler = SchedulerService(db_path)
    scheduler.start()
    try:
        assert scheduler.scheduler.running
        scheduled_jobs = scheduler.scheduler.get_jobs()
        backfill_ids = [
            j.id for j in scheduled_jobs if j.id.startswith("backfill:missed-job")
        ]
        assert backfill_ids, "expected a backfill one-shot to be enqueued"
    finally:
        scheduler.shutdown()


def test_retry_scheduled_on_failure(isolated_config: Path) -> None:
    db_path = str(get_database_path(isolated_config))
    _add_job(db_path, "broken-job", "0 7 * * *", workflow_name="nonexistent-workflow")

    scheduler = SchedulerService(db_path)
    scheduler.start()
    try:
        result = scheduler.run_job_now("broken-job")
        assert result is not None
        assert result["status"] == "failed"
        scheduled = scheduler.scheduler.get_jobs()
        retry_jobs = [j for j in scheduled if j.id.startswith("retry:broken-job")]
        assert retry_jobs, "expected a retry one-shot to be enqueued"
        run_date = retry_jobs[0].next_run_time
        assert run_date is not None
        delta = (run_date - datetime.now(timezone.utc)).total_seconds()
        assert 0 < delta <= RETRY_BACKOFFS_SECONDS[0] + 1
    finally:
        scheduler.shutdown()


def test_retry_caps_at_max_attempts(isolated_config: Path) -> None:
    db_path = str(get_database_path(isolated_config))
    _add_job(
        db_path, "always-broken", "0 7 * * *", workflow_name="nonexistent-workflow"
    )
    scheduler = SchedulerService(db_path)
    scheduler.start()
    try:
        for _ in range(MAX_ATTEMPTS):
            scheduler._run_job("always-broken")
        scheduled = scheduler.scheduler.get_jobs()
        retry_ids = sorted(
            j.id for j in scheduled if j.id.startswith("retry:always-broken")
        )
        # Two retries were scheduled by the first two failures (delays
        # 30s and 300s); the third failure must not enqueue another.
        assert retry_ids == ["retry:always-broken:0", "retry:always-broken:1"], retry_ids
    finally:
        scheduler.shutdown()
