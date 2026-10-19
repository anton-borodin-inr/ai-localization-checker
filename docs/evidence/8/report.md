# Issue 8 Report

**Incomplete: probe APK built, installed and launched after Anton's explicit
approval. Waiting for manual navigation; no probe screenshots yet. Anton has not chosen A/B, and intentional ellipsis is not accepted as a
defect.** No labels or evaluation inputs have been created.

- **What changed:** Added `docs/unciv-build.md` with the build/install/rollback
  plan, exact German probe strings, source-based width budgets and label-format
  proposal. A separate fork based on tag 4.22.10 / commit
  `899367522cea36d6063c84b02b41eedfa9a0d0e9` has a probe containing Mining and
  Worker changes plus versionCode 1271009. `BuildConfig.kt` changes build
  metadata (versionCode), not a translation or game logic. The clean/defective
  pair remains pending and will contain at most the one chosen injection.
- **How it was verified:** Source inspection and standalone Android Paint
  measurements: Mining 169.54 / 140 units (+21.10%); Worker 356.94 / 273.33
  nominal units (+30.59%). Worker can grow its panel; this is not a hard title
  limit or an observed defect. JBR 21.0.10 arm64 and SDK package versions were
  inspected. SDK API 37.0 revision 2 and Build Tools 36.0.0 were installed. The
  probe APK built successfully (Gradle 2m 38s; wall 159.03s; exit 0; 45 executed
  tasks). APK metadata confirms com.unciv.app / 4.22.10 / 1271009, minSdk 21,
  targetSdk 36 and compileSdk 37. Both exact German values are packaged;
  AndroidLauncher occurs in DEX and the arm64 libgdx library is present.
  `apksigner verify --verbose --print-certs` exited 0 for both APKs and showed
  different signing certificates. The original installed APK, internal and
  external files and exact settings bytes are backed up locally. Settings
  checksum matches the device and the archived settings bytes match the
  standalone backup; adbd ended as shell. After Anton authorized the replacement,
  uninstall and probe installation each reported Success (exit 0). An independent
  package read confirmed 4.22.10 / 1271009 and DEBUGGABLE. `am start -W` reported
  Status: ok; the process and top resumed activity were independently confirmed.
  Boot, display size 1080 x 2400, density 420 and the existing fail-closed cutout
  check passed. Screenshots and restoration are not
  run. `uv run --offline pytest` exited 0: 181 passed, 1 skipped (the opt-in
  device test), 1 upstream google-genai/Python deprecation warning in 28.09s.
  Ruff check and format check exited 0 (30 files already formatted), and
  `git diff --check` passed. `--run-device` was not run: capture/device code is
  unchanged; probe screenshots are waiting for Anton's manual navigation.
- **Deviations from the task:** Anton explicitly approved a preliminary
  two-injection probe before the one-injection pair. Probe images are exploration
  only in this Report and are excluded from labels and evaluation. Manual
  navigation plus SDK `adb exec-out screencap -p` replaces the existing capture
  CLI for these screens, because the CLI relaunches into the main menu. No
  navigation/debug hook or repository dependency is added. Initial clone
  attempts failed in the network sandbox; authorized retries succeeded. The
  first SDK request used the unavailable `android-37` package identifier; the
  corrected `android-37.0` request succeeded. Initial Gradle bootstrap timed out
  after 67.62 seconds at the wrapper's 10-second read timeout. Predownloading
  the same pinned distribution and verifying its official SHA-256 recovered
  the unchanged wrapper; no build-configuration patch was made. A fresh-clone
  Git refresh initially reported four asset read timeouts; subsequent clean
  status/diff checks succeeded, and no asset changes are in the probe commit.
  The first offline uv sync could not access the shared cache in the sandbox;
  the authorized offline retry installed only the existing locked dependencies.
  The first standalone font helper failed because app_process had not initialized
  the Android font map (exit 137, NullPointerException); initializing that map
  fixed the helper, with both subsequent measurements exiting 0.
- **Decisions proposed:** D-023 records the approved exploratory/manual-capture
  workflow and the proposed label-file format. No Accepted decision is edited.
- **Open questions for Anton:** Open the two probe screens manually, then
  choose A/B from the observed behavior and decide the ellipsis boundary. Supply
  final human labels and confirm the clean control. Every subsequent app
  replacement/deletion or explicit data overwrite still needs its own approval.
- **API usage:** No live provider calls; no detector output or hold-out access.
  No new dependencies in this repository. Existing Android/Gradle build inputs
  are downloaded as required by the unchanged upstream configuration.

## Exploration only: probe 1271009

| Screen | Actual behavior |
|---|---|
| Technology picker / Mining | Not captured; prediction: intentional ellipsis |
| City construction / Worker | Not captured; panel growth, edge loss and overlap remain unobserved |

Probe screenshots will be embedded here only after Anton opens each screen and
the capture passes the documented checks. They are never ground truth.

## Command evidence

Every device command is retained with stdout/stderr and exit status. Binary
stdout and private backups are saved to named local files with size and SHA-256
rather than printed. Public transcripts normalize the SDK executable to `adb`.
Current raw working evidence is local under `data/issue-8/`; selected command
evidence is retained beside this Report. Private app backups are excluded.

## Verified artifacts and gate

- Fork probe commit: `190275d1e4490dceb682cf881f8c3433c1b53162`.
- Probe APK: 32,475,142 bytes; SHA-256
  `31a798f9d446eb396ba7465001778c519754e62b43f750e609de7cee2c778e1f`.
- Backed-up original F-Droid APK: 27,531,553 bytes; SHA-256
  `caddedb60a6dcaf0199950251e027cefe363b7d2388cbc4c5d4587edaa1de9f2`.
- Original settings: 93 bytes; SHA-256
  `3b55ab3dd62845e1c31374bb604446d0a3b672045ba030e90810d9354fabaa6d`.
- Original private and external file archives are readable and retained in the
  private local backup. Their checksums and the probe APK checksum were rechecked
  immediately before replacement. F-Droid was uninstalled and probe installed
  after Anton explicitly answered: "Yes, uninstall F-Droid and install the probe."
  No agent settings/save overwrite or restoration has been run.

Authorized and executed commands (both exit 0 / Success):

```bash
adb -s emulator-5554 uninstall com.unciv.app
adb -s emulator-5554 install outputs/issue-8/Unciv-probe-1271009.apk
```

The probe is running and waiting for Anton to select German and open the two
screens. Existing settings were not imported into the fresh debug installation.
Every later app replacement or explicit data overwrite still has its own
confirmation gate. Read-only preflight excerpts are in
[device-preflight.txt](device-preflight.txt); full command records and saved-output
checksums are in [device-commands.txt](device-commands.txt).

## Changed files at this preparation checkpoint

- Checker: `docs/unciv-build.md`, `docs/decisions.md`, this Report, and the
  supporting text/JSON evidence listed in [README.txt](README.txt).
- Fork: `android/assets/jsons/translations/German.properties` and
  `buildSrc/src/main/kotlin/BuildConfig.kt` only; commit
  `190275d1e4490dceb682cf881f8c3433c1b53162`.
- No checker runtime, test, dependency or lockfile changes. No labels, metrics
  or matching changes. APKs, settings and saves remain outside tracked files.
