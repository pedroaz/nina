# Nina CLI and API Reference

## Local Addressing
- `api_base()` should prefer `daemon.json` in the active config dir.
- `daemon.json` stores the live daemon profile, config dir, host, and port.
- Fall back to the resolved config file if runtime state is missing.
- Final fallback is `http://127.0.0.1:8765`.

## Auth
- Use the bearer token stored in the config directory.
- Protected routes require `Authorization: Bearer <token>`.

## Core Commands
- `nina init`
- `nina daemon start`
- `nina daemon stop`
- `nina daemon status`
- `nina status`
- `nina tui`

## Config Commands
- `nina config show`
- `nina config vault <path>`
- `nina config database <path>`
- `nina config daemon-host <host>`
- `nina config daemon-port <port>`
- `nina config log-level <level>`
- `nina config llm-provider <provider>`
- `nina config llm-model <model>`
- `nina config daily-summary-time <HH:MM>`

## Config Update Contract
- `GET /config` returns resolved config values.
- `PATCH /config` persists config, updates live app state, and returns changed fields.
- Changing vault or database path should ensure storage exists immediately.
- Changing daemon host, daemon port, or log level requires a daemon restart to affect the listener.
- The CLI should try to sync a live daemon, but disk state remains the source of truth for the next restart.

## API Surface
- Health: `GET /health`
- Projects: `GET/POST/PATCH/DELETE /projects`
- Tasks: `GET/POST/PATCH/DELETE /tasks`
- Kanban: `GET /kanban`, `POST /kanban/move`
- Search: `POST /search`, `POST /search/reindex`, `POST /search/open`
- LLM: `POST /llm/complete`, `GET /llm/interactions`, `GET /llm/interactions/{id}`
- Workflows: `GET /workflows`, `POST /workflows/{workflow_name}/run`, `GET /workflow-runs`, `GET /workflow-runs/{id}`
- Jobs: `GET /jobs`, `PATCH /jobs/{id}`, `POST /jobs/{id}/run`, `GET /job-runs`
- Events: `GET /events`, `GET /events/stream`, `GET /workflow-runs/{run_id}/stream`

## Output Rules
- Mutating commands should print the changed entity ID.
- Plain output should stay compact.
- `--json` should return script-friendly JSON.
