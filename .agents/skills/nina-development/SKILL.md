---
name: nina-development
description: Nina development workflow, validation commands, test strategy, build tooling, Makefile targets, packaging, and agent handoff expectations. Use when changing tests, CI-like checks, scripts, pyproject settings, Makefile behavior, build/install flow, or repo process documentation.
---

# Nina Development

Use this skill when a task is primarily about how Nina is built, checked, tested, packaged, or handed off.

## Rules

- Use `uv` for Python workspace commands.
- Use Bun for `apps/tui`.
- Keep tests isolated from real user config, real vaults, live daemon processes, and network credentials by default.
- Prefer the narrowest useful test first, then broaden when the change crosses module boundaries.
- Report skipped checks and the reason.

## Process

1. Read the affected test, script, Makefile target, or project config.
2. Preserve current developer workflow names unless the task is explicitly to rename or remove them.
3. Update docs that mention changed commands.
4. Run focused validation and broaden to `make check` when practical for repo-wide changes.

## References

- Read `references/development.md` for tooling, Make targets, test strategy, agent workflow, and dirty-worktree rules.
