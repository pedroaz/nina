---
name: nina-codex-integration
description: Nina Codex integration, supervised Codex server/client behavior, Codex plugin hooks, task lifecycle events, runner environment variables, and Nina task final reports. Use when changing packages/nina_core/nina_core/codex, apps/server Codex routes, apps/cli Codex commands, nina-codex-plugin, or Codex task automation.
---

# Nina Codex Integration

Use this skill when a task touches Nina's Codex-backed automation path.

## Rules

- Keep Nina daemon/core code responsible for lifecycle state transitions.
- Keep Codex hooks best-effort so callback failures do not block Codex.
- Never expose Codex passwords or bearer tokens in docs, logs, or command output.
- Preserve the `nina-task` final report contract because Nina parses it.
- Treat dangerous Codex runner flags as controlled-runner behavior, not a general user recommendation.

## Process

1. Read the Codex core module, router, CLI command, plugin hook, or installer relevant to the task.
2. Check the event payload and task-status semantics before changing lifecycle behavior.
3. Update hook, daemon endpoint, tests, and plugin README together when the runtime contract changes.
4. Verify with focused Codex API, event, supervisor, hook, or plugin tests.

## References

- Read `references/codex-integration.md` for key files, runtime contract, status semantics, safety rules, and validation targets.
