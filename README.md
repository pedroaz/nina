# Nina

Nina is a local-first personal operations platform. It runs a daemon on your machine, stores operational state in SQLite, mirrors useful context into an Obsidian vault, and exposes the same data through a CLI and a terminal UI.

It is designed for one person's workflow, not a multi-user SaaS.

## What Nina Does

- Manage projects and tasks through a kanban board.
- Create tickets from the CLI, TUI, or agent mode.
- Ask questions in chat mode without running commands.
- Use agent mode to plan and auto-run safe `nina` commands.
- Run research workflows that write summary-plus-links notes into Obsidian.
- Index the vault for fast local search.
- Persist LLM interactions and workflow runs for inspection.

## Current Surface

- **Daemon**: FastAPI server that owns SQLite, Obsidian writes, LLM calls, workflows, jobs, and session state.
- **CLI**: Typer-based commands for `project`, `task`, `ticket`, `job`, `research`, `workflow`, `ask`, and `daemon`.
- **TUI**: OpenTUI terminal interface with dedicated `Tickets`, `Chat`, `Agent`, `Research`, `Jobs`, and `Config` tabs.
- **Core**: Shared models, database, search, Obsidian, LLM, research, session, and workflow services.

## Modes

### Tickets

Ticket mode is a first-class alias over Nina tasks. You can create, list, move, and complete tickets from the CLI or TUI while the underlying storage remains the same task model.

Example:

```bash
nina ticket create "Fix daemon stop recursion" --description "POSIX stop handling was recursing instead of terminating."
nina ticket move <ticket-id> --column Doing
nina ticket done <ticket-id>
```

### Chat

Chat mode answers questions with local Obsidian context and LLM reasoning. It does not execute CLI commands.

Example:

```bash
nina tui
# open the Chat tab and ask a question
```

### Agent

Agent mode can use an LLM to plan a sequence of `nina` commands and auto-run them. It never runs arbitrary shell commands.

This is the path for natural-language task creation:

```text
Create a ticket to fix daemon stop and put it in Doing.
```

Agent mode should be able to translate that into ticket creation plus any follow-up `nina` command needed to move the item.

### Research

Research mode uses OpenAI web search for live lookup and writes a Markdown note into Obsidian containing a summary and source links.

Example:

```bash
nina research run "OpenAI web search"
```

The generated note lands under `Research/YYYY-MM-DD - <topic>.md`.

## Architecture

- `apps/server`: FastAPI daemon that owns the runtime and exposes the local API.
- `apps/cli`: Typer CLI that talks to the daemon over HTTP.
- `apps/tui`: OpenTUI client that talks to the daemon over HTTP.
- `packages/nina_core`: shared application logic, models, services, and workflows.

The daemon is the source of truth for state. The CLI and TUI are clients.

## Installation

### Prerequisites

- Python 3.12+
- `uv`
- `bun`
- An Obsidian vault path
- Codex CLI auth for chat and agent mode
- An OpenAI API key for research mode

### Setup

```bash
uv sync
cd apps/tui && bun install
uv run nina init
```

That creates the local Nina profile, SQLite database, token, and vault structure.

## Quick Start

Start the daemon:

```bash
uv run nina daemon start
```

Check health:

```bash
uv run nina daemon status
```

Create a ticket:

```bash
uv run nina ticket create "Write the README" --description "Document the daemon, CLI, TUI, chat, agent, and research flows."
```

Ask a question:

```bash
uv run nina ask "What is already in the vault about Codex auth?"
```

Run a research topic:

```bash
uv run nina research run "OpenAI web search"
```

Launch the TUI:

```bash
uv run nina tui
```

## Configuration

Nina uses `NINA_CONFIG_DIR` to point at a profile directory. If it is not set, the default profile lives under `~/.nina/default`.

Useful environment variables:

- `NINA_CONFIG_DIR`: profile directory used by the CLI, daemon, and TUI.
- `NINA_LLM_PROVIDER`: LLM provider for chat and agent mode. Default: `codex`.
- `NINA_CODEX_COMMAND`: command used by the Codex provider.
- `NINA_CODEX_TIMEOUT_SECONDS`: timeout for Codex CLI calls.
- `OPENAI_API_KEY`: required for research mode.
- `NINA_RESEARCH_PROVIDER`: research backend. Default: `openai_web`.
- `NINA_RESEARCH_MODEL`: model used for research requests.
- `NINA_LLM_MODEL`: model used for general LLM calls.

The generated config file currently records paths and default settings, but runtime provider selection is primarily environment-driven.

## Obsidian Integration

Nina writes Markdown into the vault so the notes stay portable.

Current folders created by `nina init`:

- `Projects/`
- `Tasks/`
- `Research/`
- `Research/Sources/`
- `Daily/`
- `Templates/`
- `System/`
- `System/Deleted/`
- `System/Indexes/`
- `System/Logs/`

Research notes include:

- a Markdown summary
- source links
- frontmatter with `nina_type: research_report`
- the research topic
- the workflow run ID

## Development

Useful Make targets:

```bash
make help
make install
make dev
make smoke
make check
make tui
```

Common direct commands:

```bash
uv run pytest tests/
uv run pytest tests/ -m unit
uv run pytest tests/ -m integration
cd apps/tui && bun run check
```

## Validation

The repository is meant to be validated in layers:

- `uv run pytest tests/` for the Python suite.
- `cd apps/tui && bun run check` for the TUI TypeScript check.
- `make smoke` for the temp-data end-to-end flow.

The smoke path initializes isolated data, starts the daemon, creates a ticket, lists tickets, checks the TUI typecheck, and shuts the daemon down again.

## Roadmap

Current implementation is usable but still early. Likely next steps include:

- richer TUI interactions and keyboard shortcuts
- SearxNG as an additional research backend
- richer ticket workflows and templates
- note opening and external-editor integrations
- better LLM streaming and tool-call visibility in the TUI

## Contributing

Issues and pull requests should include a short description of the user flow being improved and the validation commands used to prove it.

If you add a new feature, update the README and the relevant tests in the same change.

## License

MIT.
