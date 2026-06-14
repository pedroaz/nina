---
name: nina-core
description: Nina product scope, architecture, storage, schema, and open questions. Use when working on repo-wide behavior, config, Obsidian sync, SQLite tables, or deciding what belongs in scope.
---

# Nina Core

Use this skill for repo-wide Nina reasoning: scope, architecture, storage, schema, config, and source-of-truth decisions.

## Rules
- Treat the daemon as the only writer to SQLite and Nina-managed Markdown.
- Treat CLI and TUI as clients over the local API.
- SQLite is authoritative for operational state.
- Obsidian is authoritative for durable human-readable notes.
- Keep Nina Linux-first and single-profile.
- Prefer the smallest complete local loop over extra abstractions.

## Read
- `references/core.md` for product scope, architecture, storage, schema, and open questions.
