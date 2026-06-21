"""Classify a freshly-created task into one of the task_type buckets.

The classifier calls the configured LLM with a small structured prompt and
returns a `ClassifyResult` with the inferred type and a short rationale. We
validate the model output against the `TASK_TYPES` enum and fall back to
`"reminder"` (the safe no-agent default) when the LLM produces something we don't
recognise. The classifier is intentionally decoupled from the workflow
runner so it can be exercised directly in unit tests with a `FakeProvider`.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, cast

from nina_core.models.models import TASK_TYPES


CLASSIFY_PROMPT = (
    "You are a tiny classifier for a personal task manager. "
    "Given the task's title and description, return JSON of the form "
    '{"task_type": "<type>", "reason": "<one short sentence>"}.\n\n'
    f"Allowed task_type values: {', '.join(t for t in TASK_TYPES if t != 'unclassified')}.\n\n"
    "Guidelines:\n"
    "- reminder: a personal reminder or user-only action (e.g. message a colleague, buy milk, make a phone call).\n"
    "- research: an open-ended investigation the AI can answer by reading/writing notes.\n"
    "- coding: a development task — building, fixing, refactoring code in this repo.\n"
    "- reviewing: a code review task — checking an implementation and deciding whether it is approved.\n"
    "- blocked: the task is currently waiting on someone or something else.\n"
    "- done: the work is already complete.\n\n"
    "Return ONLY the JSON object, no prose, no markdown fence."
)


@dataclass
class ClassifyResult:
    task_type: str
    reason: str
    raw: str


def parse_classify_response(text: str) -> ClassifyResult:
    """Extract `{task_type, reason}` JSON from an LLM response.

    Tolerates a JSON object wrapped in a code fence and falls back to
    substring extraction when the model rambles. The first classifier-valid
    `task_type` from the `TASK_TYPES` enum wins.
    """

    candidate = _strip_code_fence(text)
    parsed = _try_load_json(candidate)
    if parsed is None:
        parsed = _try_load_json(_extract_json_object(candidate))
    if parsed is None:
        # Last resort: scan for any of the allowed values.
        for token in (t for t in TASK_TYPES if t != "unclassified"):
            if token in candidate:
                return ClassifyResult(task_type=token, reason="", raw=text)
        return ClassifyResult(task_type="reminder", reason=_trim_reason(text), raw=text)

    if not isinstance(parsed, dict):
        return ClassifyResult(task_type="reminder", reason="", raw=text)

    raw_type = cast(object, parsed.get("task_type"))
    reason = cast(object, parsed.get("reason"))
    if isinstance(raw_type, str) and raw_type in TASK_TYPES and raw_type != "unclassified":
        return ClassifyResult(
            task_type=raw_type,
            reason=_trim_reason(reason) if isinstance(reason, str) else "",
            raw=text,
        )
    return ClassifyResult(task_type="reminder", reason=_trim_reason(text), raw=text)


def _strip_code_fence(text: str) -> str:
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if fenced:
        return fenced.group(1)
    return text.strip()


def _extract_json_object(text: str) -> str:
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start : end + 1]
    return text


def _try_load_json(text: str) -> Any:
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return None


def _trim_reason(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", value).strip()
    if len(cleaned) > 280:
        cleaned = cleaned[:277] + "..."
    return cleaned
