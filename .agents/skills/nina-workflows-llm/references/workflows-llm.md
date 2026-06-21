# Nina Workflows and LLM Reference

## Key Files

- `packages/nina_core/nina_core/llm/`: provider boundary, tools, write tools, default tool registry, transcription checks.
- `packages/nina_core/nina_core/sessions/service.py`: chat and agent session loop.
- `packages/nina_core/nina_core/workflows/runner.py`: workflow execution.
- `packages/nina_core/nina_core/scheduler/service.py`: scheduled jobs.
- `packages/nina_core/nina_core/research/service.py`: research report generation.
- `packages/nina_core/nina_core/search/`: FTS, embeddings, hybrid search, and watcher.
- `packages/nina_core/nina_core/meetings/`: recording, transcription, and meeting-note pipeline.

## LLM Provider Rules

- Codex CLI is the default provider path.
- Keep provider-specific code inside `nina_core.llm`.
- Do not assume Codex CLI auth, OpenAI API keys, and local OpenAI-compatible runtimes are interchangeable.
- Store provider, model, purpose, prompt/messages, response, status, error, and timing for inspectability.
- Keep chat read-only by tool exposure; write tools belong to agent-like paths.

## Tool and Session Rules

- Validate tool arguments at the handler boundary.
- Enforce path safety for note and Obsidian operations: no traversal, no writes outside the vault, and no writes to protected system folders unless explicitly intended.
- Persist user, tool, and assistant messages consistently so multi-turn context can be reconstructed.
- Respect cancellation between LLM/tool iterations.

## Workflow and Job Rules

- Workflows are Python code, not user-authored YAML.
- Persist workflow runs, steps, job definitions, and job runs in SQLite.
- Mark stale in-flight runs on startup rather than pretending they completed.
- Keep scheduled work restart-tolerant, but do not imply resumability unless implemented.

## Search and Research Rules

- Search should combine lexical and semantic results only when embeddings are available.
- Indexing should tolerate individual bad notes and report useful errors.
- Research notes should include a concise summary, source links, and frontmatter that ties the note to Nina metadata.

## Meeting Pipeline Rules

- Recording writes audio under the active profile.
- Transcription is local by default through the configured backend.
- Summarization uses the configured LLM provider.
- Meeting notes should include transcript, summary, action items, decisions, and metadata needed for future search.
