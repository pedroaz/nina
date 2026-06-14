# Known Good Tools

Use these first in this repo.

## Search and Read

- `rg -n "pattern" -S .` - broad text search.
- `rg --files` - list files.
- `sed -n "START,ENDp" FILE` - read targeted file ranges.
- `ls -la` - inspect directories, including hidden ones.

## Git Checks

- `git status --short` - inspect dirty state.
- `git diff --check` - catch whitespace and patch issues.
- `git diff -- FILE...` - review focused diffs.

## Edits

- `perl -0pi -e "s/OLD/NEW/s" FILE` - reliable small in-place replacement.

## Build And Install

- `make -n build` - verify the local build recipe expansion without installing anything. Needed escalation in this environment because the sandbox wrapper blocked plain execution.
- `NINA_INSTALL_ROOT=/tmp/nina-build-test NINA_LAUNCHER_DIR=/tmp/nina-launcher make build` - end-to-end build/install verification in temporary paths, avoiding the real home install. Needed escalation in this environment.
- `/tmp/nina-launcher/nina version` - verify the generated launcher starts the packaged CLI after a temp build. Needed escalation in this environment.

## Diagnostics

- `which -a nina` - list `nina` commands visible on PATH. Needed escalation in this environment.
- `ls -l ~/.local/bin/nina ~/.nina/bin/nina ~/.nina/bin/nina-tui 2>/dev/null || true` - inspect the expected local launcher and TUI binary locations. Needed escalation in this environment.
- `make doctor` - run Nina's local PATH/launcher diagnostic. Uses `python3` directly so the diagnostic does not prepend `.venv/bin` through `uv run`. Needed escalation in this environment.

## Tests

- `uv run pytest tests/unit/test_cli_commands.py` - focused CLI verification. Needed escalation in this environment because the sandbox wrapper blocked plain execution.

## Update Rule

Add a new bullet here when a command works in this repo and is worth reusing later:
- exact command
- purpose
- whether it needed escalation
- any caveat that matters for future sessions
