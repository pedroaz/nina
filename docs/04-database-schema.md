# Database Schema

Use SQLite with SQLAlchemy models and Alembic migrations. IDs should be stable string IDs such as UUIDv7 or ULID-style values.

All timestamps should be stored in UTC using ISO 8601 text.

## projects

This table was removed when Nina dropped its own project concept in favor of
letting the supervised opencode server own "project = folder" identity. The
hand-written migration in `db/init.py` drops it on next `create_database()`.

## tasks

```sql
CREATE TABLE tasks (
  id TEXT PRIMARY KEY,
  opencode_project_id TEXT,            -- server-assigned opencode project id (no FK)
  title TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT "",
  task_type TEXT NOT NULL DEFAULT "unclassified",
  status TEXT NOT NULL DEFAULT "idle",
  classified_at TEXT,
  classification_reason TEXT,
  classification_model TEXT,
  note_path TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
```

`task_type` is the lifecycle axis. The classifier workflow chooses one of these
on creation (or the user can set it directly via `PATCH /tasks/{id}`):

- `unclassified` — the inbox marker. The AI has not decided yet.
- `reminder` — a personal reminder the user needs to act on.
- `research` — open-ended investigation the AI can answer by reading/writing notes.
- `coding` — a development task the AI can work on.
- `blocked` — waiting on someone or something else.
- `done` — the work is already complete.
- `human` — needs the user to do something the AI cannot.

`status` is the agent's working/idle flag:

- `idle`
- `working` — flipped by the `run-task` workflow while a real handler runs.

`opencode_project_id` is the opaque id the supervised opencode server returns
for a registered worktree (`GET /project`). Nina does not validate it; if
opencode forgets that id, the task is unlinked but its note and DB row stay
intact. The hand-written migration in `db/init.py` renames the legacy
`project_id` column to `opencode_project_id` (best-effort) and drops the
`projects` table on next `create_database()`.

Archived tasks use `task_type = "archived"`. Soft-deleted tasks use
`task_type = "deleted"`.

The legacy `kanban_column` + `kanban_position` columns and the `kanban_columns`
table were dropped when this model landed. The lightweight migration in
`db/init.py` removes them on next `create_database()`.

## kanban_columns

This table was removed when tasks were moved to the type-grouped model. The
lightweight migration in `db/init.py` drops it if present.

## notes

Tracks Nina-managed and indexed Markdown files.

```sql
CREATE TABLE notes (
  id TEXT PRIMARY KEY,
  nina_type TEXT NOT NULL,
  entity_id TEXT,
  path TEXT NOT NULL UNIQUE,
  title TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  last_indexed_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
```

## note_search

SQLite FTS virtual table.

```sql
CREATE VIRTUAL TABLE note_search USING fts5(
  note_id UNINDEXED,
  title,
  body,
  path UNINDEXED,
  nina_type UNINDEXED
);
```

## llm_interactions

```sql
CREATE TABLE llm_interactions (
  id TEXT PRIMARY KEY,
  provider TEXT NOT NULL,
  model TEXT NOT NULL,
  purpose TEXT NOT NULL,
  prompt TEXT NOT NULL,
  response TEXT,
  status TEXT NOT NULL,
  error TEXT,
  workflow_run_id TEXT,
  created_at TEXT NOT NULL,
  completed_at TEXT
);
```

Status values:

- `pending`
- `completed`
- `failed`

## workflow_runs

```sql
CREATE TABLE workflow_runs (
  id TEXT PRIMARY KEY,
  workflow_name TEXT NOT NULL,
  status TEXT NOT NULL,
  input_json TEXT NOT NULL DEFAULT "{}",
  output_json TEXT,
  error TEXT,
  started_at TEXT NOT NULL,
  completed_at TEXT
);
```

Status values:

- `pending`
- `running`
- `paused`
- `completed`
- `failed`
- `interrupted`

## workflow_steps

```sql
CREATE TABLE workflow_steps (
  id TEXT PRIMARY KEY,
  workflow_run_id TEXT NOT NULL REFERENCES workflow_runs(id),
  step_name TEXT NOT NULL,
  position INTEGER NOT NULL,
  status TEXT NOT NULL,
  input_json TEXT NOT NULL DEFAULT "{}",
  output_json TEXT,
  error TEXT,
  attempts INTEGER NOT NULL DEFAULT 0,
  started_at TEXT,
  completed_at TEXT
);
```

## scheduled_jobs

```sql
CREATE TABLE scheduled_jobs (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  workflow_name TEXT NOT NULL,
  schedule_kind TEXT NOT NULL,
  schedule_value TEXT NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 1,
  last_run_at TEXT,
  next_run_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
```

In-flight scheduled jobs do not need to resume after daemon restart. Job definitions should persist.

## job_runs

```sql
CREATE TABLE job_runs (
  id TEXT PRIMARY KEY,
  scheduled_job_id TEXT REFERENCES scheduled_jobs(id),
  workflow_run_id TEXT REFERENCES workflow_runs(id),
  status TEXT NOT NULL,
  started_at TEXT NOT NULL,
  completed_at TEXT,
  error TEXT
);
```

## events

Append-only operational log for debugging and TUI display.

```sql
CREATE TABLE events (
  id TEXT PRIMARY KEY,
  level TEXT NOT NULL,
  source TEXT NOT NULL,
  message TEXT NOT NULL,
  entity_type TEXT,
  entity_id TEXT,
  payload_json TEXT NOT NULL DEFAULT "{}",
  created_at TEXT NOT NULL
);
```

## settings

```sql
CREATE TABLE settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
```

## Initial Migration Tasks

The first migration should:

1. Create all initial tables.
2. Create the FTS table.
3. Seed default kanban columns.
4. Seed a daily summary scheduled job based on config.
