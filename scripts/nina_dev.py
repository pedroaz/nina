#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from nina_core.config import ensure_vault_structure, load_effective_config
from nina_core.db import create_database
from nina_core.search.indexer import create_fts_table

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE = "default"
DEFAULT_RESEARCH_SMOKE_MODEL = "gpt-5.5"
DEFAULT_RESEARCH_SMOKE_TOPIC = "modern mobile authentication patterns"


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


def profile_config_dir(profile: str) -> Path:
    return Path.home() / ".nina" / profile


def with_profile(profile: str) -> dict[str, str]:
    env = os.environ.copy()
    env.pop("NINA_CONFIG_DIR", None)
    env["NINA_PROFILE"] = profile
    return env


def ensure_profile(profile: str, env: dict[str, str]) -> Path:
    config_dir = profile_config_dir(profile)
    config_path = config_dir / "config.yaml"
    if config_path.exists():
        init = run(["uv", "run", "nina", "init", "--profile", profile], env=env)
    else:
        print(f"Initializing Nina profile '{profile}' at {config_dir}")
        init = run(["uv", "run", "nina", "init", "--profile", profile], env=env)
    if init.returncode != 0:
        sys.stderr.write(init.stderr)
        raise SystemExit(init.returncode)
    config = load_effective_config(config_dir)
    ensure_vault_structure(Path(config.vault_path))
    if not Path(config.database_path).exists():
        create_database(config.database_path)
        create_fts_table(config.database_path)
    return config_dir


def require_config(config_dir: Path) -> None:
    config = load_effective_config(config_dir)
    missing = [
        path
        for path in [
            config_dir / "config.yaml",
            config_dir / "token",
            Path(config.database_path),
            Path(config.vault_path),
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


def daemon_url(config_dir: Path) -> str:
    config = load_effective_config(config_dir)
    return f"http://{config.daemon_host}:{config.daemon_port}"


def expected_vault(config_dir: Path) -> Path:
    return Path(load_effective_config(config_dir).vault_path).resolve()


def health(config_dir: Path, timeout: float = 2.0) -> dict[str, object]:
    token = read_token(config_dir)
    req = urllib.request.Request(
        f"{daemon_url(config_dir)}/health",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def wait_for_health(config_dir: Path, seconds: int = 10) -> dict[str, object]:
    deadline = time.monotonic() + seconds
    expected = expected_vault(config_dir)
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            data = health(config_dir)
            actual_vault = Path(str(data.get("vault_path", ""))).resolve()
            if actual_vault == expected:
                return data
            last_error = RuntimeError(
                f"{daemon_url(config_dir)} is serving {actual_vault}, expected {expected}"
            )
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            last_error = exc
        time.sleep(0.25)
    raise SystemExit(f"Daemon did not become healthy within {seconds}s: {last_error}")


def cmd_health(args: argparse.Namespace) -> int:
    config_dir = profile_config_dir(args.profile)
    require_config(config_dir)
    data = health(config_dir)
    expected = expected_vault(config_dir)
    actual_vault = Path(str(data.get("vault_path", ""))).resolve()
    print(f"Daemon health: {data.get('status')}")
    print(f"Vault: {data.get('vault_path')}")
    if actual_vault != expected:
        print(f"Warning: daemon is not using expected vault {expected}")
        return 1
    return 0


def cmd_reset(args: argparse.Namespace) -> int:
    profile = args.profile
    config_dir = profile_config_dir(profile)
    raise SystemExit(
        f"Refusing to delete default-profile data at {config_dir}. "
        "The dev harness no longer uses a temp config. Use `nina uninstall` "
        "or remove files manually if you really want to delete Nina data."
    )


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


def ensure_daemon_running(profile: str, env: dict[str, str], config_dir: Path) -> dict[str, object]:
    try:
        data = wait_for_health(config_dir, seconds=2)
        print("Daemon already healthy")
        return data
    except SystemExit:
        print("Starting daemon")
        start = run(["uv", "run", "nina", "daemon", "start", "--profile", profile], env=env)
        already_running = "already running" in (start.stdout + start.stderr).lower()
        if start.returncode != 0 and not already_running:
            sys.stderr.write(start.stderr)
            raise SystemExit(start.returncode) from None
        return wait_for_health(config_dir)


def cmd_smoke(args: argparse.Namespace) -> int:
    profile = args.profile
    env = with_profile(profile)
    config_dir = ensure_profile(profile, env)
    require_config(config_dir)
    result_code = 0
    smoke_ticket_id: str | None = None

    print(f"Using Nina profile '{profile}' at {config_dir}")

    try:
        data = ensure_daemon_running(profile, env, config_dir)
    except SystemExit as exc:
        return int(exc.code or 1)

    print(f"Health: {data.get('status')}")
    print(f"Vault: {data.get('vault_path')}")

    title = "Smoke task " + datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    create = run(
        ["uv", "run", "nina", "ticket", "create", title, "--no-classify"],
        env=env,
    )
    if create.returncode != 0:
        sys.stderr.write(create.stderr)
        result_code = create.returncode
    else:
        print(create.stdout.strip())
        match = re.search(r"Created ticket ([0-9a-f-]+)", create.stdout)
        if match:
            smoke_ticket_id = match.group(1)

    if result_code == 0:
        listing = run(["uv", "run", "nina", "ticket", "list"], env=env)
        if listing.returncode != 0:
            sys.stderr.write(listing.stderr)
            result_code = listing.returncode
        else:
            print("CLI ticket list: ok")

    if result_code == 0 and smoke_ticket_id:
        shown = run(["uv", "run", "nina", "ticket", "show", smoke_ticket_id], env=env)
        if shown.returncode != 0:
            sys.stderr.write(shown.stderr)
            result_code = shown.returncode
        elif title not in shown.stdout:
            sys.stderr.write("CLI smoke failed: created ticket detail did not match\n")
            result_code = 1
        else:
            print("CLI ticket round trip: ok")

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

    if smoke_ticket_id:
        delete = run(["uv", "run", "nina", "ticket", "delete", smoke_ticket_id], env=env)
        if delete.returncode == 0:
            print("Smoke ticket cleanup: ok")
        else:
            sys.stderr.write(delete.stderr or delete.stdout)
            if result_code == 0:
                result_code = delete.returncode or 1

    print(f"Daemon is running for profile '{profile}'.")
    return result_code


def cmd_research_smoke(args: argparse.Namespace) -> int:
    profile = args.profile
    env = with_profile(profile)
    config_dir = ensure_profile(profile, env)
    require_config(config_dir)

    print(f"Using Nina profile '{profile}' at {config_dir}")
    try:
        data = ensure_daemon_running(profile, env, config_dir)
    except SystemExit as exc:
        return int(exc.code or 1)
    print(f"Health: {data.get('status')}")
    print(f"Vault: {data.get('vault_path')}")

    timeout_seconds = float(args.timeout)
    config_commands = [
        ["uv", "run", "nina", "config", "llm-model", args.model],
        ["uv", "run", "nina", "config", "research-provider", "codex"],
        ["uv", "run", "nina", "config", "research-model", args.model],
        ["uv", "run", "nina", "config", "research-search-mode", args.search_mode],
        ["uv", "run", "nina", "config", "research-timeout", str(timeout_seconds)],
    ]
    for command in config_commands:
        configured = run(command, env=env)
        if configured.returncode != 0:
            sys.stderr.write(configured.stdout)
            sys.stderr.write(configured.stderr)
            return configured.returncode
        print(configured.stdout.strip())

    research_timeout = int(timeout_seconds) + 90
    print(f"Running live research via CLI: {args.topic}")
    researched = run(
        [
            "uv",
            "run",
            "nina",
            "research",
            "run",
            args.topic,
            "--search-mode",
            args.search_mode,
            "--timeout",
            str(research_timeout),
            "--json",
        ],
        env=env,
        timeout=research_timeout,
    )
    if researched.returncode != 0:
        sys.stderr.write(researched.stdout)
        sys.stderr.write(researched.stderr)
        return researched.returncode

    try:
        payload = json.loads(researched.stdout)
    except json.JSONDecodeError:
        sys.stderr.write(f"Research smoke failed: CLI did not return JSON:\n{researched.stdout}\n")
        return 1

    note_path = payload.get("note_path")
    if not isinstance(note_path, str) or not note_path:
        sys.stderr.write(f"Research smoke failed: missing note_path in payload: {payload}\n")
        return 1

    note_file = expected_vault(config_dir) / note_path
    if not note_file.exists():
        sys.stderr.write(f"Research smoke failed: note was not written at {note_file}\n")
        return 1

    summary = payload.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        sys.stderr.write("Research smoke failed: response did not include a summary\n")
        return 1

    sources = payload.get("sources") or []
    if not args.allow_empty_sources and args.search_mode == "live" and not sources:
        sys.stderr.write("Research smoke failed: live research returned no sources\n")
        return 1

    note_text = note_file.read_text(encoding="utf-8", errors="replace")
    if len(note_text.strip()) < 100:
        sys.stderr.write(f"Research smoke failed: note is unexpectedly short: {note_file}\n")
        return 1

    print("Research smoke: ok")
    print(f"Model: {args.model}")
    print(f"Search mode: {payload.get('search_mode')}")
    print(f"Note: {note_file}")
    print(f"Sources: {len(sources)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Nina local development helper")
    sub = parser.add_subparsers(required=True)

    health_parser = sub.add_parser("health")
    health_parser.add_argument("--profile", default=DEFAULT_PROFILE)
    health_parser.set_defaults(func=cmd_health)

    reset_parser = sub.add_parser("reset")
    reset_parser.add_argument("--profile", default=DEFAULT_PROFILE)
    reset_parser.set_defaults(func=cmd_reset)

    promote_parser = sub.add_parser("promote")
    promote_parser.add_argument("--source", default="~/.nina/default")
    promote_parser.add_argument("--dest", default="~/.nina/default")
    promote_parser.set_defaults(func=cmd_promote)

    smoke_parser = sub.add_parser("smoke")
    smoke_parser.add_argument("--profile", default=DEFAULT_PROFILE)
    smoke_parser.set_defaults(func=cmd_smoke)

    research_smoke_parser = sub.add_parser(
        "research-smoke",
        help="Run a live Codex research request through the CLI and verify the note output.",
    )
    research_smoke_parser.add_argument("--profile", default=DEFAULT_PROFILE)
    research_smoke_parser.add_argument(
        "--topic",
        default=os.environ.get("NINA_RESEARCH_SMOKE_TOPIC", DEFAULT_RESEARCH_SMOKE_TOPIC),
    )
    research_smoke_parser.add_argument(
        "--model",
        default=os.environ.get("NINA_RESEARCH_SMOKE_MODEL", DEFAULT_RESEARCH_SMOKE_MODEL),
    )
    research_smoke_parser.add_argument(
        "--search-mode",
        choices=["live", "cached", "disabled"],
        default=os.environ.get("NINA_RESEARCH_SMOKE_SEARCH_MODE", "live"),
    )
    research_smoke_parser.add_argument(
        "--timeout",
        type=float,
        default=float(os.environ.get("NINA_RESEARCH_SMOKE_TIMEOUT", "600")),
    )
    research_smoke_parser.add_argument("--allow-empty-sources", action="store_true")
    research_smoke_parser.set_defaults(func=cmd_research_smoke)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
