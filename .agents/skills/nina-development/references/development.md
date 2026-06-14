# Nina Development Reference

## Validation Priorities
- One command should validate the common path: `make check`.
- Tests should use temp config, temp SQLite, temp vaults, and fake services by default.
- CLI and TUI should be tested through the daemon API.
- Flaky tests are broken tests.

## Make Targets
- `make help`
- `make build`
- `make doctor`
- `make format`
- `make lint`
- `make typecheck`
- `make test`
- `make test-unit`
- `make test-integration`
- `make check`
- `make smoke`
- `make dev-init`
- `make dev-reset`
- `make dev`
- `make dev-start`
- `make dev-stop`
- `make dev-status`
- `make dev-logs`
- `make cli ARGS=...`
- `make tui`
- `make promote`

## Smoke Path
1. Stop any leftover temp daemon.
2. Initialize temp config.
3. Start daemon.
4. Assert `/health` is OK for the temp vault.
5. Create a task through the CLI.
6. List tasks through the CLI.
7. Verify the TUI package typechecks.
8. Stop daemon.

## Backlog Order
- Foundation.
- Config and initialization.
- Database and migrations.
- Daemon API.
- Projects and tasks.
- Kanban.
- Search and indexing.
- LLM provider.
- Workflows.
- Scheduler.
- TUI.
- Packaging and daily use.

## Open Questions to Keep in Mind
- OpenTUI package/runtime details.
- OpenAI vs Codex auth path.
- Delete semantics.
- Task field scope.
- Future profile system.
- Best Linux command for opening Obsidian.
