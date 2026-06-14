# Database Schema

Use SQLite with SQLAlchemy models and Alembic migrations. IDs should be stable string IDs such as UUIDv7 or ULID-style values.

All timestamps should be stored in UTC using ISO 8601 text.

## projects

```sql
CREATE TABLE projects (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT "",
  status TEXT NOT NULL DEFAULT "active",
  note_path TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
```

Status values:

- `active`
- `paused`
- `done`
- `deleted`

## tasks

```sql
CREATE TABLE tasks (
  id TEXT PRIMARY KEY,
  project_id TEXT REFERENCES projects(id),
  title TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT "",
  status TEXT NOT NULL DEFAULT "todo",
  kanban_column TEXT NOT NULL DEFAULT "Todo",
  kanban_position INTEGER NOT NULL DEFAULT 0,
  note_path TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
```

Initial status values:

- `backlog`
- `todo`
- `doing`
- `review`
- `done`
- `deleted`

## kanban_columns

```sql
CREATE TABLE kanban_columns (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  position INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
```

Seed columns:

1. Backlog
2. Todo
3. Doing
4. Review
5. Done

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
