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

pytestmark = pytest.mark.integration


def run_cli(repo_root: Path, config_dir: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["NINA_CONFIG_DIR"] = str(config_dir)
    return subprocess.run(
        ["uv", "run", "nina", *args],
        cwd=repo_root,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
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


@pytest.mark.skipif(
    os.environ.get("NINA_RUN_DAEMON_TESTS") != "1",
    reason="set NINA_RUN_DAEMON_TESTS=1 to run the real CLI+daemon smoke test",
)
def test_real_cli_daemon_task_and_job_flow(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    config_dir = tmp_path / "nina-cli-daemon"

    init = run_cli(repo_root, config_dir, ["init", "--force"])
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

        moved = run_cli(repo_root, config_dir, ["task", "move", task_id, "--column", "Doing"])
        assert moved.returncode == 0, moved.stderr
        shown = run_cli(repo_root, config_dir, ["task", "show", task_id])
        assert "Status: doing" in shown.stdout
        assert "Column: Doing" in shown.stdout

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
