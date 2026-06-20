# API Spec

The daemon exposes a local REST API plus SSE streams. CLI and TUI should use this API instead of importing server internals.

Base URL:

```text
http://127.0.0.1:8765
```

Auth:

```http
Authorization: Bearer <local-token>
```

## Health

```http
GET /health
```

Response:

```json
{
  "status": "ok",
  "profile": "default",
  "vault_path": "/home/user/NinaVault"
}
```

## Projects

The Nina daemon no longer exposes a `/projects` resource. Project identity is
owned by the supervised opencode server and surfaced through `/opencode/*`.

## Tasks

```http
GET /tasks
POST /tasks
GET /tasks/{task_id}
PATCH /tasks/{task_id}
DELETE /tasks/{task_id}
POST /tasks/{task_id}/classify
POST /tasks/{task_id}/run
POST /tasks/{task_id}/archive
POST /tasks/{task_id}/unarchive
GET /tasks/grouped-by-type
```

Task list filters:

- `task_type` — filter by one of the lifecycle values.
- `status` — `idle` or `working`.
- `include_archived` — boolean.

Create request:

```json
{
  "title": "Draft implementation plan",
  "description": "Create the first version of the plan.",
  "opencode_project_id": "abc123...",
  "task_type": "coding",
  "auto_classify": true
}
```

`opencode_project_id` is the server-assigned id from the supervised opencode
server (`GET /opencode/projects`). Nina stores it as an opaque string and
does not validate it. If `task_type` is omitted (or `unclassified`) and
`auto_classify` is `true`, the daemon enqueues the `classify-task` workflow in
a background thread and returns immediately. The TUI auto-refreshes the row
when the workflow finishes.

Patch request:

```json
{
  "title": "Draft executable implementation plan",
  "task_type": "coding",
  "status": "idle",
  "opencode_project_id": "abc123..."
}
```

Omit `opencode_project_id` to leave it unchanged. Pass an empty string to
clear the link.

`POST /tasks/{task_id}/classify` re-runs the LLM classifier on a task and
patches the task_type, classified_at, classification_reason, and
classification_model fields.

`POST /tasks/{task_id}/run` runs the `run-task` workflow. For
`human`/`reminder`/`blocked` tasks it returns `{status: "skipped"}`; for
`done` it returns `{status: "noop"}`; for `coding`/`research` it flips the
agent's `status` to `working` and back to `idle` while a routing decision is
recorded (placeholder; the real handler lands in a follow-up slice).

`GET /tasks/grouped-by-type` returns the type-grouped view used by the TUI's
"All" tab. Shape: `{ "<task_type>": [task, ...], ... }`. The `unclassified`
group is the TUI's Inbox.

## Opencode Integration

The Nina daemon supervises an `opencode serve` child process. TUI and CLI
talk to opencode only through these endpoints (the bearer token still
applies); direct HTTP to the opencode server is not supported from clients.

```http
GET /opencode/status
GET /opencode/health
GET /opencode/projects
GET /opencode/projects/current
```

`GET /opencode/status` returns the supervisor's view of the opencode server:

```json
{
  "enabled": true,
  "binary_installed": true,
  "binary_path": "/home/u/.opencode/bin/opencode",
  "state": "running",
  "version": "1.17.8",
  "host": "127.0.0.1",
  "port": 5555,
  "uptime_seconds": 482.7,
  "pid": 4242,
  "last_error": null
}
```

`state` is one of `disabled`, `not_installed`, `starting`, `running`,
`stopped`, `failed`. When `state != "running"`, `version`, `pid`, and
`uptime_seconds` are `null`.

`GET /opencode/health` proxies the opencode server's `/global/health` and
returns `{"healthy": true, "version": "1.17.8", "status": {...}}`. Returns
`502` if the supervisor cannot reach the server, `503` if the supervisor
itself is not in `running` state.

`GET /opencode/projects` returns the array of projects the opencode server
knows about:

```json
[
  {
    "id": "58fb1ebb82bf46d13af8891d4eaffa544980706a",
    "worktree": "/home/u/Desktop/dev/nina-app",
    "vcs": "git",
    "time": {
      "created": 1781328510400,
      "updated": 1781758376383
    },
    "sandboxes": []
  }
]
```

`GET /opencode/projects/current` returns the single project the opencode
server considers "current" (the worktree the server was started in, if any).
Shape: same as one element of `/opencode/projects`.

## Search

```http
POST /search
POST /search/reindex
POST /search/open
```

Search request:

```json
{
  "query": "supplier onboarding",
  "limit": 20
}
```

Open request:

```json
{
  "path": "Projects/supplier-onboarding.md"
}
```

## LLM

```http
POST /llm/complete
GET /llm/interactions
GET /llm/interactions/{interaction_id}
```

LLM calls should normally happen through workflows, but this endpoint is useful for testing the provider boundary.

Complete request:

```json
{
  "purpose": "manual_test",
  "prompt": "Summarize the current kanban board."
}
```

## Workflows

```http
GET /workflows
POST /workflows/{workflow_name}/run
GET /workflow-runs
GET /workflow-runs/{run_id}
```

Run request:

```json
{
  "input": {
    "date": "2026-06-13"
  }
}
```

## Notes

The `/notes` family exposes raw vault reads and writes. The LLM chat and
agent tools use these endpoints under the hood.

```http
GET /notes?folder=&nina_type=&limit=20
GET /notes/{path:path}
POST /notes
PATCH /notes/{path:path}
```

`POST /notes` body:

```json
{
  "path": "Research/new.md",
  "body": "# Title\n\nbody",
  "nina_type": "note"
}
```

`PATCH /notes/{path:path}` body (one of):

```json
{ "body": "new body", "frontmatter_patch": { "title": "New" } }
```

```json
{ "append": "extra paragraph" }
```

Path safety:

- No absolute paths.
- No `..` traversal.
- Paths under `System/Indexes/`, `System/Logs/`, `System/Deleted/`, or `Templates/` are refused.

## Session Cancellation

```http
POST /sessions/{session_id}/cancel
POST /sessions/{session_id}/clear-cancel
```

The daemon checks the cancel flag between tool-loop iterations and on the
next LLM call. The assistant message metadata records
`finish_reason: "cancelled"`.

## Jobs

```http
GET /jobs
PATCH /jobs/{job_id}
POST /jobs/{job_id}/run
GET /job-runs
```

Patch request:

```json
{
  "enabled": true
}
```

## Events And Streaming

```http
GET /events
GET /events/stream
GET /workflow-runs/{run_id}/stream
```

Use Server-Sent Events for streaming:

- daemon events.
- job run updates.
- workflow step updates.
- long-running worker output later.

## Error Shape

All non-2xx API errors should return:

```json
{
  "error": {
    "code": "task_not_found",
    "message": "Task was not found.",
    "details": {}
  }
}
```
