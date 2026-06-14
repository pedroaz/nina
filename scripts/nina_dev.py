#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def run(
    cmd: list[str], env: dict[str, str] | None = None, timeout: int = 30
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def with_config(config_dir: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["NINA_CONFIG_DIR"] = str(config_dir)
    return env


def require_config(config_dir: Path) -> None:
    missing = [
        path
        for path in [
            config_dir / "config.yaml",
            config_dir / "token",
            config_dir / "nina.db",
            config_dir / "vault",
        ]
        if not path.exists()
    ]
    if missing:
        paths = ", ".join(str(path) for path in missing)
        raise SystemExit(f"Config is not initialized. Missing: {paths}")


def read_token(config_dir: Path) -> str:
    token_path = config_dir / "token"
    if not token_path.exists():
        raise SystemExit(f"Missing token file: {token_path}")
    return token_path.read_text().strip()


def health(config_dir: Path, timeout: float = 2.0) -> dict[str, object]:
    token = read_token(config_dir)
    req = urllib.request.Request(
        "http://127.0.0.1:8765/health",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def wait_for_health(config_dir: Path, seconds: int = 10) -> dict[str, object]:
    deadline = time.monotonic() + seconds
    expected_vault = (config_dir / "vault").resolve()
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            data = health(config_dir)
            actual_vault = Path(str(data.get("vault_path", ""))).resolve()
            if actual_vault == expected_vault:
                return data
            last_error = RuntimeError(
                f"port 8765 is serving {actual_vault}, expected {expected_vault}"
            )
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            last_error = exc
        time.sleep(0.25)
    raise SystemExit(f"Daemon did not become healthy within {seconds}s: {last_error}")


def cmd_health(args: argparse.Namespace) -> int:
    config_dir = Path(args.config_dir)
    data = health(config_dir)
    expected_vault = (config_dir / "vault").resolve()
    actual_vault = Path(str(data.get("vault_path", ""))).resolve()
    print(f"Daemon health: {data.get('status')}")
    print(f"Vault: {data.get('vault_path')}")
    if actual_vault != expected_vault:
        print(f"Warning: daemon is not using expected temp vault {expected_vault}")
        return 1
    return 0


def cmd_reset(args: argparse.Namespace) -> int:
    config_dir = Path(args.config_dir)
    if config_dir.exists():
        shutil.rmtree(config_dir)
    print(f"Removed {config_dir}")
    return 0


def copy_config_tree(source: Path, dest: Path) -> Path | None:
    backup_path: Path | None = None
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        backup_path = dest.with_name(f"{dest.name}.backup-{stamp}")
        shutil.copytree(dest, backup_path, symlinks=True)
        shutil.rmtree(dest)
    shutil.copytree(source, dest, symlinks=True)
    return backup_path


def cmd_promote(args: argparse.Namespace) -> int:
    source = Path(args.source)
    dest = Path(args.dest).expanduser()
    require_config(source)
    if source.resolve() == dest.resolve():
        raise SystemExit("Source and destination are the same path; refusing to promote.")
    backup_path = copy_config_tree(source, dest)
    print(f"Promoted {source} -> {dest}")
    if backup_path:
        print(f"Previous real data backup: {backup_path}")
    print("Start real daemon with: nina daemon start")
    return 0


def cmd_smoke(args: argparse.Namespace) -> int:
    config_dir = Path(args.config_dir)
    env = with_config(config_dir)
    result_code = 0
    cleanup_code = 0

    run(["uv", "run", "nina", "daemon", "stop"], env=env)

    print(f"Initializing temp config at {config_dir}")
    init = run(["uv", "run", "nina", "init", "--force"], env=env)
    if init.returncode != 0:
        sys.stderr.write(init.stderr)
        return init.returncode

    print("Starting daemon")
    start = run(["uv", "run", "nina", "daemon", "start"], env=env)
    already_running = "already running" in (start.stdout + start.stderr).lower()
    if start.returncode != 0 and not already_running:
        sys.stderr.write(start.stderr)
        return start.returncode

    try:
        data = wait_for_health(config_dir)
        print(f"Health: {data.get('status')}")

        create = run(["uv", "run", "nina", "ticket", "create", "Smoke task"], env=env)
        if create.returncode != 0:
            sys.stderr.write(create.stderr)
            result_code = create.returncode
        else:
            print(create.stdout.strip())

        if result_code == 0:
            listing = run(["uv", "run", "nina", "ticket", "list"], env=env)
            if listing.returncode != 0:
                sys.stderr.write(listing.stderr)
                result_code = listing.returncode
            elif "Smoke task" not in listing.stdout:
                raise SystemExit("CLI smoke failed: created task was not listed")
            else:
                print("CLI task round trip: ok")

        if result_code == 0:
            tui_env = env.copy()
            tui_env["PATH"] = os.environ["PATH"]
            tui_check = subprocess.run(
                ["bun", "run", "check"],
                cwd=REPO_ROOT / "apps" / "tui",
                env=tui_env,
                text=True,
                capture_output=True,
                timeout=30,
                check=False,
            )
            if tui_check.returncode != 0:
                sys.stderr.write(tui_check.stdout)
                sys.stderr.write(tui_check.stderr)
                result_code = tui_check.returncode
            else:
                print("TUI typecheck: ok")
    finally:
        stop = run(["uv", "run", "nina", "daemon", "stop"], env=env)
        if stop.returncode != 0:
            cleanup_code = stop.returncode or 1
            if stop.stderr.strip():
                sys.stderr.write(stop.stderr)
            elif stop.stdout.strip():
                sys.stderr.write(stop.stdout)
        elif stop.stdout.strip():
            print(stop.stdout.strip())

    if cleanup_code != 0 and result_code == 0:
        return cleanup_code
    return result_code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Nina local development helper")
    sub = parser.add_subparsers(required=True)

    health_parser = sub.add_parser("health")
    health_parser.add_argument("--config-dir", default=".tmp/nina-dev")
    health_parser.set_defaults(func=cmd_health)

    reset_parser = sub.add_parser("reset")
    reset_parser.add_argument("--config-dir", default=".tmp/nina-dev")
    reset_parser.set_defaults(func=cmd_reset)

    promote_parser = sub.add_parser("promote")
    promote_parser.add_argument("--source", default=".tmp/nina-dev")
    promote_parser.add_argument("--dest", default="~/.nina/default")
    promote_parser.set_defaults(func=cmd_promote)

    smoke_parser = sub.add_parser("smoke")
    smoke_parser.add_argument("--config-dir", default=".tmp/nina-dev")
    smoke_parser.set_defaults(func=cmd_smoke)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
