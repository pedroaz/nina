#!/usr/bin/env python3
"""Codex hook dispatcher for Nina lifecycle events."""

from __future__ import annotations

import datetime as _dt
import json
import os
import sys
import urllib.error
import urllib.request


def _hook_response() -> None:
    print(json.dumps({"continue": True}))


def _read_hook_input() -> dict:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return {}
        value = json.loads(raw)
        return value if isinstance(value, dict) else {}
    except Exception as exc:  # noqa: BLE001 - hook must not fail Codex
        print(f"nina-codex hook: failed to parse hook input: {exc}", file=sys.stderr)
        return {}


def _timeout_seconds() -> float:
    raw = os.getenv("NINA_HOOK_TIMEOUT_MS", "2000")
    try:
        return max(0.1, int(raw) / 1000.0)
    except ValueError:
        return 2.0


def _utc_now() -> str:
    return _dt.datetime.now(_dt.UTC).isoformat().replace("+00:00", "Z")


def _first_present(source: dict, keys: tuple[str, ...]):
    for key in keys:
        value = source.get(key)
        if value is not None:
            return value
    return None


def _report_value(message: str | None, label: str) -> str:
    if not message:
        return ""
    prefix = label.lower() + ":"
    for line in message.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith(prefix):
            return stripped.split(":", 1)[1].strip().lower()
    return ""


def _is_blocked_result(outcome: str, decision: str) -> bool:
    return outcome.startswith(("blocked", "partially")) or decision.startswith(
        ("blocked", "reject", "rejected", "denied")
    )


def _started_actions(pipeline_stage: str | None) -> dict:
    actions = {"setStatus": "working"}
    if pipeline_stage:
        actions["setPipelineStage"] = pipeline_stage
    return actions


def _done_actions(task_type: str | None, pipeline_stage: str | None, message: str | None) -> dict:
    outcome = _report_value(message, "Outcome")
    decision = _report_value(message, "Decision")
    blockers = _report_value(message, "Blockers")
    stage = (pipeline_stage or "").strip().lower()
    if not stage:
        stage = "created" if task_type == "coding" else "reviewing"

    if task_type == "reviewing" or stage == "reviewing":
        if outcome.startswith(("blocked", "partially")) or _is_blocked_result(outcome, decision):
            return {
                "setStatus": "idle",
                "setTaskType": "blocked",
                "setPipelineStage": "blocked",
                "setPipelineError": blockers or "Review blocked.",
            }
        if decision.startswith(("approved", "approve")) or outcome.startswith(
            ("completed", "complete", "done")
        ):
            return {"setStatus": "idle", "setPipelineStage": "done", "setTaskType": "done"}
        return {
            "setStatus": "idle",
            "setPipelineStage": "blocked",
            "setTaskType": "blocked",
            "setPipelineError": blockers or "Review did not return an approval.",
        }

    if stage == "created":
        if _is_blocked_result(outcome, decision):
            return {
                "setStatus": "idle",
                "setPipelineStage": "blocked",
                "setPipelineError": blockers or "Creation blocked.",
            }
        return {"setStatus": "idle", "setPipelineStage": "exploration"}

    if stage == "exploration":
        if _is_blocked_result(outcome, decision):
            return {
                "setStatus": "idle",
                "setPipelineStage": "blocked",
                "setPipelineError": blockers or "Exploration blocked.",
            }
        return {"setStatus": "idle", "setPipelineStage": "coding"}

    if stage == "coding":
        if _is_blocked_result(outcome, decision):
            return {
                "setStatus": "idle",
                "setPipelineStage": "blocked",
                "setPipelineError": blockers or "Coding blocked.",
            }
        return {"setStatus": "idle", "setPipelineStage": "testing"}

    if stage == "testing":
        if _is_blocked_result(outcome, decision):
            return {
                "setStatus": "idle",
                "setPipelineStage": "blocked",
                "setPipelineError": blockers or "Testing blocked.",
            }
        return {"setStatus": "idle", "setPipelineStage": "reviewing"}

    if stage == "blocked":
        if _is_blocked_result(outcome, decision):
            return {
                "setStatus": "idle",
                "setPipelineStage": "blocked",
                "setPipelineError": blockers or "Task remains blocked.",
            }
        return {"setStatus": "idle", "setPipelineStage": "exploration"}

    return {"setStatus": "idle"}


def main() -> int:
    event = sys.argv[1] if len(sys.argv) > 1 else "unknown"
    hook_input = _read_hook_input()

    task_id = os.getenv("NINA_TASK_ID")
    run_id = os.getenv("NINA_RUN_ID")
    task_type = os.getenv("NINA_TASK_TYPE")
    pipeline_stage = os.getenv("NINA_PIPELINE_STAGE")
    base_url = os.getenv("NINA_BASE_URL")
    token = os.getenv("NINA_TOKEN")

    if not task_id or not run_id or not base_url or not token:
        print(
            "nina-codex hook: missing NINA_TASK_ID, NINA_RUN_ID, NINA_BASE_URL, or NINA_TOKEN; skipping callback",
            file=sys.stderr,
        )
        _hook_response()
        return 0

    payload = {
        "version": 1,
        "event": event,
        "source": "codex-hook",
        "taskId": task_id,
        "runId": run_id,
        "sessionId": _first_present(hook_input, ("session_id", "sessionId")),
        "turnId": _first_present(hook_input, ("turn_id", "turnId")),
        "cwd": hook_input.get("cwd"),
        "taskType": task_type,
        "pipelineStage": pipeline_stage,
        "lastAssistantMessage": _first_present(
            hook_input,
            (
                "last_assistant_message",
                "lastAssistantMessage",
                "assistant_message",
                "assistantMessage",
            ),
        ),
        "sentAt": _utc_now(),
    }

    if event == "started":
        payload.update(_started_actions(pipeline_stage))
    elif event == "done":
        payload.update(
            _done_actions(task_type, pipeline_stage, payload.get("lastAssistantMessage"))
        )

    url = base_url.rstrip("/") + "/codex/events"
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "content-type": "application/json",
            "authorization": f"Bearer {token}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=_timeout_seconds()) as response:
            if response.status < 200 or response.status >= 300:
                print(f"nina-codex hook: Nina returned HTTP {response.status}", file=sys.stderr)
    except (OSError, urllib.error.URLError, urllib.error.HTTPError) as exc:
        print(f"nina-codex hook: failed to report {event} to Nina: {exc}", file=sys.stderr)

    _hook_response()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
