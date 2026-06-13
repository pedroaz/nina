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
nina tui
```

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
nina search open <result-id>
```

For plain output, search results should show a numbered list. With `--json`, return structured result objects.

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

## Output Rules

- Human output should be compact.
- Every mutating command should print the changed entity ID.
- `--json` should make output script-friendly.
- Commands should fail with non-zero exit codes.
- If the daemon is not running, commands may auto-start it unless `--no-start-daemon` is added later.
