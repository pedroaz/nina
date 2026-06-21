# Nina Architecture Reference

## Product Boundary

- Nina is a local-first personal operations platform for one user.
- Optimize for a complete local loop before adding distributed features.
- Do not introduce multi-user auth, remote collaboration, cloud-only core behavior, or a general plugin system unless the task explicitly asks for it.
- Linux is the primary runtime. Keep cross-platform code reasonable, but avoid hiding Linux-specific behavior that the app depends on.

## Runtime Model

- `apps/server` runs the FastAPI daemon on localhost and owns persistent writes.
- `apps/cli` is a Typer client. It may start, stop, and inspect the daemon, but feature commands should go through the API.
- `apps/tui` is an OpenTUI client. It reads and writes through daemon API calls and subscribes to live updates where supported.
- `packages/nina_core` contains shared domain services and should not depend on CLI, TUI, or server presentation code.
- `nina-codex-plugin` is an installable local Codex plugin bundle used by the Nina runner for lifecycle callbacks.

## State Ownership

- SQLite is authoritative for operational state: tasks, sessions, jobs, workflow runs, LLM logs, Codex events, repositories, and search metadata.
- The Obsidian vault is authoritative for durable human-readable notes.
- Nina-managed Markdown should carry frontmatter that lets Nina identify ownership and type.
- Manual edits to note bodies are allowed; operational fields should remain controlled by SQLite and daemon services.
- Deletion behavior should preserve user data where practical, for example moving Nina-managed notes to a deleted area instead of hard-deleting.

## Documentation Map

- Root `README.md`: public overview, install, quick start, architecture, configuration, validation, and contribution notes.
- `CONFIG_LLM.md`: Codex CLI LLM setup.
- Package READMEs: short component summaries for `apps/cli`, `apps/server`, and `packages/nina_core`.
- `tests/README.md`: test layers and smoke behavior.
- `.agents/skills/*`: Codex-facing operational guidance. Keep skills concise and move detail into each skill's `references/` file.

## Design Checks

- Does the daemon still own the write path?
- Are CLI and TUI behavior backed by API contracts instead of duplicated persistence logic?
- Does the change keep local-first operation possible without a hosted service?
- Is the README or nearest component doc updated if public behavior changed?
