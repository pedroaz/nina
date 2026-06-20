from __future__ import annotations

from nina_core.tasks.classifier import parse_classify_response


def test_parse_pure_json_object() -> None:
    result = parse_classify_response('{"task_type": "coding", "reason": "refactor"}')
    assert result.task_type == "coding"
    assert result.reason == "refactor"


def test_parse_fenced_json() -> None:
    result = parse_classify_response('```json\n{"task_type": "reminder"}\n```')
    assert result.task_type == "reminder"


def test_parse_handles_rambling_output() -> None:
    text = (
        "Here is my decision: "
        '{"task_type": "research", "reason": "user wants a deep dive"} '
        "hope that helps!"
    )
    result = parse_classify_response(text)
    assert result.task_type == "research"
    assert "deep dive" in result.reason


def test_parse_falls_back_to_human_on_unknown_type() -> None:
    result = parse_classify_response('{"task_type": "transmogrify"}')
    assert result.task_type == "human"


def test_parse_finds_token_when_no_json() -> None:
    result = parse_classify_response("I think this is blocked by upstream.")
    assert result.task_type == "blocked"


def test_parse_returns_human_on_garbage() -> None:
    result = parse_classify_response("I have no idea what to do with this.")
    assert result.task_type == "human"


def test_parse_rejects_unclassified_as_answer() -> None:
    """`unclassified` is an inbox marker, not a valid classifier answer."""

    result = parse_classify_response('{"task_type": "unclassified"}')
    assert result.task_type == "human"


def test_reason_is_trimmed() -> None:
    long_reason = "x" * 500
    result = parse_classify_response(f'{{"task_type": "coding", "reason": "{long_reason}"}}')
    assert len(result.reason) <= 280
