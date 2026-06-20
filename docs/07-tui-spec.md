# TUI Spec

The TUI is the main interactive interface. It should use the OpenTUI library supplied by the user and live under `apps/tui`.

The TUI is a client. It does not write SQLite or Markdown directly.

## Layout

Primary navigation (tab order):

- Tickets
- Chat
- Agent
- Research
- Meetings
- Jobs
- Integrations
- OpenCode
- Config

The TUI optimizes for keyboard use.

## Dashboard

Shows:

- active tasks grouped by type.
- running workflow/job count.
- latest events.
- latest daily summary.

Required actions:

- create task.
- jump to Tickets.
- run daily summary workflow.
- open search.

## Tickets (task inbox + type-grouped view)

Two sub-tabs at the top of the Tickets page, toggled with `Ctrl+X`:

- **Inbox** — `task_type=unclassified` only. The "needs the AI's eye" queue.
- **All** — every active task grouped by `task_type`. Sections are rendered
  in lifecycle order: unclassified, coding, research, reminder, blocked,
  human, done.

Keyboard interactions on the Tickets page:

- `Ctrl+X` toggles between the Inbox and All views.
- `Ctrl+Up` / `Ctrl+Down` move selection.
- `Enter` opens the "Create task" prompt (the input is at the bottom of
  the page).
- `Ctrl+E` opens or closes the detail view of the selected task.
- `Ctrl+G` cycles the selected task's `task_type` to the next value in
  the lifecycle order.
- `Ctrl+1`..`Ctrl+7` set `task_type` directly:
  1=unclassified, 2=coding, 3=research, 4=reminder, 5=blocked, 6=human,
  7=done.
- `Ctrl+L` re-runs the AI classifier on the selected task.
- `Ctrl+Enter` routes the selected task to its handler (the `run-task`
  workflow). For `human`/`reminder`/`blocked` tasks this prints a banner
  and is a no-op.
- `Ctrl+D` deletes the selected task (with a Y/N confirmation).
- `Ctrl+A` archives the selected task (with a Y/N confirmation).
- `Ctrl+R` refreshes the page.
- `PageUp` / `PageDown` scroll the list.

The TUI calls `GET /tasks/grouped-by-type` to render the board. Creating a
task posts to `POST /tasks` and switches the view to the Inbox so the new
task is visible while the background classifier runs.

## Task Detail

Shows:

- title.
- project.
- task_type (with a type picker that calls `PATCH /tasks/{id}`).
- agent status (`idle` / `working`).
- Markdown note path.
- description.
- classified_at, classification_model, classification_reason.
- created/updated timestamps.

Actions:

- change `task_type` via `Ctrl+G` (cycle) or `Ctrl+1..7` (set directly).
- re-run the AI classifier (Ctrl+L).
- route the task to its handler (Ctrl+Enter).
- delete (Ctrl+D).
- archive (Ctrl+A).
- open note in Obsidian (via `POST /search/open`).

Every action has a keyboard shortcut. The TUI does not rely on mouse
clicks. The type-change action posts to `PATCH /tasks/{id}` and refreshes
the page so the task moves to the right section.

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

Shows the current config and lets the user edit saved values:

- vault path.
- database path.
- daemon host/port.
- LLM provider/model.
- daily summary schedule.
- log level.
- opencode.enabled / opencode.binary_path / opencode.host / opencode.port /
  opencode.username / opencode.password_ref / opencode.startup_timeout_seconds /
  opencode.shutdown_timeout_seconds.

The TUI reads `GET /config`, edits one field at a time, and saves through `PATCH /config`. Host, port, and log level changes should surface that a daemon restart is required. opencode.* changes are also restart-required so the supervisor can pick up the new binary path, port, or credentials.

## OpenCode

Read-only observability page for the supervised `opencode serve` child.
Surfaces:

- the supervisor's `state` (`disabled`, `not_installed`, `starting`,
  `running`, `stopped`, `failed`).
- the binary path that was resolved, plus whether opencode is enabled and
  installed.
- the listen address (`http://host:port`) and version reported by
  `GET /global/health`.
- uptime, pid, and `last_error` (when not running).
- the list of projects the opencode server has registered
  (`GET /opencode/projects`): `id | worktree | vcs | created | updated`.
- the `current` project (from `GET /opencode/projects/current`) if any.

The page is read-only. Use the existing `Ctrl+R` shortcut to refresh and
`Esc` to return to the tab strip. For edits use the Config page or
`nina config opencode-*` (future).

## Streaming

The TUI should subscribe to:

```text
GET /events/stream
```

This keeps job status, workflow progress, and event panels live while the daemon runs.
