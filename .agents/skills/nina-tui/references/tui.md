# Nina TUI Reference

## Screens
- Tickets
- Chat
- Agent
- Research
- Jobs
- Config

## General Behavior
- Tab and Shift+Tab change pages.
- Esc returns focus to the tab strip when an input is active.
- Ctrl+L refreshes the current page.
- The TUI is a client only; it does not write SQLite or Markdown directly.
- Use SSE for live updates where possible.

## Config Page
- Show the resolved profile, config dir, config file, daemon health, vault path, database path, daemon host/port, LLM provider/model, daily summary time, and log level.
- Allow one setting to be edited at a time.
- Up and Down select the setting.
- Enter saves the value.
- The editor should call `GET /config` to load and `PATCH /config` to persist.
- Treat host, port, and log level changes as restart-required.

## Interaction Notes
- Use `SelectRenderable`, `InputRenderable`, and `TabSelectRenderable` patterns.
- Keep the page content dense enough for repeated scanning and editing.
- Keep the config view aligned with the daemon runtime file behavior used by the CLI.
