"""Tests for the Nina Codex plugin lifecycle hook action mapping."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_hook() -> ModuleType:
    hook_path = (
        Path(__file__).resolve().parents[2]
        / "nina-codex-plugin"
        / "files"
        / "nina-codex"
        / "hooks"
        / "nina_hook.py"
    )
    spec = importlib.util.spec_from_file_location("nina_codex_hook", hook_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


HOOK = _load_hook()


def test_started_action_marks_task_working() -> None:
    assert HOOK._started_actions() == {"setStatus": "working"}


def test_coding_done_defaults_to_done_and_review_followup() -> None:
    assert HOOK._done_actions("coding", None) == {
        "setStatus": "idle",
        "setTaskType": "done",
        "createNextTaskType": "reviewing",
    }
    assert HOOK._done_actions("coding", "Outcome: something unexpected") == {
        "setStatus": "idle",
        "setTaskType": "done",
        "createNextTaskType": "reviewing",
    }


def test_coding_done_blocks_partial_or_blocked_reports() -> None:
    for message in (
        "Outcome: blocked\nBlockers: missing access",
        "Outcome: partially completed\nBlockers: tests failing",
    ):
        assert HOOK._done_actions("coding", message) == {"setStatus": "idle", "setTaskType": "blocked"}


def test_reviewing_done_marks_done_for_approved_or_completed_reports() -> None:
    assert HOOK._done_actions("reviewing", "Decision: approved") == {
        "setStatus": "idle",
        "setTaskType": "done",
    }
    assert HOOK._done_actions("reviewing", "Outcome: completed") == {
        "setStatus": "idle",
        "setTaskType": "done",
    }


def test_reviewing_done_blocks_rejected_partial_or_missing_reports() -> None:
    assert HOOK._done_actions("reviewing", None) == {"setStatus": "idle", "setTaskType": "blocked"}
    assert HOOK._done_actions("reviewing", "Outcome: completed\nDecision: rejected") == {
        "setStatus": "idle",
        "setTaskType": "blocked",
    }
    assert HOOK._done_actions("reviewing", "Outcome: partially completed") == {
        "setStatus": "idle",
        "setTaskType": "blocked",
    }
