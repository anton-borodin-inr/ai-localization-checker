# Unciv source builds for issue 8

**Status: probe APK built; waiting for the app-replacement gate.** No probe screen has been observed,
Anton has not chosen the final injection, and no labels have been created.
See the [Report](evidence/8/report.md) for executed checks, failures and pending
steps. Commands in recipes below are instructions, not execution evidence.

## Source and allowed changes

Unciv lives in the separate `anton-borodin-inr/Unciv` fork workspace, never in
this repository. The shared upstream base is tag `4.22.10`, commit
`899367522cea36d6063c84b02b41eedfa9a0d0e9`, researched in issue 7.

| Build | versionName | versionCode | Translation changes relative to the base |
|---|---|---:|---|
| F-Droid reference | 4.22.10 | 1271 | None in this task |
| Exploratory probe | 4.22.10 | 1271009 | Mining and Worker below |
| Final clean (pending) | 4.22.10 | 1271001 | None |
| Final defective (pending) | 4.22.10 | 1271002 | Only the injection Anton chooses |

`buildSrc/src/main/kotlin/BuildConfig.kt` changes build metadata
(`appCodeNumber`, used as APK `versionCode`), not a translation or game logic.
The final fork commit hashes differ, while the pinned upstream base is the
same. No other tracked game code, Gradle configuration, package identifier or
signing configuration may change. The local fork instruction file is ignored.

## Probe plan and width calculation

Anton approved one preliminary APK containing both injections. This APK and
its screenshots are exploration only: no label, matching input, evaluation
input or clean/defective pair may be derived from them. Intentional ellipsis
has not been accepted as a defect.

Both changes are in `android/assets/jsons/translations/German.properties`:

| Key | Before | Probe value |
|---|---|---|
| Mining | Bergbau | Bergbau und Erzgewinnung |
| Worker | Arbeiter | Arbeiter für Geländeausbau und Infrastruktur |

These are descriptive German names for mining/ore extraction and a worker
improving terrain/infrastructure, rather than the artificial sentences in the
initial candidate plan. Their suitability for the final label remains Anton's
decision.

**Measured font advances, source-based layout budgets:** a standalone helper
ran Android Paint on the API 34 emulator. It initializes the preinstalled font
map, uses `Typeface.create("", NORMAL)` at 100 px and sums each character's
integer-truncated width. This follows Unciv's [AndroidFont raster widths] and
[NativeBitmapFontData glyph advances]; scaling is 14/100 for TechButton and
18/100 for an ordinary label. The helper is not linked into or installed as
Unciv. Its output is in the command evidence, not detector output.

| Target | Original width | Probe width | Available width used in the calculation | Excess |
|---|---:|---:|---:|---:|
| Mining, TechButton title | 51.80 | 169.54 | 140.00 | 21.10% |
| Worker, construction title | 63.36 | 356.94 | 273.33 nominal | 30.59% |

All widths are Scene2D layout units, not screenshot pixels. Assumptions for
the probe are default font family, `fontSizeMultiplier = 1`,
`screenSize = Small`, landscape 2400 x 1080 and no cutout.

For Mining, [TechButton] sets font size 14, `wrap = false`, ellipsis and
`width(140f)`. `1211 * 0.14 = 169.54`; `(169.54 / 140 - 1) * 100 = 21.10%`.
The prediction is intentional ellipsis, to be verified on screen.

For Worker, [BaseScreen] uses virtual height 600 for `Small`; at the target
aspect ratio the stage width is `600 * 2400 / 1080 = 1333.33`. The description
in [ConstructionInfoTable] spans two columns at `stage.width / 4 = 333.33`.
The portrait occupies `50 + 5 + 5 = 60`; the remaining nominal title-column
space is `333.33 - 60 = 273.33`. `1983 * 0.18 = 356.94`;
`(356.94 / 273.33 - 1) * 100 = 30.59%`.

**The Worker budget is not a hard maximum.** The title has no wrapping,
ellipsis or max-width constraint; the panel packs to preferred size and is
[anchored at bottom right]. It may grow, rather than lose text. The probe must
distinguish panel growth, text lost at the display edge and overlap. Overlap
alone is not the selected v1 class. No text loss is claimed before observation.

## Build environment

Observed on this arm64 Mac during preparation:

| Component | Version |
|---|---|
| JDK selected for builds | Android Studio JBR 21.0.10, aarch64 |
| Other registered JDK | Homebrew OpenJDK 17.0.19 |
| Gradle wrapper | 9.4.1, pinned upstream |
| Android Gradle Plugin | 9.2.0, pinned upstream |
| compileSdk / targetSdk / minSdk | 37 / 36 / 21 |
| SDK platform installed for this task | `platforms;android-37.0`, revision 2 |
| Build Tools installed for this task | 36.0.0, AGP 9.2 default |
| SDK platform-tools | 37.0.0; adb 1.0.41 |
| Command-line Tools | 20.0 |
| Capture emulator | API 34 Google APIs arm64, Pixel 7 profile |

The first SDK installation request for `platforms;android-37` failed because
the actual repository identifier is `platforms;android-37.0`. The corrected
installation succeeded. Tooling printed an SDK XML v3/v4 compatibility warning;
this was retained in the preparation log.

Use the JBR 21 already bundled with Android Studio, matching upstream Android
CI's Java major version. Keep the wrapper, AGP and compileSdk unchanged.
Gradle caches are isolated in the task workspace. In the fork root, with the
three paths configured for the machine:

```bash
/usr/bin/time -p env JAVA_HOME="$BUILD_JDK" ANDROID_HOME="$BUILD_SDK" \
  GRADLE_USER_HOME="$BUILD_CACHE" \
  ./gradlew --no-daemon --console=plain :android:assembleDebug
```

`BUILD_JDK` denotes Android Studio's `Contents/jbr/Contents/Home`, `BUILD_SDK`
the installed Android SDK root and `BUILD_CACHE` the task-local Gradle cache.
Record their configuration and exact runtime versions in local build evidence;
never dump the shell environment. A local-cache bootstrap download failed at
the unchanged wrapper's 10-second read timeout; the Report records recovery.

Once installation is explicitly approved and the signature preconditions below
are met, replacing `:android:assembleDebug` with `:android:installDebug` builds
and installs in one command. Do not run this task across a signing mismatch.
Use a selected emulator serial when multiple devices are present.

The probe build succeeded: Gradle duration 2m 38s, host wall time 159.03s,
exit 0; all 45 actionable tasks executed, with a fresh task-local Gradle cache
apart from the predownloaded distribution. The Report records each attempt.
SDK preparation and Gradle distribution downloads are separate from APK build
time. Inspect APK metadata, packaged German values, signing certificate,
AndroidLauncher presence in DEX and arm64 native libraries before installation.

## Signing, backups and installation gates

The package remains `com.unciv.app`. The upstream debug keystore differs from
F-Droid's signing key; a versionCode increase cannot make it an update.

1. Stop Unciv and capture installed-package metadata and `pm path`. Copy every
   returned APK to a private host backup and verify its checksum and signature.
2. With temporary `adb root`, back up the exact settings bytes and metadata
   from `/data/user/0/com.unciv.app/files/GameSettings.json`. Back up game files
   and relevant saves, including external app storage if present. Verify the
   copies, retain them locally and finish with `adb unroot` / `whoami = shell`.
3. **Stop for Anton's explicit confirmation before uninstall.** A normal
   uninstall removes the F-Droid app's private data, including settings. Do not
   use `uninstall -k` as a signature workaround.
4. Install the probe only after the gate. Launch once and let Anton choose
   German and the documented font/UI settings. Any explicit settings or save
   overwrite by the agent requires a separate confirmation first.
5. After both exploratory captures, stop. Anton chooses the final injection
   and decides the intentional-ellipsis boundary.
6. Build the final clean and single-injection defective versions. Their debug
   signatures must match. Probe 1271009 to clean 1271001 is a downgrade:
   explicitly approved `adb install -r -d` on the debuggable package can retain
   data; an uninstall/reinstall is the alternative, with its own approval and
   backup. Clean 1271001 to defective 1271002 uses approved `adb install -r`.
7. To return to F-Droid, first obtain confirmation before deleting debug.
   Reinstall the backed-up F-Droid APK. With the app stopped and before any
   approved data restoration, obtain the current package UID, restore bytes
   with appropriate current ownership, original modes and SELinux contexts,
   then verify readback/checksums. Do not copy an obsolete UID blindly.

Every app deletion/replacement and explicit app-data overwrite has a separate
stop immediately before it. Plan approval is not approval of these device
operations. Private APK/settings/save backups are not committed. Retain them
through verified restoration.

## Navigate and capture

Anton manually opens both probe screens in German once. Technology picker:
start/load a dev game, open research, keep Mining visible and select another
technology so the long name is not duplicated in the description. City screen:
use the same game, open a city and select Worker in available constructions.
Verify actual font/UI settings before applying the width predictions.

For the final pair, use one frozen dev save with recorded checksum, ruleset,
turn and manual navigation recipe. Preserve selected item and scroll position;
do not perform game actions between captures. Capture the German pair and an
English clean control of the selected screen (D-005/D-021).

Current `l10n-capture` relaunches into the main menu. It cannot capture these
screens after manual navigation. This task uses its SDK adb transport, with
manual navigation, rather than adding Stage 2 navigation or a debug hook.

Resolve `adb` to the SDK executable (D-022); documentation and public
transcripts use the name `adb`, not its absolute host path. From the checker
root after each boot, prepare the emulator with `scripts/prepare_emulator.sh`.
For a probe Technology picker capture:

```bash
set -euo pipefail
ADB=adb
serial=emulator-5554
source scripts/cutout.sh

cutout_disabled
(
    set -C
    adb -s "$serial" exec-out screencap -p \
      > data/issue-8/exploration/tech-picker__de__2400x1080__probe__1271009.png
)
cutout_disabled
```

For Worker, use `city-construction__de__2400x1080__probe__1271009.png`.
Record raw `dumpsys display` and overlay state before/after; cutout checks fail
closed on active or unknown state. Also record `wm size`, `wm density`, package
versionCode and top resumed activity before/after; validate PNG CRC, structure
and 2400 x 1080 dimensions with the existing checker functions. Never crop the
PNG to hide a cutout or alter font/display size to force the experiment.

For the final German pair use variant `clean` / build `1271001`, then variant
`injected` / build `1271002`, preserving D-003/D-016 filename fields and refusing
overwrites. Probe images appear only as exploration in the Report and never in
the labeled set.

The bare screencap command does not validate the language, installed build,
foreground, cutout, complete PNG, overwrite policy or settings restoration.
Those checks must be recorded separately. Unlike `l10n-capture`, this manual
recipe does not apply/read back/restore language automatically or verify a
restart. Neither method automatically verifies the intended in-game screen.

## Label-file proposal only

Propose a small JSON document with `schema_version`, `screenshot`, `language`
and `labels`. Each label has `defect_type` (`truncated_text` or `untranslated`),
`text_expected`, `text_seen`, `region` from the existing 3x3 grid, and an optional
`note`. Human labels do not need model confidence.

Anton fills every value by comparing the actual screen with the translation
source. An empty labels array means a human-reviewed clean screen; the agent
must not supply it as a placeholder. No detector output is used. This proposal
does not alter D-018's detector schema or implement matching/evaluation.

[AndroidFont raster widths]: https://github.com/yairm210/Unciv/blob/899367522cea36d6063c84b02b41eedfa9a0d0e9/android/src/com/unciv/app/AndroidFont.kt#L109-L118
[NativeBitmapFontData glyph advances]: https://github.com/yairm210/Unciv/blob/899367522cea36d6063c84b02b41eedfa9a0d0e9/core/src/com/unciv/ui/components/fonts/NativeBitmapFontData.kt#L82-L90
[TechButton]: https://github.com/yairm210/Unciv/blob/899367522cea36d6063c84b02b41eedfa9a0d0e9/core/src/com/unciv/ui/screens/pickerscreens/TechButton.kt#L28-L38
[BaseScreen]: https://github.com/yairm210/Unciv/blob/899367522cea36d6063c84b02b41eedfa9a0d0e9/core/src/com/unciv/ui/screens/basescreen/BaseScreen.kt#L75-L79
[ConstructionInfoTable]: https://github.com/yairm210/Unciv/blob/899367522cea36d6063c84b02b41eedfa9a0d0e9/core/src/com/unciv/ui/screens/cityscreen/ConstructionInfoTable.kt#L65-L94
[anchored at bottom right]: https://github.com/yairm210/Unciv/blob/899367522cea36d6063c84b02b41eedfa9a0d0e9/core/src/com/unciv/ui/screens/cityscreen/CityScreen.kt#L204-L209
