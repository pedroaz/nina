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
- OpenCode session tracker.

## `transcribe-meeting` Workflow

Steps:

1. `load_meeting` — load the `Meeting` row by id; fail if the audio file is missing.
2. `transcribe` — call `TranscriptionService.transcribe(meeting)`. Default backend: local `faster-whisper` (16 kHz mono PCM, VAD on, no word timestamps). Writes raw text to `<config>/recordings/mt_<id>.txt`.
3. `update_note` — call `NoteService.update_note` to replace the `## Transcript` section of the meeting note with the new text. Patch `transcript_status: done` into the frontmatter.
4. `log_interaction` — write an `LLMInteraction` row with `purpose="meeting_transcription"`, `provider="local_whisper"`, the model name, the prompt, the response, status, and timings.

## `summarize-meeting` Workflow

Steps:

1. `load_meeting` — load the meeting plus its transcript path.
2. `build_context` — assemble title, `started_at`, transcript (or note body if no transcript), tags, optional project link.
3. `summarize` — call `LLMService.complete` with a fixed system prompt asking for a 3–6 bullet summary, an `## Action items` block, and a `## Decisions` block.
4. `update_note` — replace `## Summary`, `## Action items`, and `## Decisions`; patch `summary_status: done` into the frontmatter.
5. `log_interaction` — write an `LLMInteraction` row with the configured provider/model.
