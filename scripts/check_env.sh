#!/usr/bin/env bash
# Checks the capture environment described in docs/environment.md.
# Prints PASS/FAIL per item and exits 1 if any check fails, or 2 on invalid
# input before any check runs.
# Read-only except for the adb-root check, which restarts adbd as root and then
# back as shell (`adb unroot`).
#
# Usage (emulator must be running):
#   scripts/check_env.sh                   expect the default manifest's build
#   scripts/check_env.sh --manifest PATH   expect that manifest's build
#   scripts/check_env.sh --version-code N  expect N (Stage 0: 1271)

set -u

# Expected values. Keep in sync with docs/environment.md.
JAVA_MAJOR=17
SYSTEM_IMAGE="system-images;android-34;google_apis;arm64-v8a"
AVD_NAME=unciv_api34
AVD_WIDTH=1080
AVD_HEIGHT=2400
AVD_DENSITY=420
UNCIV_PACKAGE=com.unciv.app
DEFAULT_MANIFEST=fixtures/stage2/screens-v2.json

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

usage_error() {
    echo "check_env.sh: $1" >&2
    echo "Usage: scripts/check_env.sh [--manifest PATH | --version-code N]" >&2
    exit 2
}

# Prints a manifest's build.version_code, or an error on stderr and exits non-zero.
manifest_version_code() {
    python3 -I -c '
import json, re, sys

try:
    with open(sys.argv[1], encoding="utf-8") as file:
        code = json.load(file)["build"]["version_code"]
except (OSError, ValueError, KeyError, TypeError) as error:
    sys.exit(f"cannot read build.version_code: {error!r}")
if not isinstance(code, str) or not re.fullmatch(r"[0-9]+", code):
    sys.exit(f"invalid build.version_code: {code!r}")
print(code)
' "$1"
}

manifest_given=0
version_code_given=0
while (($# > 0)); do
    case "$1" in
        --manifest)
            (($# >= 2)) || usage_error "$1 needs a value"
            manifest_given=1
            manifest="$2"
            shift 2
            ;;
        --version-code)
            (($# >= 2)) || usage_error "$1 needs a value"
            version_code_given=1
            expected_version_code="$2"
            shift 2
            ;;
        *) usage_error "unknown argument: $1" ;;
    esac
done

if ((manifest_given && version_code_given)); then
    usage_error "--manifest and --version-code are mutually exclusive"
fi
if ((version_code_given)); then
    [[ "$expected_version_code" =~ ^[0-9]+$ ]] \
        || usage_error "--version-code must be digits: '$expected_version_code'"
    expected_source="--version-code"
else
    if ((manifest_given)); then
        manifest_path="$manifest"
        expected_source="$manifest"
    else
        manifest_path="$REPO_ROOT/$DEFAULT_MANIFEST"
        expected_source="$DEFAULT_MANIFEST"
    fi
    command -v python3 >/dev/null \
        || usage_error "python3 is needed to read '$expected_source'; or pass --version-code"
    expected_version_code="$(manifest_version_code "$manifest_path")" \
        || usage_error "bad manifest '$expected_source'"
fi

ANDROID_HOME="${ANDROID_HOME:-$HOME/Library/Android/sdk}"
ADB="$ANDROID_HOME/platform-tools/adb"
SDK_IMAGE_DIR="$ANDROID_HOME/$(echo "$SYSTEM_IMAGE" | tr ';' '/')"
AVD_CONFIG="$HOME/.android/avd/$AVD_NAME.avd/config.ini"
source "$REPO_ROOT/scripts/cutout.sh"

failures=0

pass() { printf 'PASS  %-22s %s\n' "$1" "$2"; }
fail() { printf 'FAIL  %-22s %s\n' "$1" "$2"; failures=$((failures + 1)); }

# Prints Pkg.Revision from an SDK package's source.properties, or nothing.
pkg_revision() { grep -s '^Pkg.Revision=' "$1/source.properties" | cut -d= -f2; }

# Prints a key's value from the AVD config.ini, or nothing.
avd_value() { grep -s "^$1=" "$AVD_CONFIG" | cut -d= -f2; }

# --- JDK ---
if java_home="$(/usr/libexec/java_home -v "$JAVA_MAJOR" 2>/dev/null)"; then
    java_version="$("$java_home/bin/java" -version 2>&1 | head -1)"
    pass "jdk" "$java_version ($java_home)"
else
    fail "jdk" "no JDK $JAVA_MAJOR found by /usr/libexec/java_home"
fi

# --- Android SDK packages ---
for pkg in cmdline-tools/latest platform-tools emulator; do
    revision="$(pkg_revision "$ANDROID_HOME/$pkg")"
    if [[ -n "$revision" ]]; then
        pass "$pkg" "$revision"
    else
        fail "$pkg" "not found in $ANDROID_HOME"
    fi
done

revision="$(pkg_revision "$SDK_IMAGE_DIR")"
if [[ -n "$revision" ]]; then
    pass "system-image" "$SYSTEM_IMAGE r$revision"
else
    fail "system-image" "$SYSTEM_IMAGE not installed"
fi

# --- AVD ---
if [[ ! -f "$AVD_CONFIG" ]]; then
    fail "avd" "$AVD_NAME not found ($AVD_CONFIG)"
else
    image="$(avd_value image.sysdir.1)"
    playstore="$(avd_value PlayStore.enabled)"
    size="$(avd_value hw.lcd.width)x$(avd_value hw.lcd.height)@$(avd_value hw.lcd.density)"
    expected_size="${AVD_WIDTH}x${AVD_HEIGHT}@${AVD_DENSITY}"
    if [[ "$image" == "$(echo "$SYSTEM_IMAGE" | tr ';' '/')/" \
        && "$playstore" =~ ^(no|false)$ \
        && "$size" == "$expected_size" ]]; then
        pass "avd" "$AVD_NAME, $size dpi, no Play Store"
    else
        fail "avd" "$AVD_NAME: image=$image PlayStore=$playstore size=$size (expected $expected_size)"
    fi
fi

# --- Running emulator ---
serial="$("$ADB" devices 2>/dev/null | awk '$1 ~ /^emulator-/ && $2 == "device" {print $1; exit}')"
if [[ -z "$serial" ]]; then
    fail "emulator-running" "no emulator attached (start: emulator -avd $AVD_NAME)"
    fail "adb-root" "skipped: no emulator"
    fail "unciv-apk" "skipped: no emulator"
    fail "display-cutout" "skipped: no emulator"
else
    running_avd="$("$ADB" -s "$serial" emu avd name 2>/dev/null | head -1 | tr -d '\r')"
    if [[ "$running_avd" == "$AVD_NAME" ]]; then
        pass "emulator-running" "$serial ($running_avd)"
    else
        fail "emulator-running" "$serial runs '$running_avd', expected $AVD_NAME"
    fi

    # Root must be available, and adbd must be back to shell afterwards.
    "$ADB" -s "$serial" root >/dev/null 2>&1
    "$ADB" -s "$serial" wait-for-device
    whoami="$("$ADB" -s "$serial" shell whoami 2>/dev/null | tr -d '\r')"
    "$ADB" -s "$serial" unroot >/dev/null 2>&1
    "$ADB" -s "$serial" wait-for-device
    whoami_after="$("$ADB" -s "$serial" shell whoami 2>/dev/null | tr -d '\r')"
    if [[ "$whoami" == "root" && "$whoami_after" == "shell" ]]; then
        pass "adb-root" "root available; adbd back to shell"
    else
        fail "adb-root" "whoami as root = '$whoami', after unroot = '$whoami_after'"
    fi

    version_code="$("$ADB" -s "$serial" shell dumpsys package "$UNCIV_PACKAGE" 2>/dev/null \
        | grep -m1 -o 'versionCode=[0-9]*' | cut -d= -f2)"
    if [[ "$version_code" == "$expected_version_code" ]]; then
        pass "unciv-apk" "$UNCIV_PACKAGE versionCode $version_code (expected from $expected_source)"
    elif [[ -n "$version_code" ]]; then
        fail "unciv-apk" "$UNCIV_PACKAGE versionCode $version_code, expected $expected_version_code (from $expected_source)"
    else
        fail "unciv-apk" "$UNCIV_PACKAGE not installed, expected $expected_version_code (from $expected_source)"
    fi

    if cutout_disabled; then
        pass "display-cutout" "disabled"
    else
        fail "display-cutout" "active or unknown (run: scripts/prepare_emulator.sh)"
    fi
fi

echo
if ((failures > 0)); then
    echo "$failures check(s) failed"
    exit 1
fi
echo "All checks passed"
