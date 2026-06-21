from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from nina_core.integrations.credentials import (
    delete_credentials,
    load_credentials,
    save_credentials,
)
from nina_core.integrations.registry import get_integration

from ..dependencies import _request_config_dir, get_integration_service
from ..schemas import IntegrationCredentialsUpdate


router = APIRouter()


@router.get("/integrations")
async def list_integrations_endpoint(request: Request) -> dict[str, Any]:
    return {"integrations": get_integration_service(request).list()}


@router.get("/integrations/{name}")
async def get_integration_endpoint(request: Request, name: str) -> Any:
    integration = get_integration_service(request).get(name)
    if integration is None:
        raise HTTPException(status_code=404, detail="Unknown integration")
    return integration


@router.post("/integrations/{name}/test")
async def test_integration_endpoint(request: Request, name: str) -> Any:
    if get_integration(name) is None:
        raise HTTPException(status_code=404, detail="Unknown integration")
    try:
        result = await get_integration_service(request).test(name)
    except KeyError:
        raise HTTPException(status_code=404, detail="Unknown integration")
    return result


@router.get("/integrations/{name}/tests")
async def list_integration_tests_endpoint(request: Request, name: str, limit: int = 10) -> Any:
    if get_integration(name) is None:
        raise HTTPException(status_code=404, detail="Unknown integration")
    return {"tests": get_integration_service(request).list_tests(name, limit=limit)}


@router.put("/integrations/{name}/credentials")
async def put_integration_credentials(
    request: Request,
    name: str,
    data: IntegrationCredentialsUpdate,
) -> dict[str, Any]:
    if get_integration(name) is None:
        raise HTTPException(status_code=404, detail="Unknown integration")
    if not isinstance(data.credentials, dict) or not data.credentials:
        raise HTTPException(status_code=400, detail="credentials must be a non-empty object")
    path = save_credentials(name, data.credentials, config_dir=_request_config_dir(request))
    return {"saved": True, "path": str(path)}


@router.delete("/integrations/{name}/credentials")
async def delete_integration_credentials(request: Request, name: str) -> dict[str, Any]:
    if get_integration(name) is None:
        raise HTTPException(status_code=404, detail="Unknown integration")
    deleted = delete_credentials(name, config_dir=_request_config_dir(request))
    return {"deleted": deleted}


@router.get("/integrations/{name}/credentials")
async def get_integration_credentials(request: Request, name: str) -> dict[str, Any]:
    """Return the shape of stored credentials without exposing secrets."""

    if get_integration(name) is None:
        raise HTTPException(status_code=404, detail="Unknown integration")
    creds = load_credentials(name, config_dir=_request_config_dir(request)) or {}
    return {
        "configured_fields": {key: bool(value) for key, value in creds.items()},
    }
