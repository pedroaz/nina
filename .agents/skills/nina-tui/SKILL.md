---
name: nina-tui
description: Nina OpenTUI client pages, keyboard behavior, terminal layout, API client types, and daemon interaction. Use when working in apps/tui, changing TUI screens, key bindings, page state, rendering, client-side API calls, or TUI validation.
---

# Nina TUI

Use this skill for TUI implementation and validation.

## Rules

- Keep the TUI as a daemon API client.
- Keep key handling centralized and tested.
- Keep layout dense, terminal-friendly, and stable across common terminal sizes.
- Do not introduce direct database, config-file, or vault writes from TypeScript.
- Surface offline and error states as part of the interface.

## Process

1. Read the page, shell, keymap, API type, or theme file relevant to the task.
2. Preserve existing navigation patterns unless the task is to change them.
3. Update keymap tests when keyboard behavior changes.
4. Run Bun validation for TypeScript changes.

## References

- Read `references/tui.md` for key files, client boundary, interaction rules, validation, and API expectations.
