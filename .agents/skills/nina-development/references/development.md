# Nina Development Reference

## Tooling

- Python workspace uses `uv`.
- Python target is 3.12.
- Desktop uses Rust/Cargo under `apps/desktop`.
- Formatting and linting use Ruff.
- Type checking uses Pyright.

## Make Targets

- `make help`: list supported targets.
- `make build` or `make b`: sync Python dependencies, sync version, build Nina, and refresh the Codex plugin.
- `make doctor`: inspect local launcher and PATH setup.
- `make format`: run Ruff formatter.
- `make lint`: run Ruff checks.
- `make typecheck`: run Pyright.
- `make test`: run default Python tests.
- `make test-unit`: run unit tests.
- `make test-integration`: run integration tests.
- `make check`: Python version check, format, lint, typecheck, and tests.
- `make smoke`: end-to-end smoke against the selected/default profile.
- `make dev`, `make dev-start`, `make dev-stop`, `make dev-status`, `make dev-logs`: local daemon lifecycle.
- `make desktop` or `make d`: run the GPUI desktop client.
- `make desktop-build`: build the GPUI desktop release binary for the current host.
- `make desktop-check`: format, lint, and test the GPUI desktop client.
- `make package`: build local CLI archives and the current-host desktop archive under `release/assets`.
- `make package-cli` or `make package-desktop`: build only one local artifact family.
- `make codex-plugin-install`: install or refresh the local Nina Codex plugin.

## Test Strategy

- Unit tests should avoid real daemon processes, real user config, real vaults, and live network dependencies.
- Integration tests should use isolated SQLite/config/vault data where possible.
- The default test command excludes `daemon_smoke`.
- `daemon_smoke` binds `127.0.0.1:8765` and is opt-in.
- Desktop verification runs through `make desktop-check`.

## Agent Workflow

1. Read the nearest code and docs before editing.
2. Identify the smallest behavior that satisfies the task.
3. Add or update focused tests for shared behavior and regressions.
4. Implement through existing service/router/command boundaries.
5. Run the narrowest relevant check.
6. Escalate to `make test`, `make check`, or `make smoke` when the change crosses boundaries.
7. Report checks run and any skipped validation.

## Dirty Worktree Rules

- Assume unrelated modifications belong to the user.
- Do not revert deleted docs or skills unless the task requires recreating them.
- Before editing a modified file, read it and apply a minimal patch on top of the current contents.
