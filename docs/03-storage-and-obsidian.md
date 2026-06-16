# Storage And Obsidian

## Source Of Truth Rules

SQLite is authoritative for operational state:

- Project IDs and status.
- Task IDs, status, kanban column, and position.
- Workflow run status.
- Job run status.
- LLM prompt/output logs.
- Search index metadata.

Obsidian is authoritative for durable human-readable knowledge:

- Project notes.
- Task notes and descriptions.
- Daily summaries.
- Research notes.
- Meeting notes (transcript + summary).
- Long-form context that should survive outside Nina.

The daemon keeps both layers connected. CLI and TUI do not write Markdown directly.

## Vault Layout

Nina creates and manages a new vault:

```text
Vault/
  Projects/
  Tasks/
  Daily/
  Research/
  Meetings/
  Knowledge/
  Templates/
  System/
    Indexes/
    Logs/
```

Nina uses only:

- `Projects/`
- `Tasks/`
- `Daily/`
- `Meetings/`
- `Templates/`
- `System/`

## Markdown Format

Use minimal YAML frontmatter for Nina-managed notes. This makes notes easy for humans, Obsidian, scripts, and LLMs to consume.

Example task note:

```markdown
---
nina_type: task
nina_id: task_01J...
status: todo
project_id: project_01J...
kanban_column: Todo
created_at: 2026-06-13T10:00:00Z
updated_at: 2026-06-13T10:30:00Z
---

# Task title

## Description

...

## Activity

- 2026-06-13 10:30: moved to Todo
```

The frontmatter is intentionally small. Nina should not depend on Obsidian plugins.

## Sync Rules

Manual edits in Obsidian are expected.

Sync model:

- Nina-created files include `nina_type` and `nina_id`.
- On index, Nina reads Markdown content and updates search tables.
- The body text of notes can be edited freely in Obsidian.
- Operational fields remain controlled by SQLite.
- If a user changes frontmatter operational fields manually, Nina does not treat that as authoritative.
- Nina updates frontmatter when operational state changes.

This keeps kanban reliable while still letting Obsidian be the main knowledge surface.

## Task And Project Mirroring

Projects:

- Stored in SQLite.
- Have a project note in `Projects/`.
- Project note path is stored in SQLite.

Tasks:

- Stored in SQLite.
- Have a task note in `Tasks/`.
- Task status, column, and position are stored in SQLite.
- Task Markdown is updated when title/status/project changes.

Not every future DB object must have a note, but projects and tasks should now because they are important for LLM context.

## Deletes

Delete behavior:

- Delete task/project from active SQLite tables.
- Move the linked Markdown note to `System/Deleted/` instead of permanent deletion.
- Record an event log entry.

Hard delete can be added later. Moving notes first is safer for a personal knowledge base and still removes deleted items from active Nina views.

## Search Index

Use SQLite FTS5.

Indexed fields:

- title.
- body text.
- path.
- `nina_type`.

Nina does not need to parse backlinks, headings, or tags beyond simple title/body extraction.

Index triggers:

- daemon startup.
- scheduled periodic index job.
- manual CLI command: `nina search reindex`.

File watching can be added later if needed.

## Opening Results In Obsidian

Search results should include:

- title.
- path.
- snippet.
- score/rank.

The CLI and TUI should support opening a result in Obsidian. On Linux, Nina can shell out through the configured Obsidian URI scheme or a configured command.
