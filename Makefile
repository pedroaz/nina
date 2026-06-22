.PHONY: help build b build-all doctor uninstall format lint typecheck test test-unit test-integration check check-build smoke smoke-research dev-init dev dev-start dev-stop dev-status dev-logs daemon-start daemon-stop daemon-status daemon-logs cli c desktop d desktop-build desktop-native-libs desktop-install-icon desktop-check desktop-fmt desktop-clippy desktop-test desktop-bacon package package-cli package-desktop codex-plugin-install

PYTHON := uv run python
UV := uv
NINA_PROFILE ?= default
DEFAULT_CONFIG_DIR ?= $(HOME)/.nina/$(NINA_PROFILE)
NINA_DEV_ENV := NINA_PROFILE=$(NINA_PROFILE)
NINA_DESKTOP_NATIVE_LIB_DIR := $(CURDIR)/apps/desktop/.native-libs
NINA_DESKTOP_RUSTFLAGS := -L native=$(NINA_DESKTOP_NATIVE_LIB_DIR) $(RUSTFLAGS)
NINA_DESKTOP_ENV := NINA_PROFILE=$(NINA_PROFILE) RUST_FONTCONFIG_DLOPEN=1 RUSTFLAGS="$(NINA_DESKTOP_RUSTFLAGS)"
RESEARCH_TOPIC ?= modern mobile authentication patterns
CODEX_MODEL ?= gpt-5.5
RESEARCH_TIMEOUT ?= 600
PACKAGE_NAME ?= local
PACKAGE_COMPONENTS ?= all
PACKAGE_DIR ?= $(CURDIR)/release

help:
	@printf '%s\n' "Nina local build targets"
	@printf '%s\n' ""
	@printf '%s\n' "Build and install"
	@printf '  %-20s %s\n' "build, b" "Install the CLI/server locally and refresh the Codex plugin"
	@printf '  %-20s %s\n' "build-all" "Run build and build the desktop release binary"
	@printf '  %-20s %s\n' "desktop-build" "Build the GPUI desktop release binary for this host"
	@printf '  %-20s %s\n' "package" "Build local CLI and desktop archives under PACKAGE_DIR"
	@printf '  %-20s %s\n' "package-cli" "Build local CLI wheel archives only"
	@printf '  %-20s %s\n' "package-desktop" "Build the current-host desktop archive only"
	@printf '  %-20s %s\n' "doctor" "Check local launcher and PATH setup"
	@printf '  %-20s %s\n' "uninstall" "Remove local Nina runtime and data"
	@printf '%s\n' ""
	@printf '%s\n' "Run locally"
	@printf '  %-20s %s\n' "dev, dev-start" "Initialize the selected profile and start the daemon"
	@printf '  %-20s %s\n' "dev-stop" "Stop the selected profile daemon"
	@printf '  %-20s %s\n' "dev-status" "Show daemon status and health"
	@printf '  %-20s %s\n' "dev-logs" "Tail daemon logs"
	@printf '  %-20s %s\n' "cli, c ARGS=..." "Run the CLI against the selected profile"
	@printf '  %-20s %s\n' "desktop, d" "Run the GPUI desktop client"
	@printf '%s\n' ""
	@printf '%s\n' "Quality"
	@printf '  %-20s %s\n' "format" "Format Python code with Ruff"
	@printf '  %-20s %s\n' "lint" "Run Ruff checks"
	@printf '  %-20s %s\n' "typecheck" "Run Pyright"
	@printf '  %-20s %s\n' "test" "Run unit and fast integration tests"
	@printf '  %-20s %s\n' "test-unit" "Run unit tests"
	@printf '  %-20s %s\n' "test-integration" "Run integration tests"
	@printf '  %-20s %s\n' "check" "Run format, lint, typecheck, and tests"
	@printf '  %-20s %s\n' "desktop-check" "Format, lint, and test the desktop client"
	@printf '  %-20s %s\n' "smoke" "Run local daemon smoke test"
	@printf '  %-20s %s\n' "smoke-research" "Run live Codex research smoke test"
	@printf '%s\n' ""
	@printf '%s\n' "Variables"
	@printf '  %-20s %s\n' "NINA_PROFILE" "$(NINA_PROFILE)"
	@printf '  %-20s %s\n' "PACKAGE_DIR" "$(PACKAGE_DIR)"
	@printf '  %-20s %s\n' "PACKAGE_NAME" "$(PACKAGE_NAME)"
	@printf '  %-20s %s\n' "PACKAGE_COMPONENTS" "$(PACKAGE_COMPONENTS)"

build:
	$(UV) sync --locked --python 3.12 --no-python-downloads
	$(PYTHON) scripts/sync_version.py
	$(PYTHON) scripts/nina_build.py
	$(MAKE) codex-plugin-install

check-python:
	@uv python find 3.12 --show-version >/dev/null

check-build: check-python
	$(UV) sync --locked --python 3.12 --no-python-downloads
	$(PYTHON) scripts/nina_build.py

b: build

build-all: build desktop-build

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

cli:
	$(NINA_DEV_ENV) uv run nina $(ARGS)

c: cli

desktop-native-libs:
	@sh scripts/desktop_native_libs.sh "$(NINA_DESKTOP_NATIVE_LIB_DIR)"

desktop-install-icon:
	@sh scripts/desktop_install_icon.sh

desktop: desktop-native-libs desktop-install-icon
	@cd apps/desktop && $(NINA_DESKTOP_ENV) cargo run

d: desktop

desktop-build: desktop-native-libs
	@cd apps/desktop && $(NINA_DESKTOP_ENV) cargo build --release --locked

desktop-fmt:
	@cd apps/desktop && cargo fmt

desktop-clippy: desktop-native-libs
	@cd apps/desktop && $(NINA_DESKTOP_ENV) cargo clippy --all-targets --all-features -- -D warnings

desktop-test: desktop-native-libs
	@cd apps/desktop && $(NINA_DESKTOP_ENV) cargo test

desktop-check: desktop-fmt desktop-clippy desktop-test

desktop-bacon: desktop-native-libs
	@cd apps/desktop && $(NINA_DESKTOP_ENV) bacon

package:
	@NINA_PACKAGE_NAME="$(PACKAGE_NAME)" NINA_PACKAGE_COMPONENTS="$(PACKAGE_COMPONENTS)" NINA_PACKAGE_DIR="$(PACKAGE_DIR)" sh scripts/release_assets.sh

package-cli:
	@$(MAKE) --no-print-directory package PACKAGE_COMPONENTS=cli

package-desktop:
	@$(MAKE) --no-print-directory package PACKAGE_COMPONENTS=desktop

codex-plugin-install:
	bash nina-codex-plugin/install.sh
	codex plugin add nina-codex@personal
