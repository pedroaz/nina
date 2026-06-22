# Test Strategy

Nina has three moving parts: daemon, CLI, and desktop client. The test suite is split by failure mode instead of by package.

- `tests/unit`: fast command/utility tests. CLI tests mock HTTP and verify command-to-endpoint contracts.
- `tests/integration/test_daemon_api.py`: in-process daemon API tests using isolated SQLite and vault data. These cover task movement, job persistence, job execution, and job run observation without binding a real port.
- `tests/integration/test_cli_daemon_smoke.py`: optional real CLI + daemon test for agent/release verification. It binds `127.0.0.1:8765`, so it is skipped by default. Run it with `uv run pytest -m daemon_smoke tests/integration/test_cli_daemon_smoke.py`. The live Codex research case is additionally gated by `NINA_LIVE_CODEX_RESEARCH=1` because it uses network access and account quota.
- `make smoke-research`: manual live Codex research smoke against the selected Nina profile. It configures Codex research, runs `nina research run ... --json`, and verifies the written Obsidian note. Override with `RESEARCH_TOPIC=... CODEX_MODEL=... make smoke-research`.

Desktop verification lives under the GPUI client and runs through `make desktop-check`.
