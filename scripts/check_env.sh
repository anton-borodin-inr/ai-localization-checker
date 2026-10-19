#!/usr/bin/env bash
# Checks the Stage 0 capture environment described in docs/environment.md.
# Prints PASS/FAIL per item and exits non-zero if any check fails.
# Read-only except for the adb-root check, which restarts adbd as root and then
# back as shell (`adb unroot`).
#
# Usage (emulator must be running): scripts/check_env.sh

set -u

# Expected values. Keep in sync with docs/environment.md.
JAVA_MAJOR=17
SYSTEM_IMAGE="system-images;android-34;google_apis;arm64-v8a"
AVD_NAME=unciv_api34
AVD_WIDTH=1080
AVD_HEIGHT=2400
AVD_DENSITY=420
UNCIV_PACKAGE=com.unciv.app
UNCIV_VERSION_CODE=1271
APPIUM_VERSION=3.3.1
UIAUTOMATOR2_VERSION=7.1.2

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ANDROID_HOME="${ANDROID_HOME:-$HOME/Library/Android/sdk}"
ADB="$ANDROID_HOME/platform-tools/adb"
SDK_IMAGE_DIR="$ANDROID_HOME/$(echo "$SYSTEM_IMAGE" | tr ';' '/')"
AVD_CONFIG="$HOME/.android/avd/$AVD_NAME.avd/config.ini"
export APPIUM_HOME="$REPO_ROOT/.appium"
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
    if [[ "$version_code" == "$UNCIV_VERSION_CODE" ]]; then
        pass "unciv-apk" "$UNCIV_PACKAGE versionCode $version_code"
    elif [[ -n "$version_code" ]]; then
        fail "unciv-apk" "$UNCIV_PACKAGE versionCode $version_code, expected $UNCIV_VERSION_CODE"
    else
        fail "unciv-apk" "$UNCIV_PACKAGE not installed"
    fi

    if cutout_disabled; then
        pass "display-cutout" "disabled"
    else
        fail "display-cutout" "active or unknown (run: scripts/prepare_emulator.sh)"
    fi
fi

# --- Project-local Appium ---
appium_bin="$REPO_ROOT/node_modules/.bin/appium"
appium_version="$("$appium_bin" --version 2>/dev/null | tail -1)"
if [[ "$appium_version" == "$APPIUM_VERSION" ]]; then
    pass "appium" "$appium_version (project-local)"
else
    fail "appium" "found '$appium_version', expected $APPIUM_VERSION (run: npm ci)"
fi

# The driver declares the Appium versions it supports; check ours satisfies it.
driver_check="$(cd "$REPO_ROOT" && "$appium_bin" driver list --installed --json 2>/dev/null \
    | node -e '
        const semver = require(process.argv[1] + "/node_modules/semver");
        let input = "";
        process.stdin.on("data", (c) => (input += c));
        process.stdin.on("end", () => {
            const d = JSON.parse(input).uiautomator2;
            if (!d) return console.log("MISSING");
            const ok = semver.satisfies(process.argv[2], d.appiumVersion, { includePrerelease: true });
            console.log(`${d.version} ${d.appiumVersion} ${ok ? "OK" : "INCOMPATIBLE"}`);
        });
    ' "$REPO_ROOT" "$APPIUM_VERSION" 2>/dev/null)"
read -r driver_version driver_range driver_status <<<"$driver_check"
if [[ "$driver_version" == "$UIAUTOMATOR2_VERSION" && "$driver_status" == "OK" ]]; then
    pass "uiautomator2" "$driver_version (supports appium $driver_range)"
else
    fail "uiautomator2" "got '${driver_check:-nothing}', expected $UIAUTOMATOR2_VERSION compatible with appium $APPIUM_VERSION"
fi

echo
if ((failures > 0)); then
    echo "$failures check(s) failed"
    exit 1
fi
echo "All checks passed"
