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

## setup: install tools in user space (make, JDK, fnm + Node, Python, project dependencies); idempotent
setup:
	tools/install-user-tools.sh
	uv sync --project tools
	uv sync --project backend
	npm ci --no-fund --no-audit

## dev: start backend, worker, admin, fakes locally (process list: dev/Procfile)
dev:
	$(TOOLS_PY) tools/dev.py

## test: all locally possible tests
test: test-tools test-backend test-js

test-tools:
	cd tools && uv run pytest -q

# DATABASE_URL selects SQLite (default) or MariaDB (A7).
test-backend:
	cd backend && uv run pytest -q

# Skipped until the Expo project exists (1.5).
test-js:
	@if [ -f app/package.json ]; then cd app && npm ci --no-fund --no-audit && npm test && npm run typecheck; \
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

## e2e: Playwright against a local instance (needs a browser: CI or notebook, not the home server)
e2e:
	npx --no-install playwright test -c e2e/playwright.config.ts

## apk: CI only (no Android SDK on the home server). Release build (JS bundled) signed with the
## debug key of the Expo template; real signing only in release.yml
apk:
	@if [ ! -f app/package.json ]; then echo "make apk: no Expo project yet (1.5)"; exit 1; fi
	@if [ -z "$${ANDROID_HOME:-}" ]; then echo "make apk: runs in CI only (needs the Android SDK)"; exit 1; fi
	cd app && npm ci --no-fund --no-audit && npx expo prebuild --platform android --no-install
	cd app/android && ./gradlew --no-daemon assembleRelease

## audit: pip-audit and npm audit (fail levels in tools/audit.sh)
audit:
	tools/audit.sh
