# Nina Planning Docs

Nina is a local-first personal operations platform for one user. It runs on a local machine, keeps operational state in SQLite, keeps durable knowledge in an Obsidian vault, and exposes three interfaces:

- Daemon/server: long-running local process that owns state, jobs, workflows, LLM calls, and Obsidian writes.
- CLI: fast terminal commands for common actions.
- TUI: interactive terminal UI for kanban, search, jobs, and review workflows.

The current target is a Linux-first monorepo. WSL support is acceptable later. Multi-user, remote access, permissions, and cloud-dependent core features are out of scope.

## Document Map

- [01-product-scope.md](01-product-scope.md): clarified V1 scope, non-goals, and critique of the original plan.
- [02-architecture.md](02-architecture.md): process model, monorepo layout, module boundaries, and runtime decisions.
- [03-storage-and-obsidian.md](03-storage-and-obsidian.md): SQLite/Obsidian responsibilities, vault layout, sync rules, and delete behavior.
- [04-database-schema.md](04-database-schema.md): initial relational schema and migration expectations.
- [05-api-spec.md](05-api-spec.md): local REST/SSE API used by CLI and TUI.
- [06-cli-spec.md](06-cli-spec.md): command-line interface design.
- [07-tui-spec.md](07-tui-spec.md): OpenTUI screen and interaction spec.
- [08-workflows-llm-scheduler.md](08-workflows-llm-scheduler.md): Python workflow engine, daily summary workflow, LLM logging, and jobs.
- [09-implementation-backlog.md](09-implementation-backlog.md): ordered executable backlog.
- [10-open-questions.md](10-open-questions.md): remaining decisions that should be resolved before or during implementation.
- [11-agentic-development.md](11-agentic-development.md): validation harness, Make targets, test layers, and agent workflow.

## V1 Summary

V1 should prove the whole product loop with a narrow but real slice:

1. Start a Nina daemon locally.
2. Initialize one profile and one new Obsidian vault.
3. Create projects and tasks from the CLI.
4. Manage a global kanban board in the TUI with keyboard controls.
5. Mirror useful task/project context into Markdown.
6. Index the vault with SQLite FTS.
7. Search notes and open results in Obsidian.
8. Call an OpenAI-compatible LLM provider through a provider boundary.
9. Log prompts and outputs.
10. Run the first workflow: summarize last day.

OpenCode, GitHub, Jira, meeting audio processing, semantic search, multiple profiles, and a general plugin system are later work.
