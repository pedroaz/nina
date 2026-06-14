from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from nina_core.models.models import WorkflowRun, WorkflowStep
from nina_core.research.service import ResearchService


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class WorkflowRunner:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    def _session(self) -> Session:
        engine = create_engine(f"sqlite:///{self.db_path}", echo=False)
        SessionLocal = sessionmaker(bind=engine)
        return SessionLocal()

    def run(self, workflow_name: str, input_data: dict[str, Any]) -> dict[str, Any]:
        db = self._session()
        run = WorkflowRun(
            id=str(uuid.uuid4()),
            workflow_name=workflow_name,
            status="running",
            input_json=json.dumps(input_data),
            created_at=_now(),
            updated_at=_now(),
        )
        db.add(run)
        db.commit()
        output: dict[str, Any] = {}
        try:
            if workflow_name == "summarize-last-day":
                output = self._run_summarize(db, run)
            elif workflow_name == "research-topic":
                output = self._run_research(db, run, input_data)
            else:
                raise ValueError(f"Unknown workflow '{workflow_name}'")
            run.output_json = json.dumps(output)
            run.status = "completed"
            run.completed_at = _now()
        except Exception as exc:
            run.status = "failed"
            run.error = str(exc)
            output = {"error": str(exc)}
        run.updated_at = _now()
        db.commit()
        result = {
            "id": run.id,
            "workflow_name": run.workflow_name,
            "status": run.status,
            "created_at": run.created_at,
            "output": output,
        }
        db.close()
        return result

    def _create_step(self, db: Session, run: WorkflowRun, step_name: str) -> WorkflowStep:
        step = WorkflowStep(
            id=str(uuid.uuid4()),
            workflow_run_id=run.id,
            step_name=step_name,
            status="running",
            attempt_count=1,
            created_at=_now(),
            updated_at=_now(),
        )
        db.add(step)
        db.commit()
        return step

    def _complete_step(self, db: Session, step: WorkflowStep, output: dict[str, Any] | None = None) -> None:
        step.status = "completed"
        step.output_json = json.dumps(output or {})
        step.completed_at = _now()
        step.updated_at = _now()
        db.commit()

    def _fail_step(self, db: Session, step: WorkflowStep, error: str) -> None:
        step.status = "failed"
        step.error = error
        step.updated_at = _now()
        db.commit()

    def _run_summarize(self, db: Session, run: WorkflowRun) -> dict[str, Any]:
        step = self._create_step(db, run, "build_context")
        self._complete_step(db, step, {"message": "Daily summary workflow is scaffolded."})
        run.status = "completed"
        run.completed_at = _now()
        run.updated_at = _now()
        db.commit()
        return {"message": "Daily summary workflow is scaffolded."}

    def _run_research(self, db: Session, run: WorkflowRun, input_data: dict[str, Any]) -> dict[str, Any]:
        topic = str(input_data.get("topic", "")).strip()
        if not topic:
            raise ValueError("Workflow 'research-topic' requires a 'topic' field")

        plan_step = self._create_step(db, run, "plan")
        self._complete_step(db, plan_step, {"topic": topic})

        research_step = self._create_step(db, run, "research")
        vault_path = os.environ.get("NINA_VAULT_PATH", "")
        if not vault_path:
            raise RuntimeError("NINA_VAULT_PATH is required for research workflows")
        service = ResearchService(self.db_path, vault_path)
        report = service.run(topic, workflow_run_id=run.id, created_at=run.created_at)
        self._complete_step(db, research_step, report)

        finish_step = self._create_step(db, run, "finalize")
        finish_payload = {
            "note_path": report.get("note_path"),
            "source_count": len(report.get("sources", [])),
        }
        self._complete_step(db, finish_step, finish_payload)
        run.output_json = json.dumps(report)
        run.status = "completed"
        run.completed_at = _now()
        run.updated_at = _now()
        db.commit()
        return report
