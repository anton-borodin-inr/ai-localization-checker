# Capture environment

The Stage 0 environment for capturing Unciv screenshots: an Android emulator with `adb root`, the Unciv APK from F-Droid and a project-local Appium server with the uiautomator2 driver. Related decisions: D-002, D-006, D-011, D-014, D-015.

Set up and verified on 2026-10-17 on a MacBook Pro (M3 Pro, arm64), macOS 27.0.1.

## Versions

| Tool | Version used | How it was installed |
|---|---|---|
| JDK | OpenJDK 17.0.19 (Homebrew) | `brew install openjdk@17` |
| Android SDK root | `~/Library/Android/sdk` | Android Studio (default SDK location) |
| Android cmdline-tools | 20.0 (`cmdline-tools/latest`) | Android Studio → SDK Manager → SDK Tools, or `sdkmanager "cmdline-tools;latest"` |
| Android platform-tools (adb) | 37.0.0 | `sdkmanager "platform-tools"` |
| Android emulator | 36.5.11 | `sdkmanager "emulator"` |
| System image | `system-images;android-34;google_apis;arm64-v8a`, revision 14 | `sdkmanager "system-images;android-34;google_apis;arm64-v8a"` |
| Node.js / npm | 25.9.0 / 11.12.1 (Homebrew) | `brew install node` |
| Appium | 3.3.1, project-local | `npm ci` in the repository (pinned in `package.json` / `package-lock.json`) |
| uiautomator2 driver | 7.1.2, in `./.appium` | `APPIUM_HOME=./.appium npx appium driver install uiautomator2@7.1.2` |
| Unciv | 4.22.10, versionCode 1271 (F-Droid) | see [Unciv APK](#unciv-apk) |

Notes:

- Appium 3 needs Node ≥ 20.19. Any newer Node release works.
- `sdkmanager` / `avdmanager` from cmdline-tools 20.0 print `This version only understands SDK XML versions up to 3 but an SDK XML file of version 4 was encountered`. The warning comes from Android Studio writing newer metadata. It is harmless; installs still succeed.
- This machine also has an `adb` from the Homebrew cask `android-platform-tools`. Always use the SDK `adb` (`$ANDROID_HOME/platform-tools/adb`). Two different adb versions talking to one daemon keep restarting it.
- The global Appium (`npm -g`, drivers in `~/.appium`) is not used by this project. The project sets `APPIUM_HOME=./.appium`, so its drivers never touch the global ones.

## Setup on a clean machine

Shell variables used below (nothing is written to shell profiles):

```bash
export ANDROID_HOME="$HOME/Library/Android/sdk"
export JAVA_HOME="$(/usr/libexec/java_home -v 17)"
SDKMANAGER="$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager"
AVDMANAGER="$ANDROID_HOME/cmdline-tools/latest/bin/avdmanager"
```

1. JDK 17 and Node: `brew install openjdk@17 node`.
2. Android SDK: install Android Studio and its default SDK, or the standalone cmdline-tools. Then:

   ```bash
   "$SDKMANAGER" "platform-tools" "emulator" "system-images;android-34;google_apis;arm64-v8a"
   ```

3. AVD (Google APIs image without Play Store, so `adb root` works; see D-002):

   ```bash
   echo no | "$AVDMANAGER" create avd -n unciv_api34 \
     -k "system-images;android-34;google_apis;arm64-v8a" -d pixel_7
   ```

4. Project-local Appium, from the repository root:

   ```bash
   npm ci
   APPIUM_HOME=./.appium npx appium driver install uiautomator2@7.1.2
   ```

   Start the server with `npm run appium` (sets `APPIUM_HOME=./.appium`).

## AVD

| Property | Value |
|---|---|
| Name | `unciv_api34` |
| Device profile | `pixel_7` |
| System image | `android-34;google_apis;arm64-v8a` (API 34, no Play Store) |
| Screen | 1080 × 2400 px, 420 dpi (D-014) |

Unciv runs in landscape, so screenshots are 2400 × 1080. The display cutout is disabled (see [Display cutout](#display-cutout)), so screenshots contain only the game.

Start the emulator and get root:

```bash
"$ANDROID_HOME/emulator/emulator" -avd unciv_api34 -no-snapshot-save &
"$ANDROID_HOME/platform-tools/adb" wait-for-device
"$ANDROID_HOME/platform-tools/adb" root
"$ANDROID_HOME/platform-tools/adb" shell whoami   # root
```

After **every** boot, run:

```bash
scripts/prepare_emulator.sh
```

It waits for the boot to finish, restarts adbd as root and disables the display cutout (next section).

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

It prints `PASS`/`FAIL` for the JDK, each SDK package, the system image, the AVD settings, the running emulator, `adb root`, the installed Unciv version code, the display cutout (FAIL if it is still active), the project-local Appium version and the uiautomator2 driver (including that it supports the installed Appium). It exits 1 if any check fails. Expected versions are at the top of the script and must match this file.
