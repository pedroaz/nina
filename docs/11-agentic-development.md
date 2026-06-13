# Agentic Development Spec

This project is expected to be built mostly by coding agents. The repository therefore needs a strong local validation harness: repeatable commands, isolated test data, fake external services, and clear acceptance gates for every feature.

The goal is not only to have tests. The goal is to make it easy for an agent to prove that a change works without guessing.

## Principles

- One command should validate the common path: `make check`.
- Every feature should have a small acceptance checklist in docs or tests.
- Tests must run against temporary config, temporary SQLite databases, and temporary Obsidian vaults.
- Tests must never use the real user vault, real home config, or real LLM credentials by default.
- LLM behavior must be tested with a fake provider unless a command explicitly opts into live provider tests.
- CLI and TUI should be tested through the daemon API, because that is the production path.
- Flaky tests are treated as broken tests.
- Long-running daemon state must be easy to start, stop, inspect, and reset.

## Required Make Targets

The implementation should add a root `Makefile` with these targets.

```makefile
make help              # list available commands
make install           # install Python and TUI dependencies
make format            # format all code
make lint              # static lint checks
make typecheck         # type checking
make test              # unit tests and fast integration tests
make test-unit         # pure unit tests
make test-integration  # API, DB, Obsidian, CLI integration tests
make test-e2e          # daemon plus CLI plus selected TUI flows
make check             # format check, lint, typecheck, tests
make smoke             # fast end-to-end local smoke test

make dev-init          # initialize isolated dev config and vault
make dev-reset         # delete isolated dev config, DB, and vault
make daemon-start      # start daemon using isolated dev config
make daemon-stop       # stop daemon using isolated dev config
make daemon-status     # check daemon health
make daemon-logs       # tail daemon logs
make cli ARGS=...      # run CLI against isolated dev daemon
make tui               # run TUI against isolated dev daemon
```

Recommended local paths for dev data:

```text
.tmp/nina-dev/config.yaml
.tmp/nina-dev/token
.tmp/nina-dev/nina.db
.tmp/nina-dev/vault/
.tmp/nina-dev/logs/daemon.log
.tmp/nina-dev/daemon.pid
```

The dev targets must not write to `~/.nina` unless explicitly configured.

## Command Behavior

`make dev-init`

- Creates `.tmp/nina-dev`.
- Writes a config that points to the temporary DB and vault.
- Uses a fake LLM provider by default.
- Runs migrations.
- Creates the vault folder structure.

`make daemon-start`

- Starts the daemon bound to `127.0.0.1` on a dev port, for example `8765`.
- Writes a PID file.
- Writes logs to `.tmp/nina-dev/logs/daemon.log`.
- Fails clearly if a daemon is already running.
- Waits for `/health` before returning success.

`make daemon-stop`

- Stops the daemon from the PID file or API shutdown endpoint.
- Succeeds if the daemon is already stopped.
- Does not delete dev data.

`make dev-reset`

- Stops the daemon if needed.
- Deletes `.tmp/nina-dev`.
- Recreates a clean environment if followed by `make dev-init`.

`make smoke`

Runs a short proof that the whole app loop works:

1. reset dev data.
2. initialize dev config.
3. start daemon.
4. assert `/health` is OK.
5. create a project through CLI.
6. create a task through CLI.
7. move the task on the kanban board.
8. reindex search.
9. search for the task.
10. run `summarize-last-day` with fake LLM.
11. assert a daily note exists.
12. stop daemon.

## Test Layers

### Unit Tests

Unit tests should not start the daemon or touch real files outside a temp directory.

Cover:

- config path resolution.
- ID generation.
- Markdown rendering.
- frontmatter update behavior.
- kanban position calculations.
- workflow step state transitions.
- fake LLM provider behavior.
- search text extraction.

### Integration Tests

Integration tests can use SQLite and temporary vaults.

Cover:

- migrations create the expected schema.
- project creation writes DB row and Markdown note.
- task creation writes DB row and Markdown note.
- task update refreshes frontmatter without deleting manual body edits.
- kanban moves are transactional.
- deleted notes move to `System/Deleted/`.
- reindex populates FTS tables.
- workflow run records steps and events.

### API Tests

API tests should instantiate the FastAPI app with a temporary config.

Cover:

- `/health`.
- auth required for protected routes.
- project CRUD.
- task CRUD.
- kanban move.
- search and reindex.
- workflow run creation.
- jobs list and run-now behavior.
- error response shape.

### CLI Tests

CLI tests should run commands through the installed console entrypoint or a close equivalent.

Cover:

- `nina init` is idempotent.
- `nina daemon status` reports health.
- `nina project create` returns an ID.
- `nina task create` returns an ID.
- `nina task move` changes kanban column.
- `nina search reindex` and `nina search <query>` work.
- `nina workflow run summarize-last-day` creates a run.
- `--json` returns parseable JSON for list/show commands.

CLI tests should check exit codes, stdout, stderr, and side effects.

### TUI Tests

TUI tests are harder, so V1 should make them practical rather than perfect.

Recommended strategy:

1. Keep TUI state management separate from rendering.
2. Unit test API client and state reducers.
3. Add a mock daemon fixture for TUI integration tests.
4. Add smoke-level terminal tests for the most important flows.

Required TUI validation for V1:

- TUI starts without crashing against the dev daemon.
- Dashboard renders after loading `/health` and board state.
- Kanban screen displays seeded tasks.
- Keyboard move action calls `POST /kanban/move`.
- Search screen sends query and displays results.
- Jobs screen displays job status.

If OpenTUI supports terminal snapshots, add golden snapshot tests for:

- empty kanban board.
- kanban board with one task in each column.
- search results.
- job list with running and completed jobs.

If terminal snapshots are not practical, implement a TUI test mode:

```text
nina-tui --test-script tests/fixtures/tui/kanban-move.json
```

The test script should drive key presses and export final observed state as JSON.

## Fake Services

### Fake LLM Provider

The fake provider is mandatory.

Behavior:

- returns deterministic responses.
- can be configured to fail.
- can be configured to stream chunks later.
- records request payloads.

Example config:

```yaml
llm:
  provider: fake
  model: fake-summary-v1
```

Example response for daily summary:

```text
Fake daily summary for 2026-06-13.
```

### Fake Obsidian Opener

Opening a note in Obsidian should be abstracted behind a command interface.

Tests should configure:

```yaml
obsidian:
  open_command: fake-open
```

The fake opener records requested paths instead of launching a GUI app.

## Fixtures

Test fixtures should live under `tests/fixtures/`.

Recommended fixtures:

```text
tests/fixtures/
  configs/
    minimal.yaml
    fake-llm.yaml
  vaults/
    empty/
    with-projects/
    with-daily-notes/
  markdown/
    task-note.md
    project-note.md
  tui/
    kanban-move.json
    search-query.json
```

Factories should create temporary projects, tasks, events, and workflow runs without depending on global state.

## Feature Acceptance Template

Every feature should include an acceptance block in the implementing PR or task note.

```markdown
## Acceptance

- [ ] Unit tests cover core logic.
- [ ] Integration tests cover SQLite and Obsidian side effects.
- [ ] API or CLI behavior is tested through the public interface.
- [ ] `make check` passes.
- [ ] `make smoke` passes if the feature touches daemon, CLI, DB, vault, workflow, or TUI behavior.
- [ ] Docs are updated when commands, config, API, or schema change.
```

## Phase Gates

### Phase 0 Gate

Required before more features:

- `make install`
- `make test`
- `make check`
- `nina --version`

### Phase 1 Gate

Required after config/init:

- `make dev-reset`
- `make dev-init`
- assert config file exists.
- assert DB file exists.
- assert vault folders exist.
- run `nina init` twice.

### Phase 3 Gate

Required after daemon foundation:

- `make daemon-start`
- `make daemon-status`
- unauthorized `/health` behavior documented.
- protected route rejects missing token.
- `make daemon-stop`

### Phase 5 Gate

Required after kanban:

- create five tasks.
- move tasks across all columns.
- reorder tasks within one column.
- assert positions are contiguous.
- assert Markdown frontmatter updates.

### Phase 8 Gate

Required after workflow and LLM:

- fake LLM daily summary succeeds.
- fake LLM failure creates failed interaction and failed workflow step.
- generated daily note is indexed.
- workflow run and step records are visible through API and CLI.

### Phase 10 Gate

Required after TUI:

- TUI starts against dev daemon.
- kanban screen loads.
- keyboard move updates daemon state.
- search screen returns a known result.
- job screen displays daily-summary.

## CI Expectations

Initial CI can run only local deterministic checks:

```text
make check
make smoke
```

Live LLM tests must be opt-in and excluded from normal CI.

Recommended opt-in command:

```text
make test-live-llm
```

This command should skip unless an explicit environment variable is set, for example:

```text
NINA_RUN_LIVE_LLM_TESTS=1
```

## Agent Workflow

A coding agent should follow this loop for every task:

1. Read the relevant docs.
2. Identify the smallest public behavior to implement.
3. Add or update tests first when practical.
4. Implement through the daemon/core boundary.
5. Run the narrowest relevant test command.
6. Run `make check` before final handoff.
7. Run `make smoke` for changes that affect daemon, CLI, DB, vault, workflow, scheduler, or TUI behavior.
8. Report commands run and any failures that remain.

## Debugging Requirements

The app should make failures inspectable:

- daemon logs in `.tmp/nina-dev/logs/daemon.log`.
- event records in SQLite.
- workflow step errors stored in DB.
- LLM interaction errors stored in DB.
- CLI errors include a stable error code when possible.
- API errors use the documented error shape.

## Non-Negotiable Safety Rules

- Tests must not use the real Obsidian vault.
- Tests must not use the real Nina config directory.
- Tests must not require live OpenAI credentials.
- Tests must not leave daemon processes running.
- Tests must not depend on wall-clock timing without generous timeouts.
- Tests must clean up temp directories or keep them under `.tmp/`.
