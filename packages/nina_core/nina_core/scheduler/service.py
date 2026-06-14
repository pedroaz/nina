import uuid
from datetime import datetime, timezone
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from nina_core.models.models import JobRun, ScheduledJob
from nina_core.workflows.runner import WorkflowRunner


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _cron_trigger(value: str) -> CronTrigger:
    try:
        return CronTrigger.from_crontab(value)
    except ValueError as exc:
        raise ValueError(f"Invalid cron expression '{value}'") from exc


class SchedulerService:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self.scheduler = BackgroundScheduler()
        self.jobs: dict[str, Any] = {}

    def _session(self) -> Session:
        engine = create_engine(f"sqlite:///{self.db_path}", echo=False)
        SessionLocal = sessionmaker(bind=engine)
        return SessionLocal()

    def start(self) -> None:
        self.scheduler.start()
        self.reload()

    def shutdown(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown()

    def reload(self) -> None:
        db = self._session()
        try:
            for job in db.query(ScheduledJob).all():
                if job.enabled:
                    self._schedule_job(job)
                elif job.name in self.jobs:
                    self.jobs[job.name].remove()
                    del self.jobs[job.name]
            db.commit()
        finally:
            db.close()

    def create_job(
        self,
        name: str,
        workflow_name: str,
        schedule_value: str,
        enabled: bool = True,
    ) -> dict[str, Any]:
        _cron_trigger(schedule_value)
        db = self._session()
        try:
            existing = db.query(ScheduledJob).filter(ScheduledJob.name == name).first()
            now = _now()
            if existing:
                existing.workflow_name = workflow_name
                existing.schedule_kind = "cron"
                existing.schedule_value = schedule_value
                existing.enabled = 1 if enabled else 0
                existing.updated_at = now
                job = existing
            else:
                job = ScheduledJob(
                    id=str(uuid.uuid4()),
                    name=name,
                    workflow_name=workflow_name,
                    schedule_kind="cron",
                    schedule_value=schedule_value,
                    enabled=1 if enabled else 0,
                    created_at=now,
                    updated_at=now,
                )
                db.add(job)
            db.commit()
            db.refresh(job)
            if enabled and self.scheduler.running:
                self._schedule_job(job)
            elif job.name in self.jobs:
                self.jobs[job.name].remove()
                del self.jobs[job.name]
            return self._job_to_dict(job)
        finally:
            db.close()

    def enable_job(self, job_name: str) -> dict[str, Any] | None:
        return self._set_enabled(job_name, True)

    def disable_job(self, job_name: str) -> dict[str, Any] | None:
        return self._set_enabled(job_name, False)

    def _set_enabled(self, job_name: str, enabled: bool) -> dict[str, Any] | None:
        db = self._session()
        try:
            job = db.query(ScheduledJob).filter(ScheduledJob.name == job_name).first()
            if not job:
                return None
            job.enabled = 1 if enabled else 0
            job.updated_at = _now()
            db.commit()
            db.refresh(job)
            if enabled and self.scheduler.running:
                self._schedule_job(job)
            elif job.name in self.jobs:
                self.jobs[job.name].remove()
                del self.jobs[job.name]
            return self._job_to_dict(job)
        finally:
            db.close()

    def _schedule_job(self, job: ScheduledJob) -> None:
        scheduled = self.scheduler.add_job(
            self._run_job,
            _cron_trigger(str(job.schedule_value)),
            args=[str(job.name)],
            id=str(job.name),
            replace_existing=True,
        )
        self.jobs[str(job.name)] = scheduled
        self._record_next_run(
            str(job.name), scheduled.next_run_time.isoformat() if scheduled.next_run_time else None
        )

    def _record_next_run(self, job_name: str, next_run_at: str | None) -> None:
        db = self._session()
        try:
            job = db.query(ScheduledJob).filter(ScheduledJob.name == job_name).first()
            if job:
                job.next_run_at = next_run_at
                job.updated_at = _now()
                db.commit()
        finally:
            db.close()

    def _run_job(self, job_name: str) -> dict[str, Any]:
        db = self._session()
        run = None
        try:
            job = db.query(ScheduledJob).filter(ScheduledJob.name == job_name).first()
            if not job:
                raise ValueError(f"Unknown job '{job_name}'")
            now = _now()
            run = JobRun(
                id=str(uuid.uuid4()),
                job_name=job.name,
                scheduled_job_id=job.id,
                status="running",
                started_at=now,
                created_at=now,
            )
            db.add(run)
            job.last_run_at = now
            db.commit()
            try:
                runner = WorkflowRunner(self.db_path)
                workflow_run = runner.run(str(job.workflow_name), {})
                run.workflow_run_id = workflow_run.get("id")
                run.status = "completed"
                run.completed_at = _now()
            except Exception as exc:
                run.status = "failed"
                run.error = str(exc)
            job.updated_at = _now()
            db.commit()
            return self._run_to_dict(run)
        finally:
            db.close()

    def run_job_now(self, job_name: str) -> dict[str, Any] | None:
        db = self._session()
        try:
            job = db.query(ScheduledJob).filter(ScheduledJob.name == job_name).first()
            if not job:
                return None
        finally:
            db.close()
        return self._run_job(job_name)

    def list_jobs(self) -> list[dict[str, Any]]:
        db = self._session()
        try:
            return [
                self._job_to_dict(job)
                for job in db.query(ScheduledJob).order_by(ScheduledJob.name).all()
            ]
        finally:
            db.close()

    def list_job_runs(self, job_name: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        db = self._session()
        try:
            query = db.query(JobRun)
            if job_name:
                query = query.filter(JobRun.job_name == job_name)
            runs = query.order_by(JobRun.created_at.desc()).limit(limit).all()
            return [self._run_to_dict(run) for run in runs]
        finally:
            db.close()

    def _job_to_dict(self, job: ScheduledJob) -> dict[str, Any]:
        live_job = self.jobs.get(str(job.name))
        next_run_at = job.next_run_at
        if live_job and live_job.next_run_time:
            next_run_at = live_job.next_run_time.isoformat()
        return {
            "id": job.id,
            "name": job.name,
            "workflow_name": job.workflow_name,
            "schedule_kind": job.schedule_kind,
            "schedule": job.schedule_value,
            "enabled": bool(job.enabled),
            "last_run_at": job.last_run_at,
            "next_run_at": next_run_at,
            "created_at": job.created_at,
            "updated_at": job.updated_at,
        }

    def _run_to_dict(self, run: JobRun) -> dict[str, Any]:
        return {
            "id": run.id,
            "job_name": run.job_name,
            "scheduled_job_id": run.scheduled_job_id,
            "workflow_run_id": run.workflow_run_id,
            "status": run.status,
            "scheduled_at": run.scheduled_at,
            "started_at": run.started_at,
            "completed_at": run.completed_at,
            "error": run.error,
            "created_at": run.created_at,
        }
