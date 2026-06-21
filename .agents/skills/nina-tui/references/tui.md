# Nina TUI Reference

## Key Files

- `apps/tui/src/main.ts`: entry point.
- `apps/tui/src/app/shell.ts`: application shell and rendering flow.
- `apps/tui/src/app/pages.ts`: page definitions and page state.
- `apps/tui/src/app/keymap.ts`: keyboard behavior.
- `apps/tui/src/api/types.ts`: API-facing types.
- `apps/tui/src/ui/theme.ts`: visual tokens.

## Client Boundary

- Keep the TUI client-only.
- Read and write through daemon API calls.
- Do not write SQLite, config files, or Obsidian Markdown directly from the TUI.
- Reuse API types and narrow data mappers instead of duplicating server models loosely.

## Interaction Rules

- Keep screens dense, utilitarian, and scan-friendly.
- Prefer predictable keyboard navigation over decorative behavior.
- Keep key bindings centralized in `keymap.ts` and covered by `keymap.test.ts`.
- Make page changes stable across terminal sizes. Avoid layout shifts from dynamic labels or counters.
- Surface daemon-offline and auth failures clearly without crashing the render loop.

## Validation

- Run `cd apps/tui && bun run check` for TypeScript changes.
- Run `cd apps/tui && bun test src` when changing tested keymap or client behavior.
- Run `make smoke` for TUI changes that depend on daemon profile setup or installed runtime behavior.

## API Expectations

- Load state from the daemon at startup and refresh points.
- Use live daemon runtime information where available.
- Keep user actions idempotent when practical so retries after transient daemon failures are safe.
