# Dev Ops Todo

## Completed In This Pass

- Add short Make aliases for install, CLI install, temp dev lifecycle, CLI, and TUI.
- Add temp-data smoke test covering init, daemon health, CLI task round trip, and TUI typecheck.
- Add temp-to-real promotion command with a timestamped backup of existing real data.
- Fix TUI package scripts to point at `src/main.ts` instead of missing `src/main.tsx`.
- Add an explicit TTY guard to the TUI so it fails clearly when launched from a non-interactive shell.

## Remaining

- Add real OpenTUI visual tests using `@opentui/core/testing` instead of only TypeScript checks.
- Make daemon port configurable per profile to allow temp and real daemons at the same time.
- Add CLI commands for kanban/search/workflows/jobs that are already present in the API.
- Add daemon stale PID cleanup and port-conflict diagnostics.
- Package `nina tui` so it works after installation outside the source checkout.
