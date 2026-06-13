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

```http
GET /projects
POST /projects
GET /projects/{project_id}
PATCH /projects/{project_id}
DELETE /projects/{project_id}
```

Create request:

```json
{
  "name": "Supplier onboarding",
  "description": "Initial project context"
}
```

## Tasks

```http
GET /tasks
POST /tasks
GET /tasks/{task_id}
PATCH /tasks/{task_id}
DELETE /tasks/{task_id}
```

Task list filters:

- `project_id`
- `status`
- `kanban_column`

Create request:

```json
{
  "title": "Draft implementation plan",
  "description": "Create the first version of the plan.",
  "project_id": "project_..."
}
```

Patch request:

```json
{
  "title": "Draft executable implementation plan",
  "status": "doing",
  "kanban_column": "Doing"
}
```

## Kanban

```http
GET /kanban
POST /kanban/move
```

Move request:

```json
{
  "task_id": "task_...",
  "to_column": "Doing",
  "to_position": 2
}
```

The move endpoint must update all affected task positions transactionally.

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
