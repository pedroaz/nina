# Product Scope

## Vision

Nina is a local operating system for knowledge and work. It should help one person organize tasks, notes, project context, research, workflows, and LLM-assisted summaries without making cloud services mandatory for core use.

Nina is not intended to replace the user, own projects autonomously, or become a general autonomous agent. It coordinates information and workflows.

## Current User Decisions

- Primary user: one person.
- First platform: Linux.
- Windows support: WSL is acceptable.
- Runtime style: daemon plus CLI plus TUI.
- TUI: separate monorepo project using the OpenTUI library supplied by the user.
- Package/dependency manager: `uv` for Python.
- Knowledge layer: one new Obsidian vault created and managed by Nina.
- Runtime layer: SQLite.
- Profiles: one active local profile. Multi-profile is not supported yet.
- Core capabilities: kanban, LLM support, and Obsidian.
- Search: full-text search only.
- Scheduler: jobs should run while the TUI is closed.
- Workflow language: Python.
- First workflow: summarize last day.
- LLM provider: Codex auth/token by default, with explicit OpenAI API-key support for opt-in API use.

## Scope

Nina does not try to build the full platform. It builds the smallest complete product loop:

```text
CLI/TUI action
  -> local daemon API
  -> SQLite state change
  -> Obsidian Markdown update
  -> search index update
  -> optional LLM workflow
  -> visible job/workflow log
```

The feature set is:

- One local profile.
- Local daemon.
- CLI client.
- OpenTUI client.
- SQLite schema and migrations.
- Obsidian vault initialization.
- Projects.
- Tasks.
- Global kanban board.
- Full-text Markdown indexing.
- Search.
- OpenAI-compatible LLM provider abstraction.
- LLM prompt/output logging.
- Python workflow runner.
- Scheduler inside the daemon.
- Daily summary workflow.
- Job/workflow log view in the TUI.
- Tool-calling chat and agent sessions over the vault (see `docs/12-llm-tools.md`).

## Non-Goals

- Multiple simultaneous profiles.
- Multi-user auth or permissions.
- Remote access over the network.
- General plugin system.
- GitHub integration.
- Jira integration.
- OpenCode integration.
- Meeting audio transcription.
- Semantic/vector search.
- Custom user-authored workflows.
- Advanced task fields such as dependencies, estimates, and recurrence.
- Production-grade backup/export/import.

## Critique Of The Original Plan

The original plan has a good product direction, but it mixes current and future platform ideas. The biggest risk is building too many abstractions before the first daily-use loop works.

Specific corrections:

- Make the daemon the only writer to SQLite and Nina-managed Obsidian files.
- Treat CLI and TUI as clients, not separate implementations of business logic.
- Delay the plugin system until internal modules prove the extension shape.
- Delay OpenCode, GitHub, Jira, meetings, and semantic search.
- Add a local security boundary even though this is single-user.
- Add explicit sync rules between SQLite and Obsidian.
- Add workflow run persistence before building many workflows.
- Validate OpenTUI integration early because it may affect language/package layout.
