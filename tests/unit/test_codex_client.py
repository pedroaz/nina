"""Unit tests for the Codex CLI client."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest
from nina_core.codex.client import CodexClient, CodexError


def _fake_completed_process(
    command: list[str],
    *,
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(command, returncode, stdout=stdout, stderr=stderr)


@pytest.mark.asyncio
async def test_health_reads_version_from_codex_output(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_run(_self: CodexClient, command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return _fake_completed_process(command, returncode=0, stdout="codex 0.2.0\n")

    monkeypatch.setattr(CodexClient, "_run_subprocess", fake_run)
    client = CodexClient("127.0.0.1", 5555, "nina", "secret", binary_path="/usr/bin/codex")

    result = await client.health()

    assert result.healthy is True
    assert result.version == "codex 0.2.0"
    assert calls and calls[0][:2] == ["/usr/bin/codex", "--version"]


@pytest.mark.asyncio
async def test_health_raises_on_nonzero_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(_self: CodexClient, command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return _fake_completed_process(command, returncode=1, stdout="", stderr="boom")

    monkeypatch.setattr(CodexClient, "_run_subprocess", fake_run)

    client = CodexClient("127.0.0.1", 5555, "nina", "secret", binary_path="/usr/bin/codex")

    with pytest.raises(CodexError) as exc:
        await client.health()

    assert exc.value.status_code == 1
    assert exc.value.stdout == ""
    assert exc.value.stderr == "boom"
    assert "codex failed to report version" in str(exc.value)


@pytest.mark.asyncio
async def test_exec_returns_stdout_and_parses_json_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_run(_self: CodexClient, command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        payload = {"ok": True, "answer": "done"}
        return _fake_completed_process(
            command,
            returncode=0,
            stdout="\n".join(["working...", json.dumps(payload)]),
            stderr="",
        )

    monkeypatch.setattr(CodexClient, "_run_subprocess", fake_run)
    client = CodexClient("127.0.0.1", 5555, "nina", "secret", binary_path="/usr/bin/codex")

    result = await client.exec("say hello", json_mode=True)

    assert result.exit_code == 0
    assert result.stdout.startswith("working")
    assert result.json_payload == {"ok": True, "answer": "done"}
    assert "--skip-git-repo-check" in calls[0]
    assert "--cd" not in calls[0]


@pytest.mark.asyncio
async def test_list_projects_is_compat_stub() -> None:
    client = CodexClient("127.0.0.1", 5555, "nina", "secret", binary_path="/usr/bin/codex")
    projects = await client.list_projects()

    assert projects == []


@pytest.mark.asyncio
async def test_current_project_not_supported() -> None:
    client = CodexClient("127.0.0.1", 5555, "nina", "secret", binary_path="/usr/bin/codex")

    with pytest.raises(CodexError) as exc:
        await client.current_project()

    assert exc.value.status_code == 501
    assert "does not expose current project" in str(exc.value)


@pytest.mark.asyncio
async def test_exec_task_uses_noninteractive_flags_and_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[list[str], dict[str, object], float]] = []

    def fake_run(_self: CodexClient, command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append((command, kwargs, _self._timeout))
        output_path = command[command.index("--output-last-message") + 1]
        from pathlib import Path

        Path(output_path).write_text("Outcome: completed\n")
        return _fake_completed_process(command, returncode=0, stdout=json.dumps({"ok": True}) + "\n")

    monkeypatch.setattr(CodexClient, "_run_subprocess", fake_run)
    client = CodexClient("127.0.0.1", 5555, "nina", "secret", binary_path="/usr/bin/codex")

    result = await client.exec_task(
        "do work",
        cwd="/agent-test-folder",
        env={"NINA_TASK_TYPE": "coding", "NINA_TASK_ID": "task-1"},
        timeout=42,
    )

    assert result.last_message == "Outcome: completed\n"
    assert result.json_payload == {"ok": True}
    command, kwargs, timeout = calls[0]
    assert command[:2] == ["/usr/bin/codex", "exec"]
    assert "--cd" in command and command[command.index("--cd") + 1] == "/agent-test-folder"
    assert "--skip-git-repo-check" in command
    assert "--dangerously-bypass-approvals-and-sandbox" in command
    assert "--dangerously-bypass-hook-trust" in command
    assert "--json" in command
    assert kwargs["cwd"] == "/agent-test-folder"
    assert kwargs["env"]["NINA_TASK_TYPE"] == "coding"  # type: ignore[index]
    assert timeout == 42


@pytest.mark.asyncio
async def test_run_streams_stdout_and_stderr_to_log_file(tmp_path) -> None:  # type: ignore[no-untyped-def]
    log_path = tmp_path / "codex-task.log"
    script = "import sys; print('out line'); print('err line', file=sys.stderr)"
    client = CodexClient("127.0.0.1", 5555, "nina", "secret", binary_path=sys.executable)

    result = await client._run(["-c", script, "prompt text"], log_path=log_path)

    assert result.exit_code == 0
    assert result.stdout == "out line\n"
    assert result.stderr == "err line\n"
    logged = log_path.read_text()
    assert "$ " in logged
    assert "[stdout] out line" in logged
    assert "[stderr] err line" in logged
    assert "exit_code: 0" in logged
