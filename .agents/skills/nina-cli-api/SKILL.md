---
name: nina-cli-api
description: Nina local API, CLI commands, config, daemon runtime state, and auth. Use when working on apps/cli, apps/server, /config, /health, request routing, or command behavior.
---

# Nina CLI and API

Use this skill for Nina REST endpoints, Typer commands, daemon lifecycle, config updates, auth, and live runtime address resolution.

## Rules
- Route CLI command flow through the daemon API; do not import server internals into CLI command logic.
- Resolve the live daemon address from `daemon.json` in the config dir before falling back to `config.yaml`.
- Treat `config.yaml` as persisted next-start config and `daemon.json` as live runtime state.
- Use `nina config` for editable settings: vault, database, daemon host/port, log level, LLM provider/model, daily summary time.
- Sync config updates to the running daemon when possible and keep host/port/log level restart-required.
- Keep human output compact and `--json` machine-friendly.

## Read
- `references/cli-api.md` for command maps, endpoint maps, and config/runtime behavior.
