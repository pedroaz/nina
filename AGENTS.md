# AGENTS.md

## Repository Profile

- Nina is a local-first personal operations platform for one user.
- Treat the daemon as the source of truth for writes to SQLite, Nina-managed Markdown, jobs, workflows, search indexing, and Codex lifecycle state.
- Treat the CLI and desktop client as clients of the local daemon API. Do not have client code mutate SQLite or the Obsidian vault directly.
- Keep the default AI path on the local Codex CLI unless a task explicitly changes provider behavior.

## Project Layout

- `packages/nina_core`: shared domain services, models, config, database, Obsidian, search, LLM, Codex, workflow, meeting, and repository logic.
- `apps/server`: FastAPI daemon and routers.
- `apps/cli`: Typer CLI and command output formatting.
- `apps/desktop`: GPUI desktop client written in Rust.
- `nina-codex-plugin`: local Codex plugin bundle and lifecycle hook implementation.
- `tests`: unit and integration tests. See `tests/README.md` for the test-layer contract.

## Working Rules

- Preserve user work in this repository. The worktree may already be dirty; do not revert unrelated changes.
- Prefer existing service, router, command, schema, and test patterns before adding new abstractions.
- Keep user-facing CLI output compact; keep `--json` output stable and machine-friendly.
- Keep durable documentation in the root `README.md`, focused docs such as `CONFIG_LLM.md`, package READMEs, tests docs, and repo-scoped skills under `.agents/skills`.
- When behavior changes, update the nearest relevant documentation in the same change.

## Validation

- For Python changes, run the narrowest relevant `uv run pytest ...` command first.
- For shared behavior or API/CLI changes, run `make test` when practical.
- For repo-wide handoff or pull-request-ready work, run `make check` when practical.
- For desktop changes, run `make desktop-check`.
- For daemon, CLI, profile, Codex, workflow, meeting, or desktop integration changes, consider `make smoke`; note that it exercises the default Nina profile.
- If a check is skipped, report why.

## Repo Skills

Use repo-scoped skills when they match the task:

- `$nina-architecture`: product scope, daemon boundary, state ownership, storage, and docs.
- `$nina-cli-api`: CLI commands, FastAPI routers, auth, config, daemon runtime state, and endpoint behavior.
- `$nina-codex-integration`: Codex supervisor, plugin hooks, task lifecycle callbacks, and runner contract.
- `$nina-development`: build, validation, tests, packaging, Makefile, and agent workflow.
- `$nina-workflows-llm`: LLM providers, tool calls, workflows, jobs, search, research, and meeting pipelines.
