#!/usr/bin/env bash
# Emulator E2E suite (BUILDPLAN 1.2.11, 1.5.10), run by the CI `emulator` job inside a booted
# emulator: installs the APK from the `apk` job and runs every Maestro flow in app/e2e/.
# Usage: tools/emulator-suite.sh [path/to/app.apk]
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
apk="${1:-}"

adb wait-for-device
echo "emulator: API level $(adb shell getprop ro.build.version.sdk | tr -d '\r'), boot_completed=$(adb shell getprop sys.boot_completed | tr -d '\r')"

if [ ! -f "$root/app/package.json" ]; then
  echo "emulator suite: empty (no Expo project yet)"
  exit 0
fi
[ -n "$apk" ] && [ -f "$apk" ] || { echo "emulator suite: APK missing: '$apk'"; exit 1; }

adb install -r "$apk"
maestro="${MAESTRO_BIN:-$HOME/.maestro/bin/maestro}"
mkdir -p "$root/e2e-results"
"$maestro" test --format junit --output "$root/e2e-results/report.xml" \
  --test-output-dir "$root/e2e-results" "$root/app/e2e"
