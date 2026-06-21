from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from nina_core.models.models import WorkflowRun
from nina_core.workflows.runner import WORKFLOW_DESCRIPTIONS, WorkflowRunner

from ..dependencies import _active_config_path, _request_config, get_db_session
from ..schemas import ResearchRunInput, WorkflowInput


router = APIRouter()


@router.post("/research/run")
async def run_research(request: Request, data: ResearchRunInput) -> Any:
    db_path = _active_config_path()
    runner = WorkflowRunner(db_path, config=_request_config(request))
    result = runner.run("research-topic", {"topic": data.topic})
    if result.get("status") != "completed":
        return JSONResponse(status_code=400, content=result)
    output = dict(result.get("output", {}))
    output["workflow_run_id"] = result.get("id")
    output["status"] = result.get("status")
    output["created_at"] = result.get("created_at")
    return output


@router.get("/workflows")
async def list_workflows(request: Request) -> list[dict[str, str]]:
    """Return the known workflow names with a short description of each."""

    return [
        {"name": name, "description": WORKFLOW_DESCRIPTIONS.get(name, "")}
        for name in [
            "summarize-last-day",
            "research-topic",
            "reindex-vault",
            "transcribe-meeting",
            "summarize-meeting",
            "meeting-pipeline",
            "classify-task",
            "run-task",
        ]
    ]


@router.post("/workflows/{workflow_name}/run")
async def run_workflow(
    request: Request,
    workflow_name: str,
    data: WorkflowInput,
) -> dict[str, Any]:
    db_path = _active_config_path()
    runner = WorkflowRunner(db_path, config=_request_config(request))
    return runner.run(workflow_name, data.input)


@router.get("/workflow-runs")
async def list_workflow_runs(request: Request) -> list[dict[str, Any]]:
    with get_db_session() as db:
        runs = db.query(WorkflowRun).order_by(WorkflowRun.created_at.desc()).all()
        return [
            {
                "id": run.id,
                "workflow_name": run.workflow_name,
                "status": run.status,
                "created_at": run.created_at,
            }
            for run in runs
        ]


@router.get("/workflow-runs/{run_id}")
async def get_workflow_run(request: Request, run_id: str) -> dict[str, Any]:
    with get_db_session() as db:
        run = db.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()
        if not run:
            raise HTTPException(status_code=404, detail="Not found")
        return {
            "id": run.id,
            "workflow_name": run.workflow_name,
            "status": run.status,
            "input": run.input_json,
            "created_at": run.created_at,
        }
