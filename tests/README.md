# Test Strategy

Nina has three moving parts: daemon, CLI, and TUI. The test suite is split by failure mode instead of by package.

- `tests/unit`: fast command/utility tests. CLI tests mock HTTP and verify command-to-endpoint contracts.
- `tests/integration/test_daemon_api.py`: in-process daemon API tests using isolated SQLite and vault data. These cover task movement, job persistence, job execution, and job run observation without binding a real port.
- `tests/integration/test_cli_daemon_smoke.py`: optional real CLI + daemon test for agent/release verification. It binds `127.0.0.1:8765`, so it is skipped by default. Run it with `NINA_RUN_DAEMON_TESTS=1 uv run pytest tests/integration/test_cli_daemon_smoke.py`.

TUI verification is currently TypeScript-level plus smoke visibility through `make smoke`. Interactive keyboard flows should use OpenTUI's test renderer once the TUI has stateful actions beyond read-only screens.
