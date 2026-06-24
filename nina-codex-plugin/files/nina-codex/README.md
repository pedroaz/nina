# Nina Codex Plugin

Reports Nina task lifecycle events from Codex hooks.

## Runtime contract

Nina should start Codex with these environment variables:

```bash
NINA_TASK_ID=<task-id>
NINA_RUN_ID=<unique-run-id>
NINA_TASK_TYPE=<coding|reviewing>
NINA_PIPELINE_STAGE=<created|exploration|coding|testing|reviewing|done|blocked>
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
  "sessionId": "codex-session-id-or-null",
  "turnId": "codex-turn-id-or-null",
  "cwd": "/repo/path-or-null",
  "taskType": "coding",
  "pipelineStage": "coding",
  "setStatus": "working-or-idle",
  "setTaskType": "done-or-blocked",
  "setPipelineStage": "testing",
  "setPipelineError": "reason",
  "lastAssistantMessage": "Outcome: completed\nBlockers: ...",
  "sentAt": "..."
}
```

For `done`, the hook computes `setPipelineStage` from the task stage and final report:
- `created` -> `exploration`
- `exploration` -> `coding` (or `blocked`)
- `coding` -> `testing` (or `blocked`)
- `testing` -> `reviewing` (or `blocked`)
- `reviewing` -> `done` / `blocked`
- `blocked` outcome keeps `blocked`

The hook always includes explicit action fields for stage transitions so Nina can advance
`pipeline_stage` deterministically.

## Runner command

Nina should invoke Codex like this from its external runner:

```bash
NINA_TASK_ID="$TASK_ID" \
NINA_RUN_ID="$RUN_ID" \
NINA_TASK_TYPE="$TASK_TYPE" \
NINA_PIPELINE_STAGE="$PIPELINE_STAGE" \
NINA_BASE_URL="http://127.0.0.1:$NINA_PORT" \
NINA_TOKEN="$NINA_TOKEN" \
codex exec \
  --cd "$REPO_PATH" \
  --json \
  --skip-git-repo-check \
  --dangerously-bypass-approvals-and-sandbox \
  --dangerously-bypass-hook-trust \
  "Use @nina-task.

Nina task id: $TASK_ID
Nina run id: $RUN_ID
Nina task type: $TASK_TYPE
Nina pipeline stage: $PIPELINE_STAGE
Worktree: $REPO_PATH

Task:
$TASK_BODY

When finished, provide a concise final report with Outcome, Files, Checks, Blockers,
and Decision (when reviewing)."
```

## Notes

- Lifecycle reporting is automatic when Codex hooks are enabled for this plugin.
- Nina stores callbacks idempotently by `(taskId, runId, event)`.
- `started` sets task agent `status` to `working` and updates pipeline stage when provided.
- `done` sets task agent `status` to `idle`, applies `setPipelineStage`, and applies `setPipelineError` when blocking.
- `done` can still include explicit `setTaskType` for terminal transitions (`done`, `blocked`) and `createNextTaskType`.
- `done` now drives the new pipeline stages: `created -> exploration -> coding -> testing -> reviewing -> done` (or `blocked`).
- The hook exits successfully so Codex is not blocked by callback failures.
- If Codex is killed before `Stop`, Nina should handle process crash and timeout state separately.
- `done` is emitted from Codex `Stop`, which means a completed turn in this `codex exec` run.
