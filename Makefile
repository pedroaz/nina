.PHONY: help build b doctor uninstall format lint typecheck test test-unit test-integration check smoke smoke-research dev-init dev-reset dev dev-start dev-stop dev-status dev-logs daemon-start daemon-stop daemon-status daemon-logs start stop status logs cli c chat tui codex-plugin-install promote

PYTHON := uv run python
UV := uv
NINA_PROFILE ?= default
DEFAULT_CONFIG_DIR ?= $(HOME)/.nina/$(NINA_PROFILE)
NINA_DEV_ENV := NINA_PROFILE=$(NINA_PROFILE)
RESEARCH_TOPIC ?= modern mobile authentication patterns
CODEX_MODEL ?= gpt-5.5
RESEARCH_TIMEOUT ?= 600

help:
	@echo "Available targets:"
	@echo "  help              - List available commands"
	@echo "  build, b          - Build and install Nina, then refresh the Codex plugin"
	@echo "  doctor            - Check local Nina launcher and PATH setup"
	@echo "  uninstall         - Remove Nina launcher, install root, and data"
	@echo "  format            - Format all code"
	@echo "  lint              - Static lint checks"
	@echo "  typecheck         - Type checking"
	@echo "  test              - Unit tests and fast integration tests"
	@echo "  test-unit         - Pure unit tests"
	@echo "  test-integration  - API, DB, Obsidian, CLI integration tests"
	@echo "  check             - Format check, lint, typecheck, tests"
	@echo "  smoke             - End-to-end smoke test against the default profile"
	@echo "  smoke-research    - Live Codex research smoke via CLI and daemon"
	@echo "  dev, dev-start    - Initialize default profile and start daemon"
	@echo "  dev-stop          - Stop daemon for the default profile"
	@echo "  dev-status        - Check daemon status and health"
	@echo "  dev-logs          - Tail daemon logs"
	@echo "  dev-init          - Initialize default profile config and vault"
	@echo "  dev-reset         - Disabled; dev uses default profile data"
	@echo "  promote           - No-op; dev uses default profile data"
	@echo "  cli, c ARGS=...   - Run CLI against the default daemon"
	@echo "  tui               - Run TUI against the default daemon"
	@echo "  codex-plugin-install - Install or refresh the local Nina Codex plugin"
	@echo ""
	@echo "Config variables:"
	@echo "  NINA_PROFILE=$(NINA_PROFILE)"
	@echo "  DEFAULT_CONFIG_DIR=$(DEFAULT_CONFIG_DIR)"
	@echo "  CODEX_MODEL=$(CODEX_MODEL)"
	@echo "  RESEARCH_TOPIC=$(RESEARCH_TOPIC)"

build:
	$(UV) sync --locked --python 3.12 --no-python-downloads
	cd apps/tui && bun install --frozen-lockfile
	$(PYTHON) scripts/sync_version.py
	$(PYTHON) scripts/nina_build.py
	$(MAKE) codex-plugin-install

check-python:
	@uv python find 3.12 --show-version >/dev/null

check-build: check-python
	$(UV) sync --locked --python 3.12 --no-python-downloads
	$(PYTHON) scripts/nina_build.py

b: build

doctor:
	python3 scripts/nina_doctor.py

uninstall:
	$(UV) run nina uninstall

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

check: check-python format lint typecheck test

smoke:
	$(PYTHON) scripts/nina_dev.py smoke --profile $(NINA_PROFILE)

smoke-research:
	$(PYTHON) scripts/nina_dev.py research-smoke --profile $(NINA_PROFILE) --topic "$(RESEARCH_TOPIC)" --model "$(CODEX_MODEL)" --timeout $(RESEARCH_TIMEOUT)

dev-init:
	$(NINA_DEV_ENV) uv run nina init --profile $(NINA_PROFILE)

dev-reset:
	$(PYTHON) scripts/nina_dev.py reset --profile $(NINA_PROFILE)

dev: dev-start

dev-start: dev-init daemon-start

dev-stop: daemon-stop

dev-status: daemon-status

dev-logs: daemon-logs

daemon-start:
	$(NINA_DEV_ENV) uv run nina daemon start --profile $(NINA_PROFILE)

daemon-stop:
	$(NINA_DEV_ENV) uv run nina daemon stop --profile $(NINA_PROFILE)

daemon-status:
	$(NINA_DEV_ENV) uv run nina daemon status --profile $(NINA_PROFILE)
	@$(PYTHON) scripts/nina_dev.py health --profile $(NINA_PROFILE) || true

daemon-logs:
	tail -f $(DEFAULT_CONFIG_DIR)/logs/daemon.log

start: daemon-start

stop: daemon-stop

status: daemon-status

logs: daemon-logs

cli:
	$(NINA_DEV_ENV) uv run nina $(ARGS)

c: cli

PROMPT ?= Reply with ok

chat:
	$(UV) run python -m nina_cli.main chat test "$(PROMPT)"

tui:
	@cd apps/tui && NINA_PROFILE=$(NINA_PROFILE) bun run src/main.ts

codex-plugin-install:
	bash nina-codex-plugin/install.sh
	codex plugin add nina-codex@personal

promote:
	@echo "No temp dev config to promote; dev targets use $(DEFAULT_CONFIG_DIR)."
