#!/usr/bin/env bash
# Prepends docs/last-session.md to docs/session-history.md (newest first).
# Run at the end of every session, after writing docs/last-session.md.
# Idempotent: an entry whose heading is already in the history is skipped.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
last="$root/docs/last-session.md"
history="$root/docs/session-history.md"
marker="<!-- entries below, newest first -->"

heading="$(head -n 1 "$last")"
if [[ "$heading" != "## Session "* ]]; then
  echo "error: first line of $last must start with '## Session '" >&2
  exit 1
fi

if grep -qxF -- "$heading" "$history"; then
  echo "already in history: $heading"
  exit 0
fi

if ! grep -qxF -- "$marker" "$history"; then
  echo "error: marker line missing in $history" >&2
  exit 1
fi

tmp="$(mktemp)"
awk -v marker="$marker" -v last="$last" '
  { print }
  $0 == marker {
    print ""
    while ((getline line < last) > 0) print line
    print ""
    print "---"
  }
' "$history" > "$tmp"
mv "$tmp" "$history"
echo "archived: $heading"
