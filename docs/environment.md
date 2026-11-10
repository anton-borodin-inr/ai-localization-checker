# Capture environment

The Stage 0 environment for capturing Unciv screenshots: an Android emulator with `adb root`, the Unciv APK from F-Droid and the SDK `adb` that captures screenshots (D-022). Related decisions: D-002, D-006, D-011, D-014, D-022 (D-015 superseded).

Set up and verified on 2026-10-17 on a MacBook Pro (M3 Pro, arm64), macOS 27.0.1.

## Python environment and offline tests

From the repository root, run `uv sync`, then `uv run pytest`. Python 3.14.0
and uv 0.11.6 were checked on macOS 27.0.1 for issue #17; `requires-python`
remains `>=3.11`. Device tests are skipped unless `--run-device` is requested.

On this Mac, an editable install's `.pth` file carried `UF_HIDDEN`, and Python
skipped it, causing `ModuleNotFoundError: l10n_checker` during collection.
The process that originally set the flag was not identified. The same hidden
`.pth` behavior was reproduced on Python 3.12.4, 3.13.13 and 3.14.0; see the
[upstream report](https://github.com/astral-sh/uv/issues/16977).

Pytest now adds the repository's `src` directory through its built-in
`pythonpath` setting (D-019), so source tests do not depend on the editable
hook. No wrapper, environment variable or manual flag change is needed.
This fixes pytest imports, not the source of the filesystem flag. Standalone
imports and installed commands are checked separately with
`uv run python -c "import l10n_checker"`, `uv run l10n-check --help` and
`uv run l10n-capture --help`; pytest passing alone does not verify installation.

## Versions

| Tool | Version used | How it was installed |
|---|---|---|
| JDK | OpenJDK 17.0.19 (Homebrew) | `brew install openjdk@17` |
| Android SDK root | `~/Library/Android/sdk` | Android Studio (default SDK location) |
| Android cmdline-tools | 20.0 (`cmdline-tools/latest`) | Android Studio → SDK Manager → SDK Tools, or `sdkmanager "cmdline-tools;latest"` |
| Android platform-tools (adb) | 37.0.0 | `sdkmanager "platform-tools"` |
| Android emulator | 36.5.11 | `sdkmanager "emulator"` |
| System image | `system-images;android-34;google_apis;arm64-v8a`, revision 14 | `sdkmanager "system-images;android-34;google_apis;arm64-v8a"` |
| Unciv | 4.22.10, versionCode 1271 (F-Droid) | see [Unciv APK](#unciv-apk) |

Notes:

- `sdkmanager` / `avdmanager` from cmdline-tools 20.0 print `This version only understands SDK XML versions up to 3 but an SDK XML file of version 4 was encountered`. The warning comes from Android Studio writing newer metadata. It is harmless; installs still succeed.
- This machine also has an `adb` from the Homebrew cask `android-platform-tools`. Always use the SDK `adb` (`$ANDROID_HOME/platform-tools/adb`). Two different adb versions talking to one daemon keep restarting it.

## Setup on a clean machine

Shell variables used below (nothing is written to shell profiles):

```bash
export ANDROID_HOME="$HOME/Library/Android/sdk"
export JAVA_HOME="$(/usr/libexec/java_home -v 17)"
SDKMANAGER="$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager"
AVDMANAGER="$ANDROID_HOME/cmdline-tools/latest/bin/avdmanager"
```

1. JDK 17: `brew install openjdk@17`.
2. Android SDK: install Android Studio and its default SDK, or the standalone cmdline-tools. Then:

   ```bash
   "$SDKMANAGER" "platform-tools" "emulator" "system-images;android-34;google_apis;arm64-v8a"
   ```

3. AVD (Google APIs image without Play Store, so `adb root` works; see D-002):

   ```bash
   echo no | "$AVDMANAGER" create avd -n unciv_api34 \
     -k "system-images;android-34;google_apis;arm64-v8a" -d pixel_7
   ```

4. Guest RAM: 4 GB (D-057). `avdmanager` writes 2 GB, which makes Android 14 thrash at boot (see [Hangs and slow adb](#hangs-and-slow-adb)):

   ```bash
   sed -i '' 's/^hw.ramSize=.*/hw.ramSize=4096/' ~/.android/avd/unciv_api34.avd/config.ini
   ```

   Write the value as a plain number of megabytes. `4096M` is not parsed: the emulator silently falls back to 2048 MB and logs `Increasing RAM size to 2048MB`.

## AVD

| Property | Value |
|---|---|
| Name | `unciv_api34` |
| Device profile | `pixel_7` |
| System image | `android-34;google_apis;arm64-v8a` (API 34, no Play Store) |
| Screen | 1080 × 2400 px, 420 dpi (D-014) |
| Guest RAM | `hw.ramSize=4096` (D-057) |
| Renderer | set explicitly with `-gpu` on every start (D-057) |

Unciv runs in landscape, so screenshots are 2400 × 1080. The display cutout is disabled (see [Display cutout](#display-cutout)), so screenshots contain only the game.

Start the emulator, keep the Mac display awake while it runs, and get root:

```bash
"$ANDROID_HOME/emulator/emulator" -avd unciv_api34 -no-snapshot-save -gpu lavapipe &
"$ANDROID_HOME/platform-tools/adb" wait-for-device
caffeinate -d -i -w "$(pgrep -f 'qemu-system-aarch64 -avd unciv_api34')" &
"$ANDROID_HOME/platform-tools/adb" root
"$ANDROID_HOME/platform-tools/adb" shell whoami   # root
```

The renderer is part of the capture conditions, so it is never left to `auto`. On 2026-11-10, `auto` resolved to `lavapipe` (software Vulkan on the host CPU). Earlier captures also used `auto` and are assumed, not verified, to have used `lavapipe` too. `-gpu host` (Metal through MoltenVK) is faster: cold boot in 18 s, and no watchdog or lmkd kills in the trial on 2026-11-10. It can change pixels, though. Switching renderer for captures that feed the dataset or a D-050 calibration needs a pixel comparison first (D-042 style: changed-pixel count, bounding box, maximum channel delta). Until Anton decides, use `lavapipe` for those captures.

To check which renderer and RAM a running emulator actually uses:

```bash
grep -E 'hw.gpu.mode|hw.ramSize' ~/.android/avd/unciv_api34.avd/hardware-qemu.ini
```

`caffeinate -d -i -w PID` keeps the display and the system awake until that emulator process exits; start it again after every emulator restart. The equivalent setting is System Settings → Lock Screen → turn display off on power adapter when inactive: Never. Closing the lid without an external display still sleeps the Mac.

After **every** boot, run:

```bash
scripts/prepare_emulator.sh
```

It waits for the boot to finish and disables the display cutout (next section). It runs as adbd `shell` and does not need root.

## Display cutout

The Pixel 7 profile makes the emulator enable the runtime resource overlay `com.android.internal.emulation.pixel_7`. The only resource it overrides is `config_mainBuiltInDisplayCutout`, which adds a 136 px hole-punch cutout. In landscape, Unciv leaves that strip black, so screenshots would contain a ~135 px black bar on the left.

Disabling the overlay removes the cutout and changes nothing else; resolution and density stay 1080 × 2400 at 420 dpi:

```bash
"$ANDROID_HOME/platform-tools/adb" shell cmd overlay disable com.android.internal.emulation.pixel_7
```

The emulator re-enables this overlay on every boot (checked with a cold restart), so the setting does not persist. `scripts/prepare_emulator.sh` re-applies it and waits until `dumpsys display` reports no cutout. The `com.android.internal.display.cutout.emulation.noCutout` overlay known from older images does not exist on this API 34 image.

To check by hand: `adb shell dumpsys display | grep -m1 'Built-in Screen'` must contain no `cutout DisplayCutout{insets=...}` field, or only zero insets.

## Unciv APK

| Field | Value |
|---|---|
| Package | `com.unciv.app` |
| Version | 4.22.10, versionCode 1271 |
| Source | https://f-droid.org/repo/com.unciv.app_1271.apk (F-Droid page: https://f-droid.org/packages/com.unciv.app/) |
| Size | 27 531 553 bytes |
| SHA-256 | `caddedb60a6dcaf0199950251e027cefe363b7d2388cbc4c5d4587edaa1de9f2` (matches F-Droid `index-v2.json`) |

The APK is stored in `data/apk/` (gitignored) and never committed.

```bash
mkdir -p data/apk
curl -fL -o data/apk/com.unciv.app_1271.apk https://f-droid.org/repo/com.unciv.app_1271.apk
shasum -a 256 data/apk/com.unciv.app_1271.apk
"$ANDROID_HOME/platform-tools/adb" install -r data/apk/com.unciv.app_1271.apk
"$ANDROID_HOME/platform-tools/adb" shell am start -W -n com.unciv.app/.AndroidLauncher
```

On first launch Unciv shows an Android "Viewing full screen" hint and a language picker. "Got it" and then "Pick language" with English selected (the default) open the main menu ("Version 4.22.10" at the bottom).

## Checking the environment

With the emulator running and prepared:

```bash
scripts/prepare_emulator.sh
scripts/check_env.sh
```

It prints `PASS`/`FAIL` for the JDK, each SDK package, the system image, the AVD settings, the running emulator, `adb root`, the installed Unciv version code, and the display cutout (FAIL if it is still active). It exits 1 if any check fails. Expected tool and AVD versions are at the top of the script and must match this file.

The expected Unciv version code depends on the stage, and the `unciv-apk` line names where it came from:

| Environment | Command | Expected version code |
|---|---|---|
| Stage 2 (current pipeline) | `scripts/check_env.sh` | `build.version_code` of `fixtures/stage2/screens-v2.json` |
| Another Stage 2 manifest | `scripts/check_env.sh --manifest PATH` | `build.version_code` of that manifest |
| Stage 0 (F-Droid APK) | `scripts/check_env.sh --version-code 1271` | 1271; no manifest pins this build |

Reading a manifest needs `python3`. Invalid input (both options together, an unknown option, an unreadable manifest, a non-digit version code) exits 2 before any adb call. The check compares the version code only; `l10n-capture` also verifies the manifest's APK hash.

The `adb root` check restarts adbd, so run this only when no capture is in progress.

## Hangs and slow adb

Symptoms: `adb` commands time out or take seconds, the device drops to `offline`, or Unciv freezes, sometimes after the emulator was left alone for a while.

Diagnosis on 2026-11-10 (emulator 36.5.11, API 34 r14):

- The guest's dropbox held two `system_server_watchdog` reports: on 2026-11-09 at 22:55 (main thread blocked 469 s) and on 2026-11-10 at 02:58 (149 s), with ANRs before them. Both fell inside periods when the Mac display was off; the Mac itself did not sleep. Working hypothesis: macOS throttles the windowed emulator process while the display is off. This is a correlation, not yet confirmed by a controlled run.
- With 2 GB guest RAM, lmkd logged thrashing and low swap during boot, and `system_server` reached `Watchdog: WAITED_HALF`. With `lavapipe`, the host CPU also renders every frame.
- With `lavapipe` and 4 GB RAM, `adb shell true` (30 tries, 1 s apart) took median 615 ms and max 3625 ms while Unciv was in the foreground (qemu at 172% host CPU), and median 66 ms, max 753 ms with Unciv in the background. With `-gpu host` and Unciv in the foreground, the max was 35 ms. Slow adb during a capture on `lavapipe` is therefore expected and is not by itself a hang.

Mitigations: 4 GB guest RAM, `caffeinate` while the emulator runs, and an explicit renderer (see [AVD](#avd)). Wiping the AVD data is not needed for this; nothing pointed to corrupted AVD state.

Commands used for the diagnosis (all read-only):

```bash
ADB="$ANDROID_HOME/platform-tools/adb"
"$ADB" shell dumpsys dropbox | grep -Ei 'watchdog|anr|lowmem'      # past system_server stalls, survive reboots
"$ADB" shell dumpsys dropbox --print system_server_watchdog | grep -E 'Subject|Blocked'
"$ADB" logcat -d -b all | grep -E 'lowmemorykiller: Kill|Watchdog: WAITED|ANR in'
"$ADB" shell 'grep -E "MemTotal|MemAvailable|SwapFree" /proc/meminfo'
pmset -g log | grep -E 'Display is turned (on|off)'                    # compare with dropbox timestamps
```
