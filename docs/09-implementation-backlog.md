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

- migration creates all initial tables.
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
- Driving opencode sessions from task `run` (sending a task as a prompt in
  its worktree, streaming events back to the TUI). The supervisor, schema,
  and config plumbing already exist; this is the "second cut" on top of
  Phase 13.
- GitHub plugin.
- Jira plugin.
- Hard delete support.
- Backup/export/import.
- `nina meeting import` for Teams-native recordings and other existing audio files.
- macOS BlackHole and Windows native WASAPI loopback.
- `nina meeting compact` to transcode WAV to opus.
- Speaker diarization.

## Tool-Calling Chat And Agent

The chat and agent features use a shared LLM tool loop. See
[`docs/12-llm-tools.md`](12-llm-tools.md) for the full design.

12. Add `nina_core/llm/tools.py` with `ToolSpec`, `ToolContext`, `ToolRegistry`.
13. Extend `LLMRequest` / `LLMResponse` with `messages`, `tools`, `tool_choice`, `tool_calls`, `finish_reason`.
14. Update `CodexAuthProvider` and `OpenAIProvider` to translate tool calls; extend `FakeProvider` for tests.
15. Register the read tool set: `obsidian_search`, `obsidian_get_note`, `obsidian_list_notes`, `kanban_get`, `tickets_*`, `projects_*`, `jobs_*`, `job_runs`, `llm_logs`.
16. Register the write tool set: `tickets_*`, `projects_*`, `notes_*`, `research_run`, `workflows_run`, `jobs_*`, `search_reindex`, `obsidian_open`.
17. Refactor `SessionService._send_chat` and `_send_agent` to a shared `_run_tool_loop` that carries the last N messages.
18. Add `POST /sessions/{id}/cancel` and `POST /sessions/{id}/clear-cancel`; honor the flag between tool-loop iterations.
19. Add `GET /notes`, `GET /notes/{path:path}`, `POST /notes`, `PATCH /notes/{path:path}` with vault-path safety.
20. Add `nina note list/show/create/append/update/open` CLI subcommands.
21. TUI: render tool and source cards; support `@path/to/note.md` mentions in chat input; bind `Ctrl+.` to cancel.

## Semantic Search And Live Indexing

22. Add `note_embeddings(note_id, path, title, nina_type, model, dim, embedding BLOB, ...)` to the schema.
23. Add `nina_core/search/embeddings.py` with `FastembedEmbeddingService`, `FakeEmbeddingService`, and `OpenAIEmbeddingService`.
24. Wire `obsidian_semantic_search` and `obsidian_hybrid_search` (RRF) tools into the default registry.
25. Embed new/changed notes during `index_notes` and on note writes via `NoteService`.
26. Add `nina search reindex-embeddings` and the `reindex-vault` scheduled workflow as a backstop.
27. Add `nina_core/search/watcher.py` using `watchdog`; start in the daemon lifespan; debounce per-path; skip refused prefixes.
28. Expose `search.live_indexing: bool` and `search.reindex_cron: str` in `NinaConfig`; show in the TUI Settings tab.

## Phase 12: Meetings

1. Add the `Meeting` SQLAlchemy model and an Alembic migration for the `meetings` table (id, title, status, source, device_name, started_at, ended_at, duration_seconds, audio_path, audio_size_bytes, audio_format, sample_rate, channels, transcript_path, summary_path, workflow_run_id, error, timestamps).
2. Add `Meetings/` to `ensure_vault_structure` and a `create_meeting_note` helper in `ObsidianService`.
3. Add `MeetingService` in `nina_core/meetings/service.py` with `start`, `stop`, `list`, `get`, `delete` (soft).
4. Add `nina_core/meetings/recorder.py` with a small `AudioSource` protocol, `SoundcardBackend` (cross-platform mic + system loopback via the `soundcard` library), `MacosProcessTapSource` (macOS 14.4+ system audio via Core Audio Process Tap, no BlackHole), `AlignedMixer` (frame-aligned soxr resampled mixer for `--source mixed`), and `NullAudioSource` (tests/CI).
5. Add the `transcribe-meeting` and `summarize-meeting` workflows in `WorkflowRunner` and a `TranscriptionProvider` interface in `nina_core/llm/transcription.py` (default: `FasterWhisperProvider`, plus `NullTranscriptionProvider` for tests).
6. Add `nina_core/config/transcription.py` (`TranscriptionConfig`) and the `meetings.*` block; expose both in the TUI Settings page and `nina config` subcommands.
7. Add the `/meetings` REST endpoints in `nina_server/app.py` and the `nina meeting ...` subcommands in `apps/cli/nina_cli/meeting_commands.py` (alias `mt`).
8. Add the **Meetings** TUI page in `apps/tui/src/main.ts`, wired to the daemon REST + SSE.
9. Tests: unit for `MeetingService`, recorder, transcription, and workflows; integration for the API + Obsidian; smoke target that records a short fixture and runs both workflows.

## Provider Pricing

29. Add `nina_core/pricing/` with pydantic models, JSON cache, fetcher, and per-provider parsers using `selectolax`. Cache lives at `$NINA_CONFIG_DIR/provider_pricing.json`.
30. Add `nina providers`, `nina providers list`, `nina providers show <substring>`, and `nina providers refresh [--provider ...] [--source <provider>:<path>]`. Empty cache prints a hint to run `refresh`; the row matching `config.llm.model` is highlighted in the table.
31. Support the Anthropic pricing page (`https://platform.claude.com/docs/en/about-claude/pricing`) and the OpenAI platform pricing page (`https://platform.openai.com/docs/pricing`). Parsers extract model, input, output, and cache read prices in USD per 1M tokens.

## Phase 13: opencode integration (first cut)

1. Add `OpencodeConfig` to `NinaConfig` (enabled, binary_path, host, port, username, password_ref, startup/shutdown timeouts). Expose in `GET /config` and accept in `PATCH /config`. opencode.* changes are restart-required.
2. Generate a 32-byte URL-safe password on `nina init` and store it at `$NINA_CONFIG_DIR/opencode_password` (mode 0600). `config.yaml` only stores the *filename* in `opencode.password_ref`; the secret never lands in YAML.
3. Drop the Nina `Project` concept: hand-written migration in `db/init.py` removes the `projects` table and renames `tasks.project_id` to `tasks.opencode_project_id` (no FK, opaque to Nina). Delete the `Project` model, the `ProjectService` module, the Obsidian project-note helpers, the `/projects` REST routes, the `nina project` CLI, and the `projects_*` LLM tools. Remove the `Projects/` folder from `VAULT_FOLDERS`.
4. Build `nina_core/opencode/{password,client,supervisor,models}.py`. The supervisor owns the `opencode serve` child: resolves the binary, spawns it with `OPENCODE_SERVER_PASSWORD`/`USERNAME` in env, polls `/global/health` until ready, writes `opencode.pid` + `opencode.json`, and SIGTERMs → SIGKILLs on stop. Never raises when the binary is missing — the daemon keeps serving and the TUI shows "not installed".
5. Add `/opencode/{status,health,projects,projects/current}` to the FastAPI app. The supervisor is stashed on `app.state.opencode`; lifespan in `apps/server/nina_server/main.py` starts it after the scheduler and watcher, stops it in `finally`.
6. Add `nina opencode status` and `nina opencode projects list|current` (sub-app alias `oc`). `nina status` gains a one-line `OpenCode: <state>` and a warning when the supervisor is `not_installed`/`failed`/`stopped`.
7. TUI: add the **OpenCode** page between Integrations and Config. Read-only header card (state, binary, listen address, version, uptime, last_error) plus a "All projects" card with `id | worktree | vcs | created | updated`. Empty/error states copy from `nina opencode status`. Standard `Ctrl+R` refresh.
8. Tests: unit tests for `password` (mode 0600, idempotency, force regen, traversal rejection), `client` (basic auth header, parsed payloads, 401/500 typed errors), `supervisor` (healthy → running; missing binary → not_installed; disabled → no spawn), schema tests for `tasks.opencode_project_id`. Integration test boots a tiny in-process HTTP server that mimics `/global/health` + `/project` and asserts the supervisor picks it up through the FastAPI routes.
9. Docs: `04-database-schema.md` drops the `projects` table and documents `opencode_project_id`. `05-api-spec.md` replaces the `/projects` block with `/opencode/*`. `06-cli-spec.md` adds `nina opencode ...` and rewrites the task/project sections. `07-tui-spec.md` adds the OpenCode page.
