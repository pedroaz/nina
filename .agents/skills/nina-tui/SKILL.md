---
name: nina-tui
description: Nina TUI screens, keyboard behavior, settings editing, and SSE updates. Use when working on apps/tui, OpenTUI render state, or client-side page interactions.
---

# Nina TUI

Use this skill for the OpenTUI client, page layout, keyboard and mouse handling, SSE refresh, and the editable Settings page.

## Rules
- Keep the TUI client-only; all writes go through the daemon API.
- Keep screens dense, utilitarian, and scan-friendly.
- Use the live daemon address from runtime state before the saved config fallback.
- Use `GET /config` for the Settings page and `PATCH /config` for edits.
- Surface restart-required behavior for daemon host, daemon port, and log level changes.
- Prefer predictable keyboard navigation over decorative interaction.

## Read
- `references/tui.md` for page behavior, key bindings, and the settings editor contract.
