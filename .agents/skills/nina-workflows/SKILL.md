---
name: nina-workflows
description: Nina workflows, LLM provider boundary, job scheduling, and daily summary notes. Use when working on nina_core.workflows, scheduler, job runs, or LLM logging.
---

# Nina Workflows

Use this skill for workflow execution, daily summaries, scheduler behavior, LLM provider selection, and job/workflow persistence.

## Rules
- Keep workflow logic in Python.
- Persist workflow runs and workflow steps in SQLite.
- Keep provider-specific LLM code inside `nina_core.llm`.
- Log every LLM interaction with provider, model, purpose, prompt, response, status, and error.
- Seed and update the daily-summary job from the configured local time.

## Read
- `references/workflows.md` for workflow semantics, scheduler behavior, and the daily summary shape.
