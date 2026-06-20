# CLI Spec

Use Typer unless implementation proves another CLI library is simpler. Commands should call the local daemon API.

Binary name:

```text
nina
```

Global options:

```text
--config PATH
--json
--profile default
```

`--profile` exists for future compatibility, but only `default` is supported.

## Core Commands

```text
nina init
nina daemon start
nina daemon stop
nina daemon status
nina status
nina tui
```

Short aliases:

- `nina d` for `nina daemon`
- `nina d r` for `nina daemon restart`
- `nina t` for `nina tui`

`nina status` reports daemon health, Codex OAuth status, and the resolved config paths.

`nina init` creates:

- config directory.
- config file.
- local API token.
- SQLite database.
- Obsidian vault folders.
- initial migrations.

## Project Commands

Nina no longer ships a `nina project` subcommand. Project identity is owned
by the supervised opencode server; see `nina opencode projects ...` below.

## Task Commands

```text
nina task list [--type unclassified] [--status idle]
nina task create "Draft plan" --opencode-project-id <id> --description "..." [--type coding] [--no-classify]
nina task show <task-id>
nina task update <task-id> --title "..." --description "..."
nina task type <task-id> <task-type>     # set task_type directly, bypassing the AI
nina task classify <task-id>             # re-run the AI classifier
nina task run <task-id>                  # route to the task's handler (placeholder for now)
nina task board                          # show the type-grouped view
nina task archive <task-id>
nina task unarchive <task-id>
nina task delete <task-id>
```

`nina task create` accepts `--opencode-project-id <id>` to attach the task to
an opencode worktree. The id is the server-assigned value from
`nina opencode projects list`.

`nina task type` accepts one of `unclassified`, `reminder`, `research`,
`coding`, `blocked`, `done`, `human`. It bypasses the LLM and is the right
choice when the user knows better than the classifier.

`nina task classify` is the LLM path. It re-runs the classifier workflow and
patches the task's `task_type`, `classified_at`, `classification_reason`, and
`classification_model` fields.

`nina task run` runs the `run-task` workflow. For `human`, `reminder`, and
`blocked` tasks it prints a "skipped" message; for `done` it is a no-op. For
`coding` it routes to the agent placeholder; for `research` it routes to the
research-topic workflow placeholder.

## Opencode Commands

The Nina daemon supervises an `opencode serve` child. These commands are
client views onto the supervisor's state and onto the opencode server's
project list.

```text
nina opencode status
nina opencode projects list
nina opencode projects current
```

`nina opencode status` prints the supervisor's view of the opencode child:
state (`disabled`, `not_installed`, `starting`, `running`, `stopped`,
`failed`), version, pid, host/port, uptime, and the resolved binary path.
Add `--json` for a machine-friendly payload.

`nina opencode projects list` prints a table with `ID | Worktree | VCS |
Created | Updated`. Add `--json` for the same shape as `GET /opencode/projects`.

`nina opencode projects current` prints the single project the opencode
server considers current. Same `--json` flag.

The sub-app alias is `oc` (`nina oc status`).

## Search Commands

## Search Commands

```text
nina search "supplier onboarding"
nina search reindex
nina search reindex-embeddings
nina search open <result-id>
```

For plain output, search results should show a numbered list. With `--json`, return structured result objects.

`nina search reindex-embeddings` walks the vault and re-embeds any note
whose `content_hash` changed since the last successful embed. It uses the
embedding provider configured by `NINA_EMBEDDING_PROVIDER` (`fastembed` by
default).

## Note Commands

```text
nina note list [--folder ...] [--type ...] [--limit N] [--json]
nina note show <path> [--json]
nina note create <path> --body "..." [--type ...] [--from-file FILE]
nina note append <path> --body "..." [--from-file FILE]
nina note update <path> --body "..." [--from-file FILE]
nina note open <path>
```

These are convenience wrappers around `GET /notes*` and `POST/PATCH /notes`.
The same handlers are also exposed as LLM tools to the agent session
(`notes_create`, `notes_append`, `notes_update`).

## Workflow Commands

```text
nina workflow list
nina workflow run summarize-last-day
nina workflow runs
nina workflow show <run-id>
```

## Job Commands

```text
nina job list
nina job enable daily-summary
nina job disable daily-summary
nina job run daily-summary
nina job runs
```

## LLM Commands

```text
nina llm test "Summarize the current kanban board."
nina llm logs
nina llm show <interaction-id>
```

## Provider Commands

```text
nina providers
nina providers list
nina providers show <model-substring>
nina providers refresh [--provider ...] [--source <provider>:<path>]
```

`nina providers` reads the cached pricing for each supported provider and
prints a Rich table with columns: `Provider | Model | Input $/1M | Output
$/1M | Cache Read | Cache Write | Fetched`. The row matching
`config.llm.model` is highlighted. With `--json`, the table is replaced by
a JSON document.

`nina providers show <substring>` filters rows whose model name contains
the substring across providers. `--provider <name>` and `--model
<substring>` work on every subcommand.

`nina providers refresh` fetches the public pricing pages and writes the
result to `$NINA_CONFIG_DIR/provider_pricing.json`. The first run requires
an explicit refresh; an empty cache prints a hint instead of fetching.
The supported providers today are:

- `claude` — `https://platform.claude.com/docs/en/about-claude/pricing`
- `openai` — `https://platform.openai.com/docs/pricing`

If a page is unreachable (or you want to pin a snapshot), pass
`--source <provider>:<path>` to read a saved HTML file instead of hitting
the network. The path can be repeated to mix sources across providers.

## Config Commands

```text
nina config show
nina config vault <path>
nina config database <path>
nina config daemon-host <host>
nina config daemon-port <port>
nina config log-level <level>
nina config llm-provider <provider>
nina config llm-model <model>
nina config daily-summary-time <HH:MM>
```

`nina config show` prints the resolved config values. Mutating config commands update the file on disk and, when possible, sync the running daemon. Host, port, and log level changes still require a daemon restart to take effect on the live listener.

## Output Rules

- Human output should be compact.
- Every mutating command should print the changed entity ID.
- `--json` should make output script-friendly.
- Commands should fail with non-zero exit codes.
- If the daemon is not running, commands may auto-start it unless `--no-start-daemon` is added later.
