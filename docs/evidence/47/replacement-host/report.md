# Issue 47 - Android crash fix / replacement host Report

**1271048 is host-tested only and awaits fresh exact-operation approval.** The first device attempt on 1271047 failed with zero successful PNG/dump pairs; see [../device-attempt-1/report.md](../device-attempt-1/report.md). The device still has 1271047 installed, app stopped and adbd shell. Original settings/metadata and all four save hashes were independently verified restored. No replacement device acceptance is claimed.

## What changed

Fork commit `b534a8ae67c390412984869c7a03b168d532c36c` continues the same branch from failed implementation `df59cf982e3035f7733d4ffd58e3a56325eb4c82`, ultimately based on `877b0dc2ee706dbbdb4a17e14b4522408d197390`. It replaces runtime component regex extraction with a literal brace scanner. Direct known whole keys retain precedence; otherwise only forward-known innermost nonempty components are retained, with order/repeats and Unicode/newline/placeholder behavior preserved. Unknown or malformed spans invent no provenance. No reverse translation lookup is added.

Eight new tests exercise the actual v2-active metadata bind path, including blank/unbraced input and v1/ordinary/uninitialized guards. The intentional regression fails on the old dynamic regex construction and passes after the fix. The audit found no analogous invalid literal-brace pattern in other newly introduced regex sites. Samples use a separate output folder, preserving 1271047 artifacts unchanged.

The checker pins real replacement metadata in `screens-v2.json`, moves the explicit operational build expectation to the actual replacement version and adds a third verbatim Kotlin host-draw fixture. Both old fixtures remain unchanged. No production checker runtime source, v1 manifest/state/settings/save, baseline/OCR, translation, matching, metric, golden, detector prompt/schema or Accepted decision changed.

## Provenance and verification

- Application: `com.unciv.app`, 4.22.10 / **1271048**; APK 32,546,363 bytes; SHA-256 `91d9a900f8204880e590de7fb90f0fc15e2aa5cf5d94a3ae77364497d7b0541e`.
- Signer certificate SHA-256 `b4752f8cee80842f55883ca2a9b62ca75c898df5a1b7cefd63959ba1b8fecb99`, matching installed 1271047. APK v1/v2 signature verification passed.
- APK content inspection: 339 entries in both builds, no added/removed entries. Every asset/native-library/resource byte is unchanged. Only AndroidManifest.xml, classes2.dex and signing files differ. The smaller ZIP does not reflect missing content. This is not PNG-equivalence evidence.
- Reported #45 probes are 1271451-1271458, distinct from 1271048. This was read from the completed #45 chat without messaging or changing that task.
- Fork final `:tests:test :android:assembleDebug :android:lintDebug --no-daemon`: exit 0, BUILD SUCCESSFUL in 31 s. **937 passed, 20 existing skipped**, 0 failures/errors; all **49 l10n tests passed**, including 8 new metadata tests. Lint: **0 errors, 36 warnings**, with the same warning IDs and test skip names as the prior host run.
- Intentional red regression on old code: exit 1, one test/one failure. Focused fixed l10n run: exit 0, 49 passed. No golden expected result, skip policy or production check was weakened.
- Parent independently read final JUnit XML (90 suites, 957 tests), recomputed APK SHA-256, inspected signatures, verified sample bytes/hash and compared APK members. These are evidence inspections; the parent did not rerun Gradle.
- Checker full host run after metadata/sample/test changes: **1470 passed, 2 skipped**, exit 0. Both skips are existing opt-in device tests; no replacement APK has device approval yet. Ruff check/format passed (82 files). Commands and raw output are retained here.
- The old wheel's production Python/JS source is unchanged by this follow-up. No dependency was added; no wheel rebuild is claimed for these metadata/test/evidence changes.
- Raw Gradle logs are preserved in lossless gzip with uncompressed hashes. Diff checks are performed before commit.

## Remaining gates

The replacement needs a fresh plan from installed 1271047, with its real APK hash and new request namespace. The proposed v1/fault/v2-recovery primer runs on original German settings before capture-template writes; stop on primer failure. Full 40-pair capture, PNG equality with the effective corrected #41 set and repeats, dump byte equality, #44 lifecycle/freeze/normal-start checks and restoration still need device verification. All 20 human reference confirmations and both D-025 scroll checks remain pending.

The first approved batch was not continued on changed code/APK. The user's original gate and D-024 require revised exact-operation approval. No replacement installation, launch, app-data write, push/PR or issue closure has occurred.

## Deviations, decisions and API usage

No scope or methodology change. This is an implementation portability fix within approved #47. Both D-0XX entries stay Proposed; D-038 remains Accepted for v1. No new decision is needed for the private extraction algorithm. Live provider requests **0**, estimated spend **USD 0**. No hold-out or dotenv contents accessed.

## Files changed by this follow-up

Fork (relative to failed df59cf9):

- `buildSrc/src/main/kotlin/BuildConfig.kt`
- `core/src/com/unciv/l10n/L10nDrawObserver.kt`
- `docs/l10n-hook.md`
- `tests/src/com/unciv/l10n/L10nDrawObserverTest.kt`
- `tests/src/com/unciv/l10n/L10nDumpTest.kt`
- `tests/src/com/unciv/l10n/L10nTextMetadataTest.kt`

Checker (after failure-evidence checkpoint):

- `docs/engine-text-reference.md`
- `docs/evidence/47/fork-fixed-host-draw-sample.texts.json`
- `docs/evidence/47/offline-report.md`
- `docs/evidence/47/replacement-host/apk-content-comparison.json`
- `docs/evidence/47/replacement-host/checker-checks.json`
- `docs/evidence/47/replacement-host/checker-format.txt`
- `docs/evidence/47/replacement-host/checker-pytest.txt`
- `docs/evidence/47/replacement-host/checker-ruff.txt`
- `docs/evidence/47/replacement-host/fork-apk-badging.txt`
- `docs/evidence/47/replacement-host/fork-apk-signing.txt`
- `docs/evidence/47/replacement-host/fork-focused-after-fix.log.gz`
- `docs/evidence/47/replacement-host/fork-host-checks.log.gz`
- `docs/evidence/47/replacement-host/fork-host-verification.json`
- `docs/evidence/47/replacement-host/fork-lint-results-debug.xml`
- `docs/evidence/47/replacement-host/fork-prior-artifact-hashes.json`
- `docs/evidence/47/replacement-host/fork-regex-audit.md`
- `docs/evidence/47/replacement-host/fork-regression-before-fix.log.gz`
- `docs/evidence/47/replacement-host/fork-regression-before-fix.xml`
- `docs/evidence/47/replacement-host/fork-sample.texts.json`
- `docs/evidence/47/replacement-host/fork-test-summary.json`
- `docs/evidence/47/replacement-host/fork-version-allocation.json`
- `docs/evidence/47/replacement-host/report.md`
- `fixtures/stage2/screens-v2.json`
- `tests/test_text_dump.py`
