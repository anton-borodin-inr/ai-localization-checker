> Runtime update (2026-10-22): the original 1271047 device attempt failed; original settings/saves were verified restored. See [device-attempt-1/report.md](device-attempt-1/report.md) and [replacement-host/report.md](replacement-host/report.md) for the host-tested 1271048 replacement, which still needs separate device approval. The original offline checkpoint below is historical.

# Issue 47 Report — offline phase

**Status: offline implementation complete; device acceptance and human reference confirmation are pending.** This does not complete #47 or close #44. The emulator was not accessed. Pixel equality, real-screen coverage, repeated device dumps, startup/failure/freeze behavior and the installed signing compatibility remain unverified. Android lint retains 36 warnings (0 errors).

## What changed

Two isolated branches implement the approved plan. No Unciv code was placed in the checker repository. Both repositories use `feat/47-engine-text-dump` and have local commits only; no push/PR/issue closure was performed.

- Checker base: `63b65347b328363f2fdfd51a345a805a6e8c17f9`. The initial implementation is commit `444bff3`; the integration commit contains this report and final evidence.
- Fork exact base: `877b0dc2ee706dbbdb4a17e14b4522408d197390` (`l10n-base-4.22.10`). Final fork commit: `df59cf982e3035f7733d4ffd58e3a56325eb4c82`.
- Built application: `com.unciv.app`, versionName `4.22.10`, versionCode **1271047**. APK SHA-256: `ecd8c424dc09500f32edd075df71903ab64f6ba9c7ba985bc536e80f21e2c438`; 36,240,561 bytes. Debug signer certificate SHA-256: `b4752f8cee80842f55883ca2a9b62ca75c898df5a1b7cefd63959ba1b8fecb99`. These are host build facts, not installed-build evidence. No published #45 allocation conflict was found; unpublished allocation must still be checked before installation/publication.

The fork adds opt-in protocol v2 while preserving v1 extras, state schema and event formats. It observes actual native font-cache submissions and post-layout glyph strings/geometry, including markup, ellipsis, Unicode, alpha, owner bounds and scissor clipping. Known source keys come from forward provenance; unknown keys remain null. Atomic app-private dump publication precedes READY. Geometry describes glyph quads, not opaque ink or later-actor occlusion; unsupported observations fail rather than inventing text.

All four #44 fixes are implemented and host-tested: exactly-once completion/error propagation for construction work; terminal supersession and guards/draining for retired callbacks; initialized-Current guard for font retirement; and frozen rendering after READY/ERROR with normal launch/input waking restored. Device verification of each is still required.

The checker adds strict correlated DUMP transport, preallocated exact hook outputs and directory-operation accounting, PNG/dump/state/build hash bindings, atomic pair markers and repeat-byte failure reporting. `fixtures/stage2/screens-v2.json` pins the actual APK/commit while reusing every old state/settings/save/route. The original v1 manifest is unchanged.

Offline `l10n-reference generate`, `confirm` and `compare-captures` provide editable local review pages, boxes/zoom, explicit review timing, hash-bound browser confirmation exports, portable confirmed bundles and decoded-pixel comparison to the 1271045 capture run. Engine dumps remain candidates. No reference was approved or defect label created by the agent. Repeats remain separate; wrapping/composition follow engine units; partial clipping never completes hidden input and defaults to diagnostic. Numeric/uncertain units remain diagnostic, and known missing source keys alone do not imply uncertain visible glyphs.

## How it was verified

### Checker

The final commands and exit codes are recorded in `checker-checks.json`; raw outputs accompany it.

- `uv run --offline --cache-dir /private/tmp/issue47-uv-cache pytest -q -rs`: **1469 passed, 2 skipped**, exit 0. The existing `test_capture_device.py` and `test_hook_device.py` require `--run-device`; it was intentionally not enabled while #45 owns the emulator.
- Ruff check: exit 0. Ruff format check: exit 0, 81 files formatted. `git diff --check`: exit 0.
- Focused integration run before the full suite: 59 passed. Fake transports cover 40 PNG/dump pairs, stale/missing/corrupt/duplicate outputs, state/build/dimension binding, failure preservation and repeated-dump mismatch. Candidate tests cover repeat/wrapping/composition/clipping/grid rules and confirmation invalidation. Additional tests reject missing/changed directory and temporary-output operations before any device access.
- Both Kotlin-generated samples are consumed verbatim by checker tests. The actual-libGDX/mock-GL sample retains `üЖ...` rather than its hidden full input; the pure geometry sample retains `ü`. Samples are synthetic host evidence, not real screen data. `fork-sample-validation.json` records hashes/provenance; the v2 manifest test validates unchanged input bytes.
- Browser-export interoperability ran with installed host Node.js. Node was not added as a dependency. HTML-like source text remains escaped data.
- Synthetic IAB smoke verified editing, boxes, 2x zoom, explicit start/pause timing and inline human-row add/edit/remove. No Anton checkbox was selected; no real reference or QA measurement was produced. `outputs/review-preview.png` in the task deliverables is explicitly synthetic UI evidence.
- `uv build --wheel --offline --cache-dir /private/tmp/issue47-uv-cache --out-dir ../wheel-check`: exit 0. The packaged JS exactly matches source and the console entry point is present (`wheel-inspection.json`).

### Fork

Inspected final command log, JUnit XML, lint XML, APK metadata/signature output and committed diff. Independently recomputed APK SHA-256 and summed the retained JUnit XML (89 suites). These are evidence inspections; the checker session did not rerun Gradle.

- Fork session ran `./gradlew :tests:test :android:assembleDebug :android:lintDebug --no-daemon` with the Android Studio JBR and task-local Gradle home: exit 0, BUILD SUCCESSFUL (31 s).
- **949 tests: 929 passed, 20 skipped, 0 failures/errors**. All **41 l10n tests passed**, no l10n skips. Existing skipped tests are listed in `fork-test-summary.json`; the committed test diff does not disable existing tests.
- APK assembly and signature verification passed. Android lint: 0 errors, 36 warnings; the full warning XML is retained. No dependency, lint rule or translation was changed.
- Base-to-HEAD diff check passed; fork worktree clean. Forwarded vertices/mock rendering tests establish bounded host behavior, not PNG identity on the emulator.

### Failures encountered and corrected

The initial restricted download failed; the approved retry installed existing locked dependencies only. A mistaken `uv run build` command failed and was corrected to `uv build`. A browser-native add-row prompt did not work in IAB and was replaced with inline creation, then verified. A synthetic pair helper initially hardcoded the old build when consuming the new Kotlin sample; it now uses the supplied dump build, with an explicit negative mismatch assertion. An intermediate format check requested one formatting change; the final check passed. The fork's first focused test failed due to its fixture's unattached Label stage and was corrected before the final full run. The raw Gradle log contains trailing whitespace; it is retained as lossless gzip with a hash receipt, so evidence bytes are unchanged and the staged diff check remains clean. No golden expectations, production checks, device equality rules or existing skip rules were weakened.

## Not run / remaining acceptance

- Zero adb/device commands: no inventory/preparation, install, root/unroot, launch, capture, app-data write, restore or device tests. `--run-device` was not run because the emulator is reserved for #45.
- After Anton explicitly releases the emulator, prepare/review the exact install/backups/settings/save/temporary+final dump/directory operations. Execute writes only after Anton separately confirms that concrete plan, as #41 requires. Changed build/inputs invalidate it.
- Capture 40 pairs (10 screens × EN/DE × forward/reverse) with fresh tokens; require byte-identical repeated dumps and zero changed pixels both between repeats and against corresponding 1271045 images. Preserve all discrepancies.
- Verify real ownership/box alignment and coverage, forced construction-failure latency, real-load supersession, post-terminal framebuffer freeze, normal cold/warm startup/input and restoration. Complete the victory-status/Civilopedia scroll checks.
- Generate 20 candidates; Anton reviews/edits and explicitly confirms accepted references, with per-screen time. No host test can substitute for those confirmations.
- Coordinate the version allocation with #45, assign actual D-0XX numbers against current main, publish linked PRs only after authorization, and arrange independent review. Anton alone merges. Close #44 only through #47's merge.

## Deviations from the task

No scope/methodology changes or new dependencies. Two repository branches/PRs are required by the approved plan. `scene_to_pixels` is retained as an independent coordinate oracle; production dump coordinates are already physical pixels. D-038 remains Accepted and unchanged for v1. D-033, D-037, #10, baseline/OCR, detector, matching, metrics, goldens, prompts/schema and old fixture bytes were not changed.

## Decisions proposed

Two new **D-0XX / Proposed** entries: additive v2 rendered outputs; candidate units and human confirmation. Allocate numbers before merge while accounting for #45/#48. No Accepted decision was revised.

## Open questions for Anton

The next gate is explicit emulator availability, followed by a separate exact-write approval. No plan reapproval is needed for the completed offline implementation. Device acceptance, all human confirmations, publication and independent review remain open.

## API usage

**0 live provider requests; estimated USD 0.** No OCR, detector or baseline runs. No secrets or hold-out data accessed.

## Files changed

### Checker (relative to base)

- `docs/decisions.md`
- `docs/engine-text-reference.md`
- `docs/evidence/47/checker-checks.json`
- `docs/evidence/47/checker-diff-check.txt`
- `docs/evidence/47/checker-format.txt`
- `docs/evidence/47/checker-pytest.txt`
- `docs/evidence/47/checker-ruff.txt`
- `docs/evidence/47/checker-wheel.txt`
- `docs/evidence/47/fork-apk-badging.txt`
- `docs/evidence/47/fork-apk-signing.txt`
- `docs/evidence/47/fork-host-checks.txt.gz`
- `docs/evidence/47/fork-evidence.json`
- `docs/evidence/47/fork-host-draw-sample.texts.json`
- `docs/evidence/47/fork-host-verification.json`
- `docs/evidence/47/fork-lint-results-debug.xml`
- `docs/evidence/47/fork-sample-validation.json`
- `docs/evidence/47/fork-synthetic-sample.texts.json`
- `docs/evidence/47/fork-test-summary.json`
- `docs/evidence/47/offline-report.md`
- `docs/evidence/47/wheel-inspection.json`
- `fixtures/stage2/screens-v2.json`
- `pyproject.toml`
- `src/l10n_checker/hook.py`
- `src/l10n_checker/reference_cli.py`
- `src/l10n_checker/reference_page.py`
- `src/l10n_checker/reference_review.js`
- `src/l10n_checker/screen_capture.py`
- `src/l10n_checker/screen_manifest.py`
- `src/l10n_checker/text_dump.py`
- `src/l10n_checker/text_reference.py`
- `tests/test_text_dump.py`

### Fork (relative to 877b0dc)

- `android/src/com/unciv/app/AndroidGame.kt`
- `buildSrc/src/main/kotlin/BuildConfig.kt`
- `core/src/com/unciv/UncivGame.kt`
- `core/src/com/unciv/l10n/L10nDrawObserver.kt`
- `core/src/com/unciv/l10n/L10nDump.kt`
- `core/src/com/unciv/l10n/L10nGlyphLayoutTrace.kt`
- `core/src/com/unciv/l10n/L10nRequest.kt`
- `core/src/com/unciv/l10n/L10nScreenHook.kt`
- `core/src/com/unciv/l10n/L10nWork.kt`
- `core/src/com/unciv/ui/components/extensions/Scene2dExtensions.kt`
- `core/src/com/unciv/ui/components/fonts/FontImplementation.kt`
- `core/src/com/unciv/ui/components/fonts/Fonts.kt`
- `core/src/com/unciv/ui/components/fonts/NativeBitmapFontData.kt`
- `core/src/com/unciv/ui/components/widgets/ColorMarkupLabel.kt`
- `core/src/com/unciv/ui/components/widgets/L10nSelectBox.kt`
- `core/src/com/unciv/ui/components/widgets/TextFieldWithFixes.kt`
- `core/src/com/unciv/ui/components/widgets/TranslatedSelectBox.kt`
- `core/src/com/unciv/ui/components/widgets/WrappableLabel.kt`
- `core/src/com/unciv/ui/popups/options/OptionsPopupHelpers.kt`
- `core/src/com/unciv/ui/screens/cityscreen/CityConstructionsTable.kt`
- `core/src/com/unciv/ui/screens/newgamescreen/GameOptionsTable.kt`
- `core/src/com/unciv/ui/screens/newgamescreen/MapFileSelectTable.kt`
- `docs/l10n-hook.md`
- `tests/src/com/unciv/l10n/L10nDrawObserverTest.kt`
- `tests/src/com/unciv/l10n/L10nDumpTest.kt`
- `tests/src/com/unciv/l10n/L10nWorkTest.kt`
