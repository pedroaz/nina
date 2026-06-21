from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from ..dependencies import get_scheduler
from ..schemas import JobCreate, JobUpdate


router = APIRouter()


@router.get("/jobs")
async def list_jobs(request: Request) -> list[dict[str, Any]]:
    return get_scheduler(request).list_jobs()


@router.post("/jobs")
async def create_job(request: Request, data: JobCreate) -> dict[str, Any]:
    try:
        return get_scheduler(request).create_job(
            data.name,
            data.workflow_name,
            data.schedule,
            data.enabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.patch("/jobs/{job_name}")
async def update_job(request: Request, job_name: str, data: JobUpdate) -> dict[str, Any]:
    service = get_scheduler(request)
    job = service.enable_job(job_name) if data.enabled else service.disable_job(job_name)
    if not job:
        raise HTTPException(status_code=404, detail="Not found")
    return job


@router.post("/jobs/{job_name}/run")
async def run_job(request: Request, job_name: str) -> dict[str, Any]:
    run = get_scheduler(request).run_job_now(job_name)
    if not run:
        raise HTTPException(status_code=404, detail="Not found")
    return run


@router.get("/job-runs")
async def list_job_runs(
    request: Request,
    job_name: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    return get_scheduler(request).list_job_runs(job_name, limit)
