# Nina Codex Integration Reference

## Key Files

- `packages/nina_core/nina_core/codex/`: supervised Codex server/client/password logic.
- `apps/server/nina_server/routers/codex.py`: daemon endpoints for Codex status and lifecycle events.
- `apps/cli/nina_cli/codex_commands.py`: CLI surface for Codex-related operations.
- `nina-codex-plugin/files/nina-codex/hooks/nina_hook.py`: Codex lifecycle hook callback implementation.
- `nina-codex-plugin/files/nina-codex/skills/nina-task/SKILL.md`: task-run final report contract.
- `nina-codex-plugin/install.sh`: local plugin installation script.
- `nina-codex-plugin/README.md`: plugin replication and runtime contract.

## Runtime Contract

- Nina launches Codex with task environment variables such as `NINA_TASK_ID`, `NINA_RUN_ID`, `NINA_TASK_TYPE`, `NINA_BASE_URL`, and `NINA_TOKEN`.
- Codex hooks emit `started` and `done` lifecycle events to `POST /codex/events`.
- The daemon stores lifecycle events idempotently and owns task status transitions.
- The hook must not block Codex work if Nina is unavailable; failures should be logged and Codex should continue.
- The final assistant message is parsed by Nina for outcome and review decisions, so preserve the `nina-task` report shape.

## Status Semantics

- `started` marks a task's agent status as `working`.
- `done` marks agent status as `idle`.
- Completed coding runs should allow Nina to create a reviewing follow-up task.
- Blocked or partial coding runs should keep the task blocked rather than silently advancing.
- Reviewing runs need an explicit decision: approved, rejected, or blocked.

## Safety Rules

- Keep lifecycle transition decisions in Nina daemon/core code, not inside ad hoc shell wrappers.
- Do not expose the Codex password in logs, config output, README examples, or hook payload diagnostics.
- Avoid broad hook failures. The hook should exit successfully after best-effort reporting.
- Treat `--dangerously-bypass-*` flags as runner-only behavior for the controlled Nina environment.

## Validation

- Unit tests: `tests/unit/test_codex_client.py`, `tests/unit/test_codex_password.py`, `tests/unit/test_codex_supervisor.py`, and hook/plugin tests.
- Integration tests: `tests/integration/test_codex_api.py` and `tests/integration/test_codex_events_api.py`.
- Plugin install changes should be checked with `make codex-plugin-install` only when the local Codex environment is available.
