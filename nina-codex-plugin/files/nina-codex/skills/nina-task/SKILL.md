---
name: nina-task
description: Work on a Nina task launched by the Nina runner and produce a clear final report. Lifecycle callbacks are handled automatically by hooks.
---

# Nina Task

Use this skill when the user or runner asks Codex to work on a Nina task.

## Operating rules

- Treat the prompt as the source of truth for the Nina task id, run id, task body, constraints, and done criteria.
- Do not call Nina directly from the model response or shell unless the user explicitly asks for a separate manual callback.
- Lifecycle reporting is automatic: the Nina Codex hooks report `started` at session start and `done` when the turn stops.
- Nina owns task transitions through hook actions. Your job is to complete the requested task type and provide a final report.
- If blocked, state the blocker clearly in the final response instead of trying to change Nina state.

## Final response format

End every Nina task run with a concise report containing:

- Outcome: completed, partially completed, or blocked.
- Decision: approved, rejected, or blocked, only for reviewing tasks.
- Summary: what changed or what was discovered.
- Files: key files changed or inspected, when relevant.
- Checks: commands run and results, or state that checks were not run.
- Blockers: any missing input, failing dependency, or risk Nina should know about.
