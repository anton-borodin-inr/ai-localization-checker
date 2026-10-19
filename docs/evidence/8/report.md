# Issue 8 Report

**Probe checkpoint complete; issue 8 remains incomplete.** Both exploratory
screens were captured after Anton's manual navigation. Mining shows intentional
ellipsis; Worker displays its complete title without demonstrated text loss.
Stopped for Anton's selection. No final pair, labels or evaluation inputs have
been created, and intentional ellipsis is not yet accepted as a defect.

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
  check passed. Both probe screens were captured without restart or app-data
  writes after Anton opened each. Read-only `run-as` settings reads confirmed
  German, Small UI, font multiplier 1 and the default font family. PNG structure,
  CRC and 2400 x 1080 size passed; foreground and cutout passed before/after.
  Restoration and the final pair are not run. At the preparation checkpoint,
  `uv run --offline pytest` exited 0: 181 passed, 1 skipped (the opt-in
  device test), 1 upstream google-genai/Python deprecation warning in 28.09s.
  Ruff check and format check exited 0 (30 files already formatted), and
  `git diff --check` passed. `--run-device` was not run: capture/device code is
  unchanged. These offline checks were not rerun for the later documentation
  and image-evidence updates; their runtime/test sources remain unchanged.
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
- **Open questions for Anton:** Choose the next step from the two observed
  outcomes and decide the intentional-ellipsis boundary. A is a candidate only
  if Anton accepts that shortening as a defect; B has not demonstrated
  `truncated_text` and is not evidence of a defect. If ellipsis is rejected,
  neither current probe establishes the required text-loss case; another
  experiment needs Anton's direction before changes. Final human labels and
  clean-control acceptance remain Anton-owned. Every subsequent app
  replacement/deletion or explicit data overwrite still needs its own approval.
- **API usage:** No live provider calls; no detector output or hold-out access.
  No new dependencies in this repository. Existing Android/Gradle build inputs
  are downloaded as required by the unchanged upstream configuration.

## Exploration only: probe 1271009

| Screen | Actual behavior |
|---|---|
| Technology picker / Mining | **Observed:** the title ends in `...`, omitting the end of `Erzgewinnung`, inside the fixed-width TechButton. This is the source's intentional-ellipsis path. No collision around the target title is visible. Defect acceptance remains Anton's decision. |
| City construction / Worker | **Observed:** the complete title fits on one line in the lower-right construction panel, without ellipsis, edge loss or visible collision. In the available-constructions list it wraps onto two lines, retaining the full text. The panel accommodates the title beyond the nominal budget; this is consistent with source-driven growth, but its width change versus a clean build has not been measured. `truncated_text` is not demonstrated. |

The Technology capture is 393,632 bytes, 2400 x 1080; SHA-256
`68f2f287f19b312bff501793bb563da03a81b7768d935b0e0027ea479f4bc49b`.
No clean-control comparison has been made yet. These observations are
exploration, not ground-truth labels.

![Exploration only: Mining title with intentional ellipsis](exploration/tech-picker__de__2400x1080__probe__1271009.png)

The Worker capture is 562,946 bytes, 2400 x 1080; SHA-256
`56f2a11958c5cb3a12c5cc7d7b1b6edf726b04e94de3a655fc2b3624f5fc0e71`.

![Exploration only: complete Worker title in the adaptive panel](exploration/city-construction__de__2400x1080__probe__1271009.png)

**Recommendation, not a label:** A is the only current candidate showing text
shortening, and it is the intentional-ellipsis path. Proceed with A only if
Anton explicitly accepts that boundary. B is a successful adaptation in this
capture and should not be presented as truncation. Do not build the final pair
or change either injection before Anton chooses the next step.

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
  after Anton explicitly answered (translated from Russian): "Yes, uninstall
  F-Droid and install the probe."
  No agent settings/save overwrite or restoration has been run.

Authorized and executed commands (both exit 0 / Success):

```bash
adb -s emulator-5554 uninstall com.unciv.app
adb -s emulator-5554 install outputs/issue-8/Unciv-probe-1271009.apk
```

Anton selected German, founded Istanbul, opened the Technology picker and
then selected Worker in the city screen. Both exploratory captures are complete.
Existing settings were not imported into the fresh debug installation.
Every later app replacement or explicit data overwrite still has its own
confirmation gate. Read-only preflight excerpts are in
[device-preflight.txt](device-preflight.txt); full command records and saved-output
checksums are in [device-commands.txt](device-commands.txt).

## Changed files at this probe checkpoint

- Checker: `docs/unciv-build.md`, `docs/decisions.md`, this Report, and the
  supporting text/JSON evidence listed in [README.txt](README.txt).
- Fork: `android/assets/jsons/translations/German.properties` and
  `buildSrc/src/main/kotlin/BuildConfig.kt` only; commit
  `190275d1e4490dceb682cf881f8c3433c1b53162`.
- No checker runtime, test, dependency or lockfile changes. No labels, metrics
  or matching changes. APKs, settings and saves remain outside tracked files.
