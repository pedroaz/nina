# TUI Spec

The TUI is the main interactive interface. It should use the OpenTUI library supplied by the user and live under `apps/tui`.

The TUI is a client. It does not write SQLite or Markdown directly.

## Layout

Primary navigation:

- Dashboard
- Kanban
- Search
- Daily
- Jobs
- LLM Logs
- Settings

V1 should optimize for keyboard use.

## Dashboard

Shows:

- active tasks grouped by column.
- running workflow/job count.
- latest events.
- latest daily summary.

Required actions:

- create task.
- jump to kanban.
- run daily summary workflow.
- open search.

## Kanban

Global board with columns:

- Backlog
- Todo
- Doing
- Review
- Done

Keyboard interactions:

- arrow keys or Vim-style keys move focus.
- enter opens task detail.
- `n` creates a task.
- `e` edits selected task.
- `d` marks done.
- `x` deletes selected task.
- `[` and `]` move selected task left/right across columns.
- `Shift+Up` and `Shift+Down` reorder within a column.

The TUI calls `POST /kanban/move` for all moves.

## Task Detail

Shows:

- title.
- project.
- status/column.
- Markdown note path.
- description.
- recent events.

Actions:

- edit title/description.
- move status.
- open note in Obsidian.
- delete.

## Search

Search all indexed Nina vault Markdown.

Shows:

- title.
- path.
- snippet.

Actions:

- open result in Obsidian.
- copy path.
- reindex.

## Daily

Shows generated daily summaries from `Daily/`.

Actions:

- run summarize-last-day.
- open summary in Obsidian.

## Jobs

Shows:

- scheduled jobs.
- enabled/disabled state.
- last run.
- next run.
- latest status.

Actions:

- enable/disable job.
- run now.
- inspect latest run.

## LLM Logs

Shows:

- provider.
- model.
- purpose.
- status.
- timestamp.

Actions:

- inspect prompt.
- inspect response.
- inspect error.

## Settings

Shows read-only V1 config:

- vault path.
- database path.
- daemon URL.
- LLM provider/model.
- daily summary schedule.

Editing settings can come later.

## Streaming

The TUI should subscribe to:

```text
GET /events/stream
```

This keeps job status, workflow progress, and event panels live while the daemon runs.
