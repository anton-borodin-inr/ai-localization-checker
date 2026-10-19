Issue 8 preparation evidence (English; no labels)

report.md                         Current Report; captures complete, human labels/review pending
probe-manifest.json               Pinned source, APK hash, width budgets, exclusions
pair-manifest.json                Final builds, accepted D-023 boundary, save checks and capture state
pair-apk-comparison.json          Byte comparisons: DEX, native libraries, assets and changed ZIP entries
device-commands.txt               Every executed adb command, output or saved-output hash, exit code
device-preflight.txt              Relevant fields from independent installed-package/display/foreground reads
font-width-helper.txt             Standalone measurement helper; not Unciv source
gradle-bootstrap-failure.txt      Original unchanged-wrapper download failure
gradle-download-verification.txt  Official and downloaded Gradle SHA-256 match
gradle-runtime.txt                Exact Gradle/JBR runtime
probe-build.txt                   Successful probe assembleDebug stdout/stderr and timing
probe-badging.txt                 aapt2 dump badging output
probe-signature.txt               Probe apksigner verification and certificate
clean-build.txt                   Clean 1271001 assembleDebug output and timing
defective-build.txt               Mining-only 1271002 assembleDebug output and timing
clean-badging.txt                 Clean APK metadata
defective-badging.txt             Defective APK metadata
clean-signature.txt               Clean APK signature verification
defective-signature.txt           Defective APK signature verification
clean-source-diff.txt             Clean source diff from pinned base; normalized review text
defective-source-diff.txt         Defective source diff from pinned base; normalized review text
fdroid-signature.txt              Backed-up F-Droid APK verification and certificate
sdk-install.txt                  Corrected SDK package installation output
pytest.txt                       Offline test output, including skip and warning
pytest-pair-builds.txt            Fresh offline run: 181 passed, 1 skipped, 1 warning
ruff-check-pair-builds.txt        Fresh Ruff check output
ruff-format-pair-builds.txt       Fresh Ruff format check output
host-checks.txt                   Executed host checks and their results

Public text copies normalize machine-specific host paths, line endings and
trailing whitespace (including empty lines at EOF). Device filesystem
paths remain unchanged. The adb executable is always written as adb. Copies
do not imply a command was rerun. Exact local working logs remain available.

The original APK, GameSettings.json, settings metadata/readbacks, internal and
external app-file archives, and their checksum manifest are private local
backups under data/issue-8/backups/fdroid-original/. They are not committed.
No backup archive is extracted into this repository. The backed-up settings
match both the device checksum and the settings member of the internal archive.

exploration/tech-picker__de__2400x1080__probe__1271009.png
exploration/city-construction__de__2400x1080__probe__1271009.png

Both original probe screenshots are retained under exploration/ and embedded
only in the Report. Their hashes, dimensions and capture checks are recorded
in probe-manifest.json. They are exploration only. No file here is a ground-truth label
or an evaluation input. Anton selected Mining after the probe and accepted
the screenshot-level ellipsis boundary as D-023. Neither decision turns a
probe screenshot into a label.

Private backups of the manually saved issue-8-pair (Ottoman Istanbul, turn 1)
and probe settings are retained before and after the authorized clean install.
Their unchanged hashes are recorded in pair-manifest.json and the Report.
No full settings or saved-game content is published.

final/tech-picker__de__2400x1080__clean__1271001.png
final/tech-picker__en__2400x1080__clean__1271001.png
final/tech-picker__de__2400x1080__injected__1271002.png
Final screenshots have no agent-written labels. Their capture checks, hashes
and the reference-save checksum are recorded in pair-manifest.json.
