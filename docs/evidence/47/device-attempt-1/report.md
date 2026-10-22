# Issue 47 — device attempt 1 (2026-10-22)

**FAILED: APK 1271047 crashes on the first real v2 screens. Zero successful PNG/dump pairs.** The 40-request batch was interrupted after one client timeout and the next pending request. The raw summary remains unchanged, including that pending record. No detector/reference result can be inferred from this attempt.

## Observed failure

Android reports `java.util.regex.PatternSyntaxException` for pattern `\{([^{}]+)}` at `L10nTextMetadata.bind(L10nDrawObserver.kt:41)`. The crash trace includes construction of CrashScreen/BaseScreen, so crash handling also reaches the same metadata path. Source inspection identifies the unescaped closing literal brace in the component extraction regex. This is an Android-runtime failure missed by the host tests, not evidence that host tests failed or device acceptance passed.

The first approved request was options-gameplay / EN. It received no terminal event and the client reported `client_timeout`. The runner performed the already approved force-stop recovery and began new-game / EN. After the crash was diagnosed, SIGINT was sent to the owned capture CLI only; its finally restored settings and unrooted adbd. CLI exit code: **130**. No extra hook requests or retries were issued.

## Operations actually executed

- Anton approved the exact-operation plan and emulator start on 2026-10-22. Plan SHA-256: `adf97ce9ec33e3c289c57e13ab7a37308ea2a5c9d33e959365d177e9aaa30261`.
- Started the previously stopped `unciv_api34` AVD using `-no-snapshot-save`; no wipe/reset. The cold boot exposed active display cutout, so the first preinstall check stopped before installation. The standard D-014 preparation script disabled only the Pixel 7 emulation overlay and verified the intended capture environment.
- Fresh preinstall settings/all-save backup matched every approved source hash and metadata. Target APK and manifest hashes matched the approved plan.
- Installed the exact APK once with `adb -s emulator-5554 install -r .../Unciv-1271047-debug.apk`; PackageManager returned Success. Readback confirmed versionCode 1271047 and SHA-256 `ecd8c424dc09500f32edd075df71903ab64f6ba9c7ba985bc536e80f21e2c438`; density 420. Original settings and all saves were unchanged after installation.
- **Exactly two explicit settings writes:** apply approved EN template `853e1a055177314c866ae4427e697adeb6f79cab051d31bff0d6160b149c1776`, then restore original bytes `7fc6dff53a9ff0b1a87e75c530edcf98fc000ee3dfa6f04d6feccd7085f9bfa7`. Both were verified. No contingent restoration was needed.
- Two scheduled v2 requests were attempted. No dump or pair was published. Independent final inspection found `files/l10n-hook` absent; the runner's output operations therefore remain attempted, not verified.
- No save copy/replacement/deletion, uninstall, data clear, downgrade, rollback, translation change, extra settings payload, baseline/OCR run, reference confirmation or provider request was executed. The `uv` install/uninstall lines in the capture log refer to the local Python package, not Android application removal.

## Independently verified final state

`after-abort-preservation.json` comes from a separate readback after capture exited, not the runner's incomplete save check.

- Installed: **1271047**, app stopped, adbd **shell**. No automatic rollback was authorized or attempted.
- Original settings SHA-256 `7fc6dff53a9ff0b1a87e75c530edcf98fc000ee3dfa6f04d6feccd7085f9bfa7`; uid/gid/mode/size `10196 10196 600 873` restored exactly.
- All four original save hashes match. Private verified backups remain under `data/issue-47/preinstall-20261022` and `data/issue-47/after-aborted-capture-20261022`, excluded from public evidence.

## Checks not run

Remaining 38 captures, repeat/image/dump comparisons, the nine planned lifecycle requests, forced construction failure, supersession, freeze, ordinary startup/input, retained real main-menu device pytest and candidate generation were **not run** after this failure. No complete device suite or #44 acceptance is claimed. All 20 human reference confirmations and the two D-025 scroll checks remain pending.

The earlier 1469-pass checker suite and fork host checks are dated host-only evidence for their respective commits. The installed APK has now failed device acceptance despite that host evidence. No golden, threshold, state, comparison rule or failure status was changed to conceal it.

## Required next work

Fix the Android-compatible component extraction in the separate fork session, retain provenance semantics, add focused coverage, rerun host tests/build/lint and record a new commit/versionCode/APK hash. Anton explicitly authorized messaging the existing fork chat and the fix; the follow-up was dispatched on 2026-10-22. The fork session is limited to code/host checks and may not access the emulator. A replacement APK, new request namespace and affected command/input hashes require a revised concrete device-operation plan before another installation/capture; no additional device writes are authorized automatically by this report.

## API usage

Live provider requests **0**, tokens **0**, estimated spend **USD 0**. No hold-out or dotenv contents accessed. No push/PR/issue closure.

## Files added by this evidence checkpoint

- `docs/evidence/47/device-attempt-1/after-abort-preservation.json`
- `docs/evidence/47/device-attempt-1/android-crash.txt`
- `docs/evidence/47/device-attempt-1/approved-device-plan.json`
- `docs/evidence/47/device-attempt-1/authorization.json`
- `docs/evidence/47/device-attempt-1/capture-abort.json`
- `docs/evidence/47/device-attempt-1/capture-diagnostic-log.txt`
- `docs/evidence/47/device-attempt-1/capture-exit.json`
- `docs/evidence/47/device-attempt-1/capture-summary.json`
- `docs/evidence/47/device-attempt-1/capture.txt`
- `docs/evidence/47/device-attempt-1/emulator-prepare.txt`
- `docs/evidence/47/device-attempt-1/emulator-start.json`
- `docs/evidence/47/device-attempt-1/evidence-receipt.json`
- `docs/evidence/47/device-attempt-1/install-result.json`
- `docs/evidence/47/device-attempt-1/postinstall-verification.json`
- `docs/evidence/47/device-attempt-1/report.md`
