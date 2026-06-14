---
name: nina-development
description: Nina repo validation, make targets, temp-data smoke tests, and implementation sequencing. Use when changing tests, dev harnesses, build scripts, or backlog/planning docs.
---

# Nina Development

Use this skill for repo setup, developer tooling, smoke tests, validation strategy, and backlog-driven implementation work.

## Rules
- Prefer temporary config, temporary SQLite, and temporary vaults in tests.
- Exercise the daemon through the API; do not bypass it in CLI/TUI integration tests.
- Keep validation layered: unit, integration, CLI, TUI, smoke.
- Treat the make targets and temp-data flow as the local development contract.
- Use the backlog and open questions as implementation guidance, not as product truth.

## Read
- `references/development.md` for the make/dev/test contract, backlog order, and remaining implementation constraints.
