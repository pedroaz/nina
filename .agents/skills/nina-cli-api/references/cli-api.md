# Nina CLI and API Reference

## Key Files

- `apps/cli/nina_cli/main.py`: top-level Typer app, aliases, status, install/uninstall, `ask`, and `open`.
- `apps/cli/nina_cli/*_commands.py`: feature command groups.
- `apps/cli/nina_cli/api.py`: daemon base URL resolution and request helpers.
- `apps/server/nina_server/app.py`: FastAPI application factory.
- `apps/server/nina_server/routers/`: API routers.
- `apps/server/nina_server/schemas/`: request and response schemas.
- `apps/server/nina_server/auth.py`: bearer-token middleware.

## CLI Contract

- Keep command groups thin. Command code should validate CLI arguments, call daemon endpoints, and format output.
- Do not import server router internals into CLI command logic.
- Keep plain output readable and compact.
- Keep `--json` output stable and script-friendly.
- Hidden aliases are acceptable for speed, but the full command names should remain discoverable.

## Daemon Addressing

- Resolve the active profile and live daemon runtime state before falling back to saved config.
- `config.yaml` is persisted next-start configuration.
- Runtime daemon state points clients at the actual host and port while the daemon is running.
- The default profile lives under `~/.nina/default` unless profile/config resolution says otherwise.

## API Surface

- Health and config: `/health`, `/config`.
- Tasks and board behavior: `/tasks`, task typing/classification/archive flows.
- Notes, search, and ask: `/notes`, `/search`, `/ask`.
- Sessions and LLM: `/sessions`, `/sessions/{id}/cancel`, `/llm`.
- Workflows and jobs: `/workflows`, `/workflow-runs`, `/jobs`, `/job-runs`.
- Meetings: `/meetings`.
- Repositories: `/repositories`.
- Integrations: `/integrations`.
- Codex: `/codex/status`, `/codex/events`, and related router endpoints.

## Config Rules

- Use Pydantic defaults so old config files remain valid.
- When adding settings, update config schemas, CLI config commands, daemon config behavior, status output where useful, and README/config docs.
- Host, port, and some runtime settings may require daemon restart. Surface that clearly in CLI output.
- Secrets should live in files or external credential stores, not in `config.yaml`.

## Test Targets

- CLI command behavior: `tests/unit/test_cli_commands.py` and command-specific unit tests.
- API behavior: `tests/integration/test_daemon_api.py` and feature-specific integration tests.
- Real CLI plus daemon smoke: `uv run pytest -m daemon_smoke tests/integration/test_cli_daemon_smoke.py`.
