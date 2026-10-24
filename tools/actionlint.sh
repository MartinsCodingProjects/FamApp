#!/usr/bin/env bash
# Runs a pinned actionlint on .github/workflows, downloaded once into .tools/ (gitignored).
set -euo pipefail

version="1.7.12"
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
bin="$root/.tools/actionlint-$version"

if [ ! -x "$bin" ]; then
  mkdir -p "$root/.tools"
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' EXIT
  curl -sSfL "https://github.com/rhysd/actionlint/releases/download/v$version/actionlint_${version}_linux_amd64.tar.gz" \
    | tar -xz -C "$tmp" actionlint
  mv "$tmp/actionlint" "$bin"
fi

cd "$root"
exec "$bin" "$@"
