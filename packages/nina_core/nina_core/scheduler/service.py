import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from croniter import croniter
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from nina_core.models.models import JobRun, ScheduledJob, WorkflowRun
from nina_core.workflows.runner import WorkflowRunner


RETRY_BACKOFFS_SECONDS: tuple[int, ...] = (30, 300, 1800)
MAX_ATTEMPTS: int = 3
STALE_RUN_ERROR: str = "daemon restarted"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _cron_trigger(value: str) -> CronTrigger:
    try:
        return CronTrigger.from_crontab(value)
    except ValueError as exc:
        raise ValueError(f"Invalid cron expression '{value}'") from exc


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


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
        self._sweep_stale_running_runs()
        self._backfill_missed_runs()

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
            success = self._execute_workflow(db, job, run)
            job.updated_at = _now()
            db.commit()
            if not success:
                self._maybe_schedule_retry(job_name)
            return self._run_to_dict(run)
        finally:
            db.close()

    def _execute_workflow(self, db: Session, job: ScheduledJob, run: JobRun) -> bool:
        """Run the job's workflow, update the run, return True on success.

        Exceptions are caught here so the caller can decide whether to
        schedule a retry; the run row's status/error reflect the outcome.
        Workflows that fail gracefully inside `WorkflowRunner.run` (e.g.
        `Unknown workflow '...'`) still come back through the inner
        try/except, so the outer wrapper checks the returned `status`.
        """
        try:
            runner = WorkflowRunner(self.db_path)
            workflow_run = runner.run(str(job.workflow_name), {})
        except Exception as exc:
            run.status = "failed"
            run.error = str(exc)
            run.completed_at = _now()
            return False
        run.workflow_run_id = workflow_run.get("id")
        run.completed_at = _now()
        if workflow_run.get("status") == "completed":
            run.status = "completed"
            return True
        run.status = "failed"
        output = workflow_run.get("output") or {}
        run.error = str(output.get("error") or "workflow did not complete")
        return False

    def _maybe_schedule_retry(self, job_name: str) -> None:
        """Schedule a retry for a failed job run using backoff.

        Counts consecutive failed `JobRun` rows since the last successful
        run and, if under `MAX_ATTEMPTS`, enqueues a one-shot `date`
        trigger so the worker thread is freed for other jobs.
        """
        db = self._session()
        try:
            job = db.query(ScheduledJob).filter(ScheduledJob.name == job_name).first()
            if job is None or not job.enabled:
                return
            last_success = (
                db.query(JobRun)
                .filter(JobRun.scheduled_job_id == job.id, JobRun.status == "completed")
                .order_by(JobRun.completed_at.desc())
                .first()
            )
            if last_success and last_success.completed_at:
                failures = (
                    db.query(JobRun)
                    .filter(
                        JobRun.scheduled_job_id == job.id,
                        JobRun.status == "failed",
                        JobRun.completed_at > last_success.completed_at,
                    )
                    .count()
                )
            else:
                failures = (
                    db.query(JobRun)
                    .filter(JobRun.scheduled_job_id == job.id, JobRun.status == "failed")
                    .count()
                )
            attempts_done = failures
            if attempts_done >= MAX_ATTEMPTS:
                return
            delay = RETRY_BACKOFFS_SECONDS[attempts_done - 1]
            run_date = datetime.now(timezone.utc) + timedelta(seconds=delay)
            self.scheduler.add_job(
                self._run_job,
                "date",
                run_date=run_date,
                args=[str(job.name)],
                id=f"retry:{job.name}:{attempts_done - 1}",
                replace_existing=True,
            )
        finally:
            db.close()

    def _sweep_stale_running_runs(self) -> None:
        """Mark runs left in 'running' from a prior daemon as 'interrupted'.

        APScheduler does not persist job state, so anything in 'running'
        on startup is by definition stale (the worker thread that owned
        it no longer exists). Without this sweep the UI would show
        permanently-running rows after every daemon restart.
        """
        db = self._session()
        try:
            now = _now()
            stale_job_runs = db.query(JobRun).filter(JobRun.status == "running").all()
            for run in stale_job_runs:
                run.status = "interrupted"
                run.error = STALE_RUN_ERROR
                run.completed_at = now
            stale_workflow_runs = (
                db.query(WorkflowRun).filter(WorkflowRun.status == "running").all()
            )
            for run in stale_workflow_runs:
                run.status = "interrupted"
                run.error = STALE_RUN_ERROR
                run.completed_at = now
            if stale_job_runs or stale_workflow_runs:
                db.commit()
        finally:
            db.close()

    def _backfill_missed_runs(self) -> None:
        """Fire missed cron firings on startup.

        Nina runs on a personal computer; the daemon can be off for days
        while a job's cron keeps ticking. APScheduler's in-memory
        scheduler loses those firings, so on startup we compute the next
        cron tick after the last run (or after the job was created) and,
        if that tick has already passed, enqueue a single one-shot run.
        At most one backfill per job per daemon-up window.
        """
        db = self._session()
        try:
            now = datetime.now(timezone.utc)
            for job in db.query(ScheduledJob).filter(ScheduledJob.enabled == 1).all():
                anchor = _parse_iso(job.last_run_at) or _parse_iso(job.created_at)
                if anchor is None:
                    continue
                try:
                    itr = croniter(str(job.schedule_value), anchor)
                    next_fire = itr.get_next(datetime)
                except Exception:
                    continue
                if next_fire is None or next_fire > now:
                    continue
                self.scheduler.add_job(
                    self._run_job,
                    "date",
                    run_date=now,
                    args=[str(job.name)],
                    id=f"backfill:{job.name}:{next_fire.isoformat()}",
                    replace_existing=True,
                )
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
