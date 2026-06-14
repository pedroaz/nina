.PHONY: help install install-cli i i-c uninstall format lint typecheck test test-unit test-integration check smoke dev-init dev-reset dev dev-start dev-stop dev-status dev-logs daemon-start daemon-stop daemon-status daemon-logs start stop status logs cli c tui t promote

PYTHON := uv run python
UV := uv
DEV_CONFIG_DIR ?= .tmp/nina-dev
REAL_CONFIG_DIR ?= $(HOME)/.nina/default
NINA_DEV_ENV := NINA_CONFIG_DIR=$(DEV_CONFIG_DIR)

help:
	@echo "Available targets:"
	@echo "  help              - List available commands"
	@echo "  install, i        - Install Python and TUI dependencies"
	@echo "  install-cli, i-c  - Symlink 'nina' into ~/.local/bin for PATH access"
	@echo "  uninstall         - Remove the symlink from ~/.local/bin"
	@echo "  format            - Format all code"
	@echo "  lint              - Static lint checks"
	@echo "  typecheck         - Type checking"
	@echo "  test              - Unit tests and fast integration tests"
	@echo "  test-unit         - Pure unit tests"
	@echo "  test-integration  - API, DB, Obsidian, CLI integration tests"
	@echo "  check             - Format check, lint, typecheck, tests"
	@echo "  smoke             - Fast end-to-end local smoke test against temp data"
	@echo "  dev, dev-start    - Initialize temp data and start daemon"
	@echo "  dev-stop          - Stop daemon using temp data"
	@echo "  dev-status        - Check daemon status and health"
	@echo "  dev-logs          - Tail daemon logs"
	@echo "  dev-init          - Initialize isolated dev config and vault"
	@echo "  dev-reset         - Delete isolated dev config, DB, and vault"
	@echo "  promote           - Copy temp data to real data with a backup"
	@echo "  cli, c ARGS=...   - Run CLI against isolated dev daemon"
	@echo "  tui, t            - Run TUI against isolated dev daemon"
	@echo ""
	@echo "Config variables:"
	@echo "  DEV_CONFIG_DIR=$(DEV_CONFIG_DIR)"
	@echo "  REAL_CONFIG_DIR=$(REAL_CONFIG_DIR)"

install:
	$(UV) sync
	cd apps/tui && bun install

i: install

install-cli: install
	@echo "Installing nina CLI to ~/.local/bin..."
	@mkdir -p $(HOME)/.local/bin
	@ln -sf $(PWD)/.venv/bin/nina $(HOME)/.local/bin/nina
	@echo "Done. Make sure ~/.local/bin is in your PATH."
	@echo "  Add $$HOME/.local/bin to PATH if needed."
	@echo "Test it: nina version"

i-c: install-cli

uninstall:
	@echo "Removing nina from ~/.local/bin..."
	@rm -f $(HOME)/.local/bin/nina
	@echo "Done."

format:
	$(UV) run ruff format .

lint:
	$(UV) run ruff check .

typecheck:
	$(UV) run pyright

test:
	$(UV) run pytest tests/

test-unit:
	$(UV) run pytest tests/ -m unit

test-integration:
	$(UV) run pytest tests/ -m integration

check: format lint typecheck test

smoke:
	$(PYTHON) scripts/nina_dev.py smoke --config-dir $(DEV_CONFIG_DIR)

dev-init:
	$(NINA_DEV_ENV) uv run nina init

dev-reset:
	$(PYTHON) scripts/nina_dev.py reset --config-dir $(DEV_CONFIG_DIR)

dev: dev-start

dev-start: dev-init daemon-start

dev-stop: daemon-stop

dev-status: daemon-status

dev-logs: daemon-logs

daemon-start:
	$(NINA_DEV_ENV) uv run nina daemon start

daemon-stop:
	$(NINA_DEV_ENV) uv run nina daemon stop

daemon-status:
	$(NINA_DEV_ENV) uv run nina daemon status
	@$(PYTHON) scripts/nina_dev.py health --config-dir $(DEV_CONFIG_DIR) || true

daemon-logs:
	tail -f $(DEV_CONFIG_DIR)/logs/daemon.log

start: daemon-start

stop: daemon-stop

status: daemon-status

logs: daemon-logs

cli:
	$(NINA_DEV_ENV) uv run nina $(ARGS)

c: cli

tui:
	@cd apps/tui && NINA_CONFIG_DIR=../../$(DEV_CONFIG_DIR) bun run src/main.ts

t: tui

promote:
	$(PYTHON) scripts/nina_dev.py promote --source $(DEV_CONFIG_DIR) --dest $(REAL_CONFIG_DIR)
