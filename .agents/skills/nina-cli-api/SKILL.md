---
name: nina-cli-api
description: Nina CLI commands, FastAPI daemon routers, schemas, auth, config, daemon runtime state, and local API contracts. Use when working in apps/cli, apps/server, command behavior, endpoint behavior, profile/config resolution, request output, or daemon lifecycle code.
---

# Nina CLI API

Use this skill when a task touches Nina's command line, local daemon API, auth, config, status, or profile behavior.

## Rules

- Route feature behavior through the daemon API.
- Keep command groups thin and output-focused.
- Keep server routers thin and delegate domain behavior to `nina_core` services.
- Preserve bearer-token auth on protected routes.
- Keep plain output concise and JSON output stable.

## Process

1. Read the relevant CLI command, API helper, router, schema, and core service.
2. Identify the public command or endpoint contract before editing.
3. Update matching CLI, router, schema, tests, and docs together when behavior changes.
4. Use focused CLI or daemon integration tests for verification.

## References

- Read `references/cli-api.md` for key files, CLI contracts, daemon addressing, config rules, API map, and test targets.
