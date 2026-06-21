# Nina Codex Plugin

Reports Nina task lifecycle events from Codex hooks.

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

The hook posts to:

```http
POST /codex/events
Authorization: Bearer <NINA_TOKEN>
Content-Type: application/json
```

Payload fields:

```json
{
  "version": 1,
  "event": "started|done",
  "source": "codex-hook",
  "taskId": "...",
  "runId": "...",
  "sessionId": "...",
  "turnId": "...",
  "cwd": "...",
  "taskType": "coding",
  "setStatus": "working-or-idle",
  "setTaskType": "done-or-blocked",
  "createNextTaskType": "reviewing",
  "lastAssistantMessage": "...",
  "sentAt": "..."
}
```

## Nina runner example

```bash
NINA_TASK_ID="$TASK_ID" NINA_RUN_ID="$RUN_ID" NINA_TASK_TYPE="$TASK_TYPE" NINA_BASE_URL="http://127.0.0.1:$NINA_PORT" NINA_TOKEN="$NINA_TOKEN" codex exec   --cd "$REPO_PATH"   --json   --skip-git-repo-check   --dangerously-bypass-approvals-and-sandbox   --dangerously-bypass-hook-trust   "Use @nina-task.

Nina task id: $TASK_ID
Nina run id: $RUN_ID
Nina task type: $TASK_TYPE

Task:
$TASK_BODY

When finished, provide a concise final report with an Outcome line, changed files, checks run, blockers, and a Decision line when the task type is reviewing."
```

## Notes

- Lifecycle reporting is automatic when Codex hooks are enabled for this plugin.
- Nina stores callbacks idempotently by `(taskId, runId, event)`.
- `started` sets task agent `status` to `working` and records the task type when present.
- `done` sets task agent `status` to `idle`.
- `done` applies explicit hook actions such as `setStatus`, `setTaskType`, and `createNextTaskType`.
- Coding completion, including missing or unparseable final reports, marks the task `done` and asks Nina to create a `reviewing` follow-up task. Blocked or partial coding reports mark it `blocked`.
- Reviewing completion marks the review task `done`; rejected, blocked, partial, missing, or unparseable review reports mark it `blocked`.
- The hook exits successfully even if Nina is unavailable, so Codex is not blocked by callback failures.
- `done` is emitted from Codex `Stop`, which means a completed turn in this `codex exec` run.
