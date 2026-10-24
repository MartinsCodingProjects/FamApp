#!/usr/bin/env bash
# Runs pinned actionlint + shellcheck on .github/workflows, downloaded once into .tools/
# (gitignored). Pinning shellcheck keeps the home server and CI runners on the same checks.
set -euo pipefail

actionlint_version="1.7.12"
shellcheck_version="0.11.0"
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
actionlint="$root/.tools/actionlint-$actionlint_version"
shellcheck="$root/.tools/shellcheck-$shellcheck_version"

if [ ! -x "$actionlint" ] || [ ! -x "$shellcheck" ]; then
  mkdir -p "$root/.tools"
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' EXIT
  curl -sSfL "https://github.com/rhysd/actionlint/releases/download/v$actionlint_version/actionlint_${actionlint_version}_linux_amd64.tar.gz" \
    | tar -xz -C "$tmp" actionlint
  mv "$tmp/actionlint" "$actionlint"
  curl -sSfL "https://github.com/koalaman/shellcheck/releases/download/v$shellcheck_version/shellcheck-v$shellcheck_version.linux.x86_64.tar.gz" \
    | tar -xz -C "$tmp"
  mv "$tmp/shellcheck-v$shellcheck_version/shellcheck" "$shellcheck"
fi

cd "$root"
exec "$actionlint" -shellcheck="$shellcheck" "$@"
