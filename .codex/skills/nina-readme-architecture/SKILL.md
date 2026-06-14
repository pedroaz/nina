---
name: nina-readme-architecture
description: Update Nina's README architecture section with Mermaid charts and communication diagrams. Use when the root README needs to explain how the CLI, TUI, and daemon relate, how they communicate over localhost, or how to show state ownership and SSE/REST boundaries.
---

# Nina README Architecture

## Overview

Use this skill to keep the root README architecture section aligned with the runtime model in `docs/02-architecture.md`, `docs/05-api-spec.md`, `docs/06-cli-spec.md`, and `docs/07-tui-spec.md`.

## Workflow

1. Read the current `README.md` architecture section and the architecture, API, CLI, and TUI docs.
2. Keep the daemon as the source of truth for all persistent state and writes.
3. Describe the CLI and TUI as clients that communicate with the daemon over `http://127.0.0.1:8765`.
4. Use Mermaid charts to make the boundaries explicit:
   - one flowchart for process ownership and data flow
   - one sequence diagram for request/response and TUI streaming
5. Label transport details accurately:
   - REST for reads and commands
   - SSE for `/events/stream`
   - Note CLI auto-start behavior when relevant.
6. Keep the README prose short. Do not invent new components or data paths.

## Diagram Rules

- Never show CLI or TUI writing SQLite or Markdown directly.
- Never imply direct CLI-to-TUI communication.
- Show persistent state, Obsidian writes, workflows, jobs, and LLM calls behind the daemon.
- Prefer exact endpoint names and localhost details when they clarify the boundary.
- Use `<br/>` inside Mermaid node labels when a multi-line label is necessary.
- If the runtime boundary changes, update the README to match the docs instead of inventing new behavior.
