---
name: nina-workflows-llm
description: Nina LLM providers, tool-calling chat and agent sessions, workflow execution, scheduler jobs, search/research indexing, and meeting transcription/summarization pipelines. Use when working in nina_core.llm, sessions, workflows, scheduler, research, search, meetings, job runs, or LLM logging.
---

# Nina Workflows LLM

Use this skill when a task touches Nina's LLM, workflow, job, search, research, or meeting pipeline.

## Rules

- Keep provider-specific behavior behind the LLM provider boundary.
- Keep Codex CLI as the default provider path unless the task changes provider selection.
- Keep chat read-only by exposing only read tools.
- Persist workflow, job, LLM, and session state for inspection.
- Enforce note path safety before any tool writes to the vault.

## Process

1. Read the relevant service and tests before changing behavior.
2. Check whether the change affects provider contracts, tool schemas, session persistence, workflow state, or note output.
3. Update tests around fake providers, fake embeddings, isolated vaults, or daemon integration.
4. Update README or config docs if public setup or commands change.

## References

- Read `references/workflows-llm.md` for key files, provider rules, tool/session rules, workflow/job behavior, search/research, and meeting pipeline rules.
