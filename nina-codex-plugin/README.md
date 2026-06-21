# Nina Codex Plugin Replication Guide

This directory contains the local Nina Codex proof-of-concept plugin bundle and
installer for another machine.

The plugin reports two Codex lifecycle events back to Nina:

- `started`: emitted from the Codex `SessionStart` hook.
- `done`: emitted from the Codex `Stop` hook.

Nina receives those callbacks at `POST /codex/events`, stores them idempotently
by `(taskId, runId, event)`, and drives the current board fields:

- `started` sets the task agent `status` to `working`.
- `done` sets the task agent `status` to `idle`.
- `done` applies explicit hook actions such as `setStatus`, `setTaskType`, and `createNextTaskType`.
- Coding completion, including missing or unparseable final reports, marks the task `done` and asks Nina to create a `reviewing` follow-up task. Blocked or partial coding reports mark it `blocked`.
- Reviewing completion marks the review task `done`; rejected, blocked, partial, missing, or unparseable review reports mark it `blocked`.

The external runner still owns launching Codex. This plugin only reports
lifecycle callbacks.

## Installed locations

The installer writes the plugin source and personal marketplace entry here:

```text
~/plugins/nina-codex/
~/.agents/plugins/marketplace.json
```

After `codex plugin add nina-codex@personal`, Codex manages its own installed
copy/cache.

The repo-local bundle lives under:

```text
nina-codex-plugin/files/
```

## Runtime contract

Nina should start Codex with these environment variables:

```bash
NINA_TASK_ID=<task-id>
NINA_RUN_ID=<unique-run-id>
NINA_TASK_TYPE=<coding|reviewing>
NINA_BASE_URL=http://127.0.0.1:<nina-port>
NINA_TOKEN=<nina-bearer-token>
```

Optional:

```bash
NINA_HOOK_TIMEOUT_MS=2000
```

The hook sends:

```http
POST /codex/events
Authorization: Bearer <NINA_TOKEN>
Content-Type: application/json
```

Payload:

```json
{
  "version": 1,
  "event": "started",
  "source": "codex-hook",
  "taskId": "nina-task-id",
  "runId": "nina-run-id",
  "sessionId": "codex-session-id-or-null",
  "turnId": "codex-turn-id-or-null",
  "cwd": "/repo/path-or-null",
  "taskType": "coding",
  "setStatus": "working",
  "lastAssistantMessage": null,
  "sentAt": "2026-06-20T12:00:00Z"
}
```

For `done`, `event` is `"done"` and `lastAssistantMessage` contains Codex's
final assistant message when Codex provides it in the hook input. The hook always includes explicit action fields: `started` sends `setStatus: working`; `done` sends `setStatus: idle`; coding and reviewing runs also send `setTaskType`. Coding runs that are not blocked or partial request a `reviewing` follow-up with `createNextTaskType`.

## Runner command

Nina should invoke Codex like this from its external runner:

```bash
NINA_TASK_ID="$TASK_ID" NINA_RUN_ID="$RUN_ID" NINA_TASK_TYPE="$TASK_TYPE" NINA_BASE_URL="http://127.0.0.1:$NINA_PORT" NINA_TOKEN="$NINA_TOKEN" codex exec   --cd "$REPO_PATH"   --json   --skip-git-repo-check   --dangerously-bypass-approvals-and-sandbox   --dangerously-bypass-hook-trust   "Use @nina-task.

Nina task id: $TASK_ID
Nina run id: $RUN_ID
Nina task type: $TASK_TYPE

Task:
$TASK_BODY

When finished, provide a concise final report with an Outcome line, changed files, checks run, blockers, and a Decision line when the task type is reviewing."
```

`--dangerously-bypass-approvals-and-sandbox` and `--dangerously-bypass-hook-trust` are intended only for the controlled Nina
runner environment. For manual usage, review hooks with `/hooks` inside Codex.

## Install on another machine

From the repo root, run:

```bash
bash nina-codex-plugin/install.sh
codex plugin add nina-codex@personal
```

Then start a new Codex thread or run so the plugin is loaded.

The installer copies:

```text
nina-codex-plugin/files/nina-codex/
  -> ~/plugins/nina-codex/
```

It also creates or updates:

```text
~/.agents/plugins/marketplace.json
```

with a local marketplace entry for `nina-codex`.

## Files included

```text
nina-codex-plugin/files/
  marketplace.json
  nina-codex/
    .codex-plugin/plugin.json
    README.md
    hooks/hooks.json
    hooks/nina_hook.py
    skills/nina-task/SKILL.md
```

## Why hooks, not MCP

Hooks are the right v1 mechanism because Nina needs automatic lifecycle
callbacks. MCP would be useful later if Codex needs Nina as an explicit tool,
for example `nina_get_task`, `nina_add_comment`, or `nina_request_review`.

## Failure behavior

The hook exits successfully so Codex is not blocked by Nina callback failures.

If Nina is unavailable, unauthorized, or returns an error, the hook logs to
`stderr` and Codex continues.

If Codex is killed before `Stop`, Nina should not expect a `done` callback.
Nina's runner should handle process crash and timeout state separately.
