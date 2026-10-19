Issue 8 preparation evidence (English; no labels)

report.md                         Current Report and pending device gate
probe-manifest.json               Pinned source, APK hash, width budgets, exclusions
device-commands.txt               Every executed adb command, output or saved-output hash, exit code
font-width-helper.txt             Standalone measurement helper; not Unciv source
gradle-bootstrap-failure.txt      Original unchanged-wrapper download failure
gradle-download-verification.txt  Official and downloaded Gradle SHA-256 match
gradle-runtime.txt                Exact Gradle/JBR runtime
probe-build.txt                   Successful probe assembleDebug stdout/stderr and timing
probe-badging.txt                 aapt2 dump badging output
probe-signature.txt               Probe apksigner verification and certificate
fdroid-signature.txt              Backed-up F-Droid APK verification and certificate
sdk-install.txt                  Corrected SDK package installation output
pytest.txt                       Offline test output, including skip and warning
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

Probe screenshots do not exist yet. Once captured, they are exploration only
and may be embedded only in the Report. No file here is a ground-truth label
or an evaluation input. Anton decides the final injection after the probe.
