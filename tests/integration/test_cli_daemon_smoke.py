from __future__ import annotations

import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.daemon_smoke]


def run_cli(
    repo_root: Path,
    config_dir: Path,
    args: list[str],
    *,
    timeout: int = 30,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["NINA_CONFIG_DIR"] = str(config_dir)
    return subprocess.run(
        ["uv", "run", "nina", *args],
        cwd=repo_root,
        env=env,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def wait_for_daemon(repo_root: Path, config_dir: Path) -> None:
    token = (config_dir / "token").read_text().strip()
    expected_vault = (config_dir / "vault").resolve()
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            req = urllib.request.Request(
                "http://127.0.0.1:8765/health",
                headers={"Authorization": f"Bearer {token}"},
            )
            with urllib.request.urlopen(req, timeout=2) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            if Path(data["vault_path"]).resolve() == expected_vault:
                return
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            pass
        time.sleep(0.25)
    log_path = config_dir / "logs" / "daemon.log"
    log = log_path.read_text() if log_path.exists() else ""
    raise AssertionError(f"daemon did not become healthy; log:\n{log}")


def _configure_codex_research(
    repo_root: Path,
    config_dir: Path,
    *,
    model: str,
    timeout_seconds: int,
) -> None:
    commands = [
        ["config", "llm-model", model],
        ["config", "research-provider", "codex"],
        ["config", "research-model", model],
        ["config", "research-search-mode", "live"],
        ["config", "research-timeout", str(timeout_seconds)],
    ]
    for command in commands:
        result = run_cli(repo_root, config_dir, command)
        assert result.returncode == 0, result.stderr or result.stdout


def test_real_cli_daemon_task_and_job_flow(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    config_dir = tmp_path / "nina-cli-daemon"

    init = run_cli(repo_root, config_dir, ["init", "--force", "--vault", str(config_dir / "vault")])
    assert init.returncode == 0, init.stderr

    start = run_cli(repo_root, config_dir, ["daemon", "start"])
    assert start.returncode == 0, start.stderr
    try:
        wait_for_daemon(repo_root, config_dir)

        created = run_cli(repo_root, config_dir, ["task", "create", "CLI daemon task"])
        assert created.returncode == 0, created.stderr
        match = re.search(r"Created task ([0-9a-f-]+)", created.stdout)
        assert match, created.stdout
        task_id = match.group(1)

        typed = run_cli(repo_root, config_dir, ["task", "type", task_id, "coding"])
        assert typed.returncode == 0, typed.stderr
        shown = run_cli(repo_root, config_dir, ["task", "show", task_id])
        assert "Type: coding" in shown.stdout

        job = run_cli(
            repo_root,
            config_dir,
            [
                "job",
                "create",
                "cli-daemon-summary",
                "--schedule",
                "*/15 * * * *",
                "--workflow",
                "summarize-last-day",
            ],
        )
        assert job.returncode == 0, job.stderr
        run = run_cli(repo_root, config_dir, ["job", "run", "cli-daemon-summary"])
        assert run.returncode == 0, run.stderr
        runs = run_cli(repo_root, config_dir, ["job", "runs", "--name", "cli-daemon-summary"])
        assert runs.returncode == 0, runs.stderr
        assert "completed" in runs.stdout
    finally:
        run_cli(repo_root, config_dir, ["daemon", "stop"])


def test_real_cli_daemon_live_research_flow(tmp_path: Path) -> None:
    if os.environ.get("NINA_LIVE_CODEX_RESEARCH") != "1":
        pytest.skip("set NINA_LIVE_CODEX_RESEARCH=1 to spend a real Codex research call")

    repo_root = Path(__file__).resolve().parents[2]
    config_dir = tmp_path / "nina-cli-research-daemon"
    model = os.environ.get("NINA_LIVE_CODEX_MODEL", "gpt-5.5")
    topic = os.environ.get("NINA_LIVE_CODEX_TOPIC", "modern mobile authentication patterns")
    timeout_seconds = int(os.environ.get("NINA_LIVE_CODEX_TIMEOUT", "600"))

    init = run_cli(repo_root, config_dir, ["init", "--force", "--vault", str(config_dir / "vault")])
    assert init.returncode == 0, init.stderr

    start = run_cli(repo_root, config_dir, ["daemon", "start"])
    assert start.returncode == 0, start.stderr
    try:
        wait_for_daemon(repo_root, config_dir)
        _configure_codex_research(
            repo_root,
            config_dir,
            model=model,
            timeout_seconds=timeout_seconds,
        )

        researched = run_cli(
            repo_root,
            config_dir,
            [
                "research",
                "run",
                topic,
                "--search-mode",
                "live",
                "--timeout",
                str(timeout_seconds + 90),
                "--json",
            ],
            timeout=timeout_seconds + 90,
        )
        assert researched.returncode == 0, researched.stderr or researched.stdout

        payload = json.loads(researched.stdout)
        assert payload["status"] == "completed"
        assert payload["search_mode"] == "live"
        assert payload["summary"].strip()
        assert payload["sources"], payload

        note_path = config_dir / "vault" / payload["note_path"]
        assert note_path.exists()
        assert len(note_path.read_text().strip()) > 100
    finally:
        run_cli(repo_root, config_dir, ["daemon", "stop"])
