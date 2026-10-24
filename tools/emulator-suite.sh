#!/usr/bin/env bash
# Emulator E2E suite (BUILDPLAN 1.2.11), run by the CI `emulator` job inside a booted emulator.
# Empty until the Expo project (1.5) and the engine E2E tests (Run 2) exist; for now it only
# proves the emulator boots with KVM.
set -euo pipefail

adb wait-for-device
echo "emulator: API level $(adb shell getprop ro.build.version.sdk | tr -d '\r'), boot_completed=$(adb shell getprop sys.boot_completed | tr -d '\r')"

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ ! -f "$root/app/package.json" ]; then
  echo "emulator suite: empty (no Expo project yet, added in 1.5)"
  exit 0
fi
echo "emulator suite: empty (tests are added with 1.5 and Run 2)"
