# Nina Workflows Reference

## Workflow Model
- Workflows are Python code.
- No user-authored YAML workflows.
- Persist workflow runs and step records in SQLite.
- Retry policy belongs to the step.
- Mark stale in-flight runs as interrupted or failed on startup.

## Step Semantics
- Mark a step running before execution.
- Increment attempt count on each try.
- Store output JSON and mark completed after success.
- Store error and retry if policy allows after failure.

## First Workflow: summarize-last-day
- Load tasks updated on the date.
- Load completed tasks on the date.
- Load workflow and job events from the date.
- Load Markdown notes created or updated on the date.
- Build a compact context bundle.
- Call the LLM.
- Write `Daily/YYYY-MM-DD.md`.
- Index the new note.
- Emit completion event.

## Daily Summary Note
- Frontmatter should include `nina_type: daily_summary`, `date`, `workflow_run_id`, and `created_at`.
- Keep the body structured and compact.

## LLM Boundary
- Use an `LLMProvider` interface.
- Keep provider-specific logic inside `nina_core.llm`.
- Do not assume ChatGPT, Codex, and API credentials are interchangeable.
- Keep model and provider selection explicit.

## LLM Logging
- Store provider, model, purpose, prompt, response, status, error, workflow run ID, created_at, and completed_at.

## Scheduler
- Use APScheduler inside the daemon.
- Persist job definitions in SQLite.
- Seed the daily-summary job from the configured local time.
- Keep in-flight jobs restart-tolerant but not resumable.
