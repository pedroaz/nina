---
name: nina-architecture
description: Nina product architecture, daemon boundary, state ownership, storage model, and documentation structure. Use when changing repo-wide behavior, README/docs, config/storage decisions, Obsidian/SQLite responsibilities, package boundaries, or public architecture explanations.
---

# Nina Architecture

Use this skill to keep Nina's system shape coherent while changing cross-cutting behavior or documentation.

## Rules

- Treat the daemon as the owner of persistent writes.
- Treat CLI and desktop clients as localhost API clients.
- Keep `packages/nina_core` independent from presentation layers.
- Keep SQLite authoritative for operational state and Obsidian authoritative for human-readable notes.
- Keep root documentation accurate when public behavior or architecture changes.

## Process

1. Read the files relevant to the boundary being changed.
2. Check whether the change crosses daemon, CLI, desktop, core, plugin, or storage ownership.
3. Update the smallest set of code and documentation that keeps the public contract truthful.
4. Use the reference only when architecture, state ownership, or docs structure is part of the task.

## References

- Read `references/architecture.md` for product scope, runtime model, state ownership, documentation map, and design checks.
