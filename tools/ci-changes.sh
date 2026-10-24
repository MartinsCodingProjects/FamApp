#!/usr/bin/env bash
# Change detection for CI (BUILDPLAN 1.2.1). Reads changed paths on stdin, or "--all" for a
# full run, and prints `<area>=true|false` lines for $GITHUB_OUTPUT.
# Areas: backend, app, shared, tools, docs. A change under .github/ counts as every area,
# so workflow changes always run the whole pipeline. Also prints has_backend / has_app
# (whether the project exists yet), used to skip jobs before 1.3.2 / 1.5.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
backend=false app=false shared=false tools=false docs=false

if [ "${1:-}" = "--all" ]; then
  backend=true app=true shared=true tools=true docs=true
else
  while IFS= read -r path || [ -n "$path" ]; do
    [ -n "$path" ] || continue
    case "$path" in
      .github/*) backend=true app=true shared=true tools=true docs=true ;;
      backend/* | deploy/* | docker-compose*.yml) backend=true ;;
      app/* | branding.json) app=true ;;
      shared/*) shared=true ;;
      tools/* | dev/* | Makefile | package.json | package-lock.json | ruff.toml | eslint.config.js | .editorconfig | .gitignore) tools=true ;;
      docs/* | *.md | LICENSE) docs=true ;;
      *) tools=true ;;  # unknown top-level file: run the cheap tool checks rather than nothing
    esac
  done
fi

echo "backend=$backend"
echo "app=$app"
echo "shared=$shared"
echo "tools=$tools"
echo "docs=$docs"
[ -f "$root/backend/pyproject.toml" ] && echo "has_backend=true" || echo "has_backend=false"
[ -f "$root/app/package.json" ] && echo "has_app=true" || echo "has_app=false"
