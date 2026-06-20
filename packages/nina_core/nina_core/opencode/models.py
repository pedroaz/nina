"""Pydantic models for the subset of the opencode server API Nina consumes.

We deliberately do not generate a full client from opencode's OpenAPI spec;
this is the four endpoints (health, project list, project/current, and a
handful of fields) Nina actually needs.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ProjectTime(BaseModel):
    created: int | None = None
    updated: int | None = None


class Project(BaseModel):
    id: str
    worktree: str
    vcs: str | None = None
    time: ProjectTime = Field(default_factory=ProjectTime)
    sandboxes: list[Any] = Field(default_factory=list)


class Health(BaseModel):
    healthy: bool
    version: str | None = None


class OpencodeStatus(BaseModel):
    """Snapshot returned by the Nina daemon's `/opencode/status` endpoint."""

    enabled: bool
    binary_installed: bool
    binary_path: str
    state: str
    version: str | None = None
    host: str
    port: int
    uptime_seconds: float | None = None
    pid: int | None = None
    last_error: str | None = None


# `state` values used in OpencodeStatus. Mirror the supervisor.
STATE_DISABLED = "disabled"
STATE_NOT_INSTALLED = "not_installed"
STATE_STARTING = "starting"
STATE_RUNNING = "running"
STATE_STOPPED = "stopped"
STATE_FAILED = "failed"
