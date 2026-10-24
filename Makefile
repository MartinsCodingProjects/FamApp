# One command per task (BUILDPLAN A1, AGENTS.md section 4). Agents and CI use the same targets.
# Home server without make/java: run tools/install-user-tools.sh once and put ~/.local/bin on PATH.

SHELL := bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

TOOLS_PY := uv run --project tools python

.PHONY: help setup dev test lint tokens e2e apk lint-python lint-js lint-kotlin lint-tokens lint-strings test-tools

help:
	@echo "make setup | dev | test | lint | tokens | e2e | apk"

## setup: install tools in user space (1.3.1 adds the backend, app and engine toolchains)
setup:
	tools/install-user-tools.sh
	uv sync --project tools
	npm ci --no-fund --no-audit

## dev: start backend, worker, admin, fakes locally
dev:
	@echo "make dev: not built yet, added in package 1.3 (dev environment)"

## test: all locally possible tests
test: test-tools

test-tools:
	cd tools && uv run pytest -q

## lint: Ruff, ESLint, ktlint, token staleness, string checks
lint: lint-python lint-js lint-kotlin lint-tokens lint-strings

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

## tokens: regenerate token files from shared/design/tokens.json
tokens:
	$(TOOLS_PY) tools/tokens.py

## e2e: Playwright against a local instance
e2e:
	@echo "make e2e: not built yet, added in package 1.9.7 (wizard E2E)"

## apk: CI only
apk:
	@echo "make apk: runs in CI only (APK build job, package 1.2.8); there is no Android SDK on the home server"
