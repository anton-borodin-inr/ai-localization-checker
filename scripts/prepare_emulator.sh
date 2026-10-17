#!/usr/bin/env bash
# Prepares a booted emulator for capture: restarts adbd as root and disables
# the display cutout, so screenshots contain only the game (D-014).
#
# The emulator re-enables the Pixel 7 emulation overlay on every boot, so this
# must be run after each emulator start. See docs/environment.md.
#
# Usage (emulator must be running): scripts/prepare_emulator.sh

set -euo pipefail

# The only resource this overlay changes is config_mainBuiltInDisplayCutout.
CUTOUT_OVERLAY=com.android.internal.emulation.pixel_7

ANDROID_HOME="${ANDROID_HOME:-$HOME/Library/Android/sdk}"
ADB="$ANDROID_HOME/platform-tools/adb"

serial="$("$ADB" devices | awk '$1 ~ /^emulator-/ && $2 == "device" {print $1; exit}')"
if [[ -z "$serial" ]]; then
    echo "No emulator attached. Start it first: emulator -avd unciv_api34" >&2
    exit 1
fi
adb_device() { "$ADB" -s "$serial" "$@"; }

adb_device wait-for-device
until [[ "$(adb_device shell getprop sys.boot_completed | tr -d '\r')" == "1" ]]; do
    sleep 1
done

adb_device root >/dev/null
adb_device wait-for-device

adb_device shell cmd overlay disable "$CUTOUT_OVERLAY"

# The display picks up the change asynchronously; wait until the built-in
# screen reports no cutout insets.
for _ in $(seq 1 20); do
    insets="$(adb_device shell dumpsys display | grep -m1 'Built-in Screen' \
        | grep -o 'cutout DisplayCutout{insets=Rect([^)]*)' || true)"
    if [[ -z "$insets" || "$insets" == *"Rect(0, 0 - 0, 0)" ]]; then
        echo "Emulator $serial ready: adbd is root, display cutout disabled"
        exit 0
    fi
    sleep 0.5
done

echo "Display cutout is still active: $insets" >&2
exit 1
