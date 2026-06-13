# Implementation Backlog

This backlog is ordered so an LLM coding agent can execute it from an empty repository.

## Phase 0: Repository Foundation

1. Create Python monorepo skeleton.
2. Add `pyproject.toml` using `uv`.
3. Add packages/apps directories:
   - `packages/nina_core`
   - `apps/server`
   - `apps/cli`
   - `apps/tui`
4. Add lint/type/test tooling.
5. Add root `Makefile` targets from [11-agentic-development.md](11-agentic-development.md).
6. Add isolated `.tmp/nina-dev` dev harness.
7. Add basic test command.
8. Add development README with run commands.

Acceptance:

- `uv sync` works.
- `make help` lists development commands.
- `make test` runs, even if minimal.
- `make check` runs the available validation stack.
- CLI entrypoint can print version.

## Phase 1: Config And Initialization

1. Implement config directory resolution.
2. Implement default config file.
3. Implement local API token generation.
4. Implement `nina init`.
5. Create vault folder structure.
6. Create SQLite database path.

Acceptance:

- `nina init` creates config, DB, token, and vault folders.
- running it twice is safe.

## Phase 2: Database And Migrations

1. Add SQLAlchemy models.
2. Add Alembic.
3. Create initial migration from [04-database-schema.md](04-database-schema.md).
4. Seed kanban columns.
5. Add repository/service layer tests.

Acceptance:

- migration creates all V1 tables.
- default columns exist.

## Phase 3: Daemon API Foundation

1. Create FastAPI app.
2. Add `/health`.
3. Add local bearer token middleware.
4. Add daemon start command.
5. Add event logging service.

Acceptance:

- daemon starts on `127.0.0.1:8765`.
- CLI can call `/health`.
- unauthorized requests fail.

## Phase 4: Projects And Tasks

1. Implement project CRUD service.
2. Implement task CRUD service.
3. Implement project/task note rendering.
4. Implement Obsidian file writes.
5. Add API endpoints.
6. Add CLI commands.

Acceptance:

- creating a project creates a DB row and Markdown note.
- creating a task creates a DB row and Markdown note.
- updating status updates DB and frontmatter.

## Phase 5: Kanban

1. Implement kanban board read model.
2. Implement transactional move operation.
3. Add `/kanban` and `/kanban/move`.
4. Add CLI kanban commands.
5. Add tests for position updates.

Acceptance:

- tasks can move between columns.
- positions remain contiguous and deterministic.

## Phase 6: Search And Indexing

1. Implement Markdown scanner.
2. Implement simple frontmatter/body extraction.
3. Implement note table updates.
4. Implement FTS indexing.
5. Add search API.
6. Add CLI search commands.
7. Add manual reindex command.

Acceptance:

- `nina search reindex` indexes the vault.
- `nina search "query"` returns matching notes.

## Phase 7: LLM Provider

1. Add provider interface.
2. Add OpenAI provider.
3. Add config loading for provider/model/key.
4. Add LLM interaction logging.
5. Add manual test endpoint/CLI command.

Acceptance:

- `nina llm test "..."` creates an interaction log.
- failures are stored and visible.

## Phase 8: Workflows

1. Add workflow registry.
2. Add workflow run/step persistence.
3. Add retry handling.
4. Implement `summarize-last-day`.
5. Write daily summary note.
6. Reindex generated note.

Acceptance:

- `nina workflow run summarize-last-day` creates a workflow run.
- a daily note appears in Obsidian.
- LLM prompt/output are logged.

## Phase 9: Scheduler

1. Add APScheduler to daemon.
2. Load scheduled jobs from DB.
3. Seed `daily-summary`.
4. Add job API and CLI commands.
5. Emit job events.

Acceptance:

- daily summary can be enabled/disabled.
- manual run now works.
- job runs are visible.

## Phase 10: TUI

1. Validate OpenTUI project setup.
2. Create TUI shell/navigation.
3. Add API client.
4. Build Dashboard.
5. Build Kanban screen.
6. Build Search screen.
7. Build Jobs screen.
8. Build LLM Logs screen.
9. Add SSE event stream integration.

Acceptance:

- TUI can display and move kanban tasks.
- TUI can search and open notes.
- TUI shows job/workflow progress.

## Phase 11: Packaging And Daily Use

1. Add daemon lifecycle commands.
2. Add Linux service example.
3. Add developer scripts.
4. Add smoke test script.
5. Document install/run flow.

Acceptance:

- Nina can be initialized, daemonized, used from CLI, and opened in TUI on Linux.

## Later Work

- Multiple profiles.
- OpenCode integration.
- GitHub plugin.
- Jira plugin.
- Meeting transcription.
- Research workflow.
- Semantic search.
- File watcher indexing.
- Hard delete support.
- Backup/export/import.
