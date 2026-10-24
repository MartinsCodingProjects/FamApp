# One command per task (BUILDPLAN A1, AGENTS.md section 4). Agents and CI use the same targets.
# Home server without make/java: run tools/install-user-tools.sh once and put ~/.local/bin on PATH.

SHELL := bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

TOOLS_PY := uv run --project tools python

.PHONY: help setup dev test lint tokens e2e apk audit lint-python lint-js lint-kotlin lint-tokens lint-strings \
	lint-arch lint-workflows test-tools test-backend test-js

help:
	@echo "make setup | dev | test | lint | tokens | e2e | apk | audit"

## setup: install tools in user space (1.3.1 adds the backend, app and engine toolchains)
setup:
	tools/install-user-tools.sh
	uv sync --project tools
	npm ci --no-fund --no-audit

## dev: start backend, worker, admin, fakes locally
dev:
	@echo "make dev: not built yet, added in package 1.3 (dev environment)"

## test: all locally possible tests
test: test-tools test-backend test-js

test-tools:
	cd tools && uv run pytest -q

# Placeholder until the backend project exists (1.3.2). DATABASE_URL selects SQLite or MariaDB (A7).
test-backend:
	@if [ -f backend/pyproject.toml ]; then cd backend && uv run pytest -q; \
	else echo "test-backend: no backend project yet (1.3.2), nothing to run"; fi

# Skipped until the Expo project exists (1.5).
test-js:
	@if [ -f app/package.json ]; then cd app && npm ci --no-fund --no-audit && npm test; \
	else echo "test-js: no Expo project yet (1.5), nothing to run"; fi

## lint: Ruff, ESLint, ktlint, token staleness, string checks, architecture checks, actionlint
lint: lint-python lint-js lint-kotlin lint-tokens lint-strings lint-arch lint-workflows

lint-python:
	uv run --project tools ruff check .
	uv run --project tools ruff format --check .

lint-js:
	npx --no-install eslint --max-warnings=0 .

lint-kotlin:
	tools/ktlint.sh

lint-tokens:
	$(TOOLS_PY) tools/tokens.py --check

lint-strings:
	$(TOOLS_PY) tools/strings_check.py

lint-arch:
	$(TOOLS_PY) tools/arch_check.py

lint-workflows:
	tools/actionlint.sh

## tokens: regenerate token files from shared/design/tokens.json
tokens:
	$(TOOLS_PY) tools/tokens.py

## e2e: Playwright against a local instance
e2e:
	@echo "make e2e: not built yet, added in package 1.9.7 (wizard E2E)"

## apk: CI only (no Android SDK on the home server); debug-signed APK
apk:
	@if [ ! -f app/package.json ]; then echo "make apk: no Expo project yet (1.5)"; exit 1; fi
	@if [ -z "$${ANDROID_HOME:-}" ]; then echo "make apk: runs in CI only (needs the Android SDK)"; exit 1; fi
	cd app && npm ci --no-fund --no-audit && npx expo prebuild --platform android --no-install
	cd app/android && ./gradlew --no-daemon assembleDebug

## audit: pip-audit and npm audit (fail levels in tools/audit.sh)
audit:
	tools/audit.sh
