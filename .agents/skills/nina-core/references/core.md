# Nina Core Reference

## Scope
- Local-first personal operations platform for one user.
- Linux-first in V1; WSL later is acceptable.
- No remote access, multi-user auth, or general plugin system in V1.
- The product loop is: CLI/TUI action -> daemon API -> SQLite -> Obsidian -> search index -> optional LLM workflow -> visible logs.

## Runtime Model
- Daemon owns SQLite, Obsidian writes, scheduler, workflow execution, LLM calls, and logs.
- CLI starts the daemon when needed and calls the local API.
- TUI is an OpenTUI client that talks to the daemon API and SSE streams.
- Only the daemon mutates persistent state.

## Storage Rules
- SQLite is authoritative for projects, tasks, workflow runs, job runs, LLM logs, events, and search metadata.
- Obsidian is authoritative for durable human-readable notes.
- Nina-created files carry `nina_type` and `nina_id` frontmatter.
- Manual body edits are allowed; operational fields remain controlled by SQLite.
- Deletes move notes to `System/Deleted/` instead of hard-deleting in V1.

## V1 Vault Layout
- `Projects/`
- `Tasks/`
- `Daily/`
- `Templates/`
- `System/`
- Search uses SQLite FTS5 over title, body, path, and `nina_type`.

## Core Tables
- `projects`
- `tasks`
- `notes`
- `note_search`
- `llm_interactions`
- `workflow_runs`
- `workflow_steps`
- `scheduled_jobs`
- `job_runs`
- `events`
- `settings`

## Open Questions and Defaults
- OpenTUI runtime details stay client-side.
- Use OpenAI API credentials for the provider boundary first; keep Codex-specific auth separate.
- Keep task fields simple in V1.
- Keep one active profile in V1.
- Prefer moving deleted notes to `System/Deleted/`.
- Validate the Linux Obsidian open command before adding a hard dependency.
