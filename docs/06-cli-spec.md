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

`--profile` exists for future compatibility but V1 only supports `default`.

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

```text
nina project list
nina project create "Supplier onboarding" --description "..."
nina project show <project-id>
nina project update <project-id> --name "..."
nina project delete <project-id>
```

## Task Commands

```text
nina task list
nina task create "Draft plan" --project <project-id> --description "..."
nina task show <task-id>
nina task update <task-id> --title "..." --description "..."
nina task move <task-id> --column Doing --position 0
nina task done <task-id>
nina task delete <task-id>
```

## Kanban Commands

```text
nina kanban show
nina kanban move <task-id> --to Doing --position 2
```

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
