#!/usr/bin/env bash
# Prepares a booted emulator for capture: disables the display cutout, so
# screenshots contain only the game (D-014). adbd runs as root only while the
# overlay is changed and is always returned to shell (`adb unroot`).
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
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/cutout.sh"

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

unroot() {
    adb_device unroot >/dev/null || true
    adb_device wait-for-device
    if [[ "$(adb_device shell whoami | tr -d '\r')" != "shell" ]]; then
        echo "adb unroot failed; adbd is still root. Run: adb unroot" >&2
        exit 1
    fi
}
trap unroot EXIT

adb_device root >/dev/null
adb_device wait-for-device

adb_device shell cmd overlay disable "$CUTOUT_OVERLAY"

# The display picks up the change asynchronously; wait until the built-in
# screen reports no cutout insets.
for _ in $(seq 1 20); do
    if cutout_disabled; then
        echo "Emulator $serial: display cutout disabled; returning adbd to shell"
        exit 0
    fi
    sleep 0.5
done

echo "Display cutout is active or unknown" >&2
exit 1
