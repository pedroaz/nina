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


def test_started_actions_marks_task_working() -> None:
    assert HOOK._started_actions(None) == {"setStatus": "working"}


def test_started_actions_preserves_pipeline_stage_when_available() -> None:
    assert HOOK._started_actions("exploration") == {
        "setStatus": "working",
        "setPipelineStage": "exploration",
    }


def test_created_done_moves_to_exploration_when_not_blocked() -> None:
    assert HOOK._done_actions("coding", "created", "Outcome: completed\n") == {
        "setStatus": "idle",
        "setPipelineStage": "exploration",
    }


def test_created_done_blocks_partial_or_blocked_outcomes() -> None:
    assert HOOK._done_actions(
        "coding",
        "created",
        "Outcome: blocked\nBlockers: missing context",
    ) == {
        "setStatus": "idle",
        "setPipelineStage": "blocked",
        "setPipelineError": "missing context",
    }
    assert HOOK._done_actions(
        "coding",
        "created",
        "Outcome: partially completed\nBlockers: no tests",
    ) == {
        "setStatus": "idle",
        "setPipelineStage": "blocked",
        "setPipelineError": "no tests",
    }


def test_exploration_done_prompts_coding_when_not_blocked() -> None:
    assert HOOK._done_actions("coding", "exploration", "Outcome: completed\n") == {
        "setStatus": "idle",
        "setPipelineStage": "coding",
    }


def test_exploration_done_blocks_partial_or_blocked_outcomes() -> None:
    assert HOOK._done_actions(
        "coding",
        "exploration",
        "Outcome: blocked\nBlockers: missing data",
    ) == {
        "setStatus": "idle",
        "setPipelineStage": "blocked",
        "setPipelineError": "missing data",
    }
    assert HOOK._done_actions(
        "coding",
        "exploration",
        "Outcome: partially completed\nBlockers: no tests",
    ) == {
        "setStatus": "idle",
        "setPipelineStage": "blocked",
        "setPipelineError": "no tests",
    }


def test_coding_done_moves_to_testing() -> None:
    assert HOOK._done_actions("coding", "coding", "Outcome: completed\n") == {
        "setStatus": "idle",
        "setPipelineStage": "testing",
    }


def test_testing_done_moves_to_reviewing() -> None:
    assert HOOK._done_actions("coding", "testing", "Outcome: completed\n") == {
        "setStatus": "idle",
        "setPipelineStage": "reviewing",
    }


def test_blocked_coding_rerun_moves_back_to_exploration_when_completed() -> None:
    assert HOOK._done_actions("coding", "blocked", "Outcome: completed\nBlockers: none") == {
        "setStatus": "idle",
        "setPipelineStage": "exploration",
    }


def test_reviewing_done_marks_approved_as_done() -> None:
    assert HOOK._done_actions(
        "reviewing",
        "reviewing",
        "Outcome: completed\nDecision: approved\n",
    ) == {
        "setStatus": "idle",
        "setTaskType": "done",
        "setPipelineStage": "done",
    }


def test_reviewing_done_marks_blocked_on_rejection_or_blockers() -> None:
    assert HOOK._done_actions(
        "reviewing",
        "reviewing",
        "Outcome: completed\nDecision: rejected\nBlockers: missing validation",
    ) == {
        "setStatus": "idle",
        "setPipelineStage": "blocked",
        "setTaskType": "blocked",
        "setPipelineError": "missing validation",
    }
