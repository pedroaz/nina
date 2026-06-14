# Workflows, LLM, And Scheduler

## Workflow Model

Workflows are Python code. Nina does not support user-authored YAML workflows.

A workflow has:

- name.
- input schema.
- ordered steps.
- stored run record.
- stored step records.
- retry policy per step.
- final output.

Every workflow run is stored in SQLite.

## Step Semantics

Before each step:

- create/update `workflow_steps` as `running`.
- increment attempt count.

After success:

- store step output JSON.
- mark step `completed`.

After failure:

- store error.
- retry if policy allows.
- otherwise mark step and workflow `failed`.

Nina does not need full resume of interrupted in-flight jobs after daemon restart. It marks stale `running` runs as `interrupted` or `failed` on daemon startup.

## First Workflow: summarize-last-day

Goal:

Create a daily summary note from yesterday task activity, workflow/job activity, and relevant notes.

Input:

```json
{
  "date": "2026-06-13"
}
```

Steps:

1. Load tasks updated on the date.
2. Load completed tasks on the date.
3. Load workflow/job events from the date.
4. Load Markdown notes created or updated on the date.
5. Build a compact context bundle.
6. Call LLM with summary prompt.
7. Write `Daily/YYYY-MM-DD.md`.
8. Index the new note.
9. Emit completion event.

Output note:

```markdown
---
nina_type: daily_summary
date: 2026-06-13
workflow_run_id: workflow_...
created_at: 2026-06-14T07:00:00Z
---

# Daily Summary - 2026-06-13

## Summary

...

## Completed

...

## Open Loops

...

## Suggested Next Actions

...
```

## LLM Provider Boundary

Implement one provider first:

```python
class LLMProvider:
    async def complete(self, request: LLMRequest) -> LLMResponse:
        ...
```

Provider config:

```yaml
llm:
  provider: codex
  model: gpt-5
```

Important implementation note:

- Do not let application code depend directly on one OpenAI SDK call shape.
- Keep all provider-specific logic inside `nina_core.llm`.
- Do not assume a ChatGPT or Codex subscription is automatically the same as API credentials. Validate the intended auth path during implementation.

## LLM Logging

Every LLM call stores:

- provider.
- model.
- purpose.
- prompt.
- response.
- status.
- error if failed.
- workflow run ID if relevant.

The user does not require confirmation before AI-generated content is written into Obsidian.

## Scheduler

Use APScheduler inside the daemon.

Scheduled job definitions are persisted in SQLite. In-flight job execution does not need to resume after restart.

Initial scheduled job:

```text
daily-summary
  workflow: summarize-last-day
  default schedule: daily at configured local time
```

The scheduler should create `job_runs` and linked `workflow_runs`.

## Worker Output

Workflows stream status events. Later external worker integrations, such as OpenCode, will stream process output into the same events/log system.

## Later Workflow Ideas

- Start project.
- Start ticket.
- Weekly review.
- Research topic.
- Process meeting recording.
- OpenCode session tracker.
