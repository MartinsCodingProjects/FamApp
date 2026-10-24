#!/usr/bin/env bash
# Dependency audits (BUILDPLAN 1.2.6). Fail levels (docs/assumptions.md):
#   pip-audit: any known vulnerability; npm audit: high or critical, minus the dated
#   exceptions in tools/audit-allowlist.txt.
# Covers every uv project (tools/, backend/) and npm lockfile (root, app/) that exists.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
status=0

for project in tools backend; do
  [ -f "$project/uv.lock" ] || continue
  echo "pip-audit: $project"
  uv export --project "$project" --frozen --all-groups --format requirements-txt -q -o "$tmp/$project.txt"
  uvx --quiet pip-audit@2.10.1 -r "$tmp/$project.txt" --disable-pip --require-hashes --progress-spinner off || status=1
done

for dir in . app; do
  [ -f "$dir/package-lock.json" ] || continue
  echo "npm audit: $dir"
  (cd "$dir" && npm audit --json || true) > "$tmp/npm-audit.json"
  python3 tools/npm_audit_gate.py "$tmp/npm-audit.json" tools/audit-allowlist.txt || status=1
done

exit "$status"
