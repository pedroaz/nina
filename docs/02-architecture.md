# Architecture

## Runtime Model

Nina has three user-facing processes:

```text
nina daemon
  Owns SQLite, Obsidian writes, scheduler, workflow execution, LLM calls, logs.

nina CLI
  Sends commands to the daemon API. Can start the daemon if it is not running.

Nina TUI
  Interactive OpenTUI application. Talks to the daemon API.
```

Only the daemon should mutate persistent state. This avoids split-brain bugs where CLI, TUI, and background jobs all write to the database or vault independently.

## Local API

The daemon exposes a local HTTP API:

- Bind address: `127.0.0.1`.
- Default port: `8765`.
- Transport: REST for commands and reads, Server-Sent Events for logs/streaming updates.
- Security: local bearer token stored in the Nina config directory.

Even for a single-user app, the token prevents accidental writes from unrelated local processes or browser-origin requests. The token is not a multi-user auth system.

## Monorepo Layout

Exact structure can evolve, but the implementation should start with this shape:

```text
nina-app/
  apps/
    server/              # Python daemon entrypoint
    cli/                 # Python CLI entrypoint
    tui/                 # OpenTUI client project
  packages/
    nina_core/           # domain services, config, models, workflows
  migrations/            # database migrations
  docs/
  tests/
  pyproject.toml
  uv.lock
```

If OpenTUI requires TypeScript or another runtime, `apps/tui` may use that runtime. Business logic must remain in the Python daemon/core. The TUI is a client only.

## Python Stack

Recommended:

- `uv` for dependency management and execution.
- FastAPI for the daemon API.
- SQLAlchemy 2.x for database access.
- Alembic for migrations.
- Pydantic for API/config schemas.
- Typer for CLI.
- APScheduler for in-process scheduling.
- SQLite with FTS5 for runtime and search.

## Module Boundaries

`nina_core.config`
: Load config, resolve paths, manage local token.

`nina_core.db`
: SQLAlchemy engine/session setup and migrations integration.

`nina_core.projects`
: Project CRUD and project note integration.

`nina_core.tasks`
: Task CRUD, kanban state, positions, and note mirroring.

`nina_core.obsidian`
: Vault initialization, Markdown rendering, file writes, open-in-Obsidian commands.

`nina_core.search`
: Markdown indexing and SQLite FTS queries.

`nina_core.llm`
: Provider interface, OpenAI provider, prompt/output logging.

`nina_core.workflows`
: Python workflow runner, workflow steps, retries, status.

`nina_core.scheduler`
: Scheduled job definitions and trigger wiring.

`nina_core.events`
: Append-only operational event log used by TUI and debugging.

## Process Responsibilities

Daemon:

- Applies migrations.
- Loads config.
- Ensures vault structure exists.
- Owns database sessions.
- Runs API server.
- Runs scheduler.
- Runs workflows.
- Emits events/logs.

CLI:

- Resolves active config.
- Starts daemon when needed for local commands.
- Calls API endpoints.
- Prints compact output.
- Supports scripting with JSON output.

TUI:

- Reads dashboard state.
- Manages kanban with keyboard interactions.
- Shows job/workflow logs.
- Shows search results.
- Streams live log updates from SSE.

## Failure Principles

- Failed Obsidian writes must fail the whole command and leave a visible event.
- Failed LLM calls must create a failed workflow step with the request metadata, not silently disappear.
- Kanban position updates must be transactional.
- Long-running workflows must record step status before and after each step.
- The daemon must be restartable without corrupting the database or vault.
