#!/usr/bin/env bash
# Runs a pinned ktlint, downloaded once into .tools/ (gitignored). Needs Java
# (home server: tools/install-user-tools.sh; CI runners have it).
# Usage: tools/ktlint.sh [ktlint args]   (default: lint all Kotlin files)
set -euo pipefail

version="1.8.0"
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
jar="$root/.tools/ktlint-$version"

if [ ! -f "$jar" ]; then
  mkdir -p "$root/.tools"
  curl -sSfL "https://github.com/pinterest/ktlint/releases/download/$version/ktlint" -o "$jar.part"
  mv "$jar.part" "$jar"
fi

java_bin="java"
if ! command -v java >/dev/null 2>&1 && [ -x "$HOME/.local/jdk-21/bin/java" ]; then
  java_bin="$HOME/.local/jdk-21/bin/java"
fi

cd "$root"
if [ "$#" -eq 0 ]; then
  set -- "**/*.kt" "**/*.kts" "!**/build/**" "!**/node_modules/**" "!app/android/**"
fi
exec "$java_bin" -jar "$jar" --relative "$@"
