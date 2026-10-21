# Issue 45 report — in progress

**Not complete:** all eight APKs are built and host-verified; separately approved installations/captures remain pending. No v1 class proposal is made before mutation evidence. No PR has been opened or pushed.

## What changed

- Isolated checker branch `feat/45-defect-type-probes` from `63b65347b328363f2fdfd51a345a805a6e8c17f9`.
- Isolated fork probe branch `probe/45-defect-types`, pinned to `877b0dc2ee706dbbdb4a17e14b4522408d197390`. Never merge this probe branch into the clean base.
- Eight APK builds passed; `apk-verification.json` verifies all versionCodes, signatures matching the original APK, exact packaged translations against each fork commit, translation-only source diffs, and arm64/DEX presence. No APK has been installed.
- Eight translation-only variants, exact keys/old/new values, EN applicability and versionCodes 1271451–1271458 are in [probe-design.json](probe-design.json). The fork's tracked source changes are translation files only. An external init script sets Android APK versionCode without editing tracked Kotlin or Gradle files.
- Unchanged D-038 client reused from task-specific scripts. No hook, l10n-capture implementation, OCR baseline, matching, metrics, prompt/schema, labels or goldens changed. No dependencies added.
- Frozen v1 prompt, schema, sent wrapper and provider-source hashes are in [frozen-contract.json](frozen-contract.json).

## How it was verified

- Before device writes: exact installed 1271045 APK backed up and SHA-256 verified against the D-039 manifest; private settings and both internal/external file archives independently read back. `run-as` was used, without root. Private backups are retained outside committed evidence.
- Anton separately approved the clean-control operation plan SHA-256 `11c62a89ffb07fdf22504061e4c3d116e4392c8d727737da5ca0cd7b9a3b7c40` in this task chat.
- The first settings-transfer attempt failed readback before any hook request or screenshot. The exact original settings were restored; all saves were verified unchanged. Audit retained under `captures/clean/`.
- The corrected `adb shell -T run-as tee` transfer passed. Four controls were captured, each with matching screen/request READY, foreground/cutout checks, decoded PNG validation and 2400x1080 dimensions. The whole four-image block restored the original settings byte for byte and verified all saves unchanged. Audit: `captures/clean-retry-2/capture-audit.json`.
- Before new helper tests: `.venv/bin/python -m pytest -q`: 1448 passed, 2 skipped (device tests, not requested by this preparation). Focused helper checks after capture/runner changes: 7 passed. After the current helper changes: `.venv/bin/python -m pytest -q`: 1455 passed, 2 skipped (device tests). Evidence: `pytest-checkpoint.txt`.
- `.venv/bin/ruff check .`, `.venv/bin/ruff format --check .`, `git diff --check`: passed at this preparation checkpoint. Later edits need fresh checks.

## Clean controls and model stability

The [gallery](gallery.html) contains unchanged original PNGs. “Clean control” means no injected translation mutation, not an agent-created human clean label.

Each of the four controls was sent twice with the frozen v1 contract and `--max-requests 1`. All eight runs were checked/readable. One of two German city-production runs returned `truncated_text` for `Kann Land Verbesserungen auf Feldern bauen` at bottom-right, confidence 0.6; the second returned no findings. Visual inspection shows the complete string wrapped in that panel. Preserve this discrepancy without retuning, rerunning it away or turning observations into labels. The other six runs returned no findings. These are stability observations on controls, not precision/recall or a general quality claim.

Each run's raw response, result, prompt, sent wrapper, metadata and CLI output are committed in `runs/<run-id>/`. [clean-runs.json](clean-runs.json) lists every returned finding and readability field alongside usage/cost.

## Deviations from the task

- No scope deviation. The first failed capture and initial failed Gradle-wrapper attempt are retained as failures, not successes.
- Copying an old isolated Gradle cache was stopped because it was too slow. A fresh task-local Gradle cache uses the same pinned wrapper/plugins/dependencies; no project dependency changed.
- Device transfer uses `run-as` rather than temporary root; app data ownership is retained and read back.

## Decisions proposed

- `D-0XX`: Anton's dev assignment of tech-picker and city-production; number assigned at merge.
- The proposal superseding D-006's class count and D-020's class list remains pending the mutation evidence. Anton owns definitions, boundaries and acceptance.

## Open questions for Anton

Pending exact-install/capture approval for each prepared probe; restoration to original 1271045 is also an explicit device gate. No install has been performed yet. The first install/capture plans were explicitly approved; their first preflight stopped because the emulator process was absent. No app replacement or app-data write occurred. Anton separately approved restarting the same AVD without snapshots or wipe and running the standard cutout preparation; pre-task app data must be rechecked before the approved install proceeds.

## API usage

Current total: 8 / 100 requests, peak tariff estimate USD 0.002773536, unknown-cost reserve USD 0, maximum task spend USD 1.00. Token totals: `{"prompt_tokens": 14688, "completion_tokens": 270, "total_tokens": 14958, "prompt_cache_hit_tokens": 6656, "prompt_cache_miss_tokens": 8032}`.

Tariffs and the conservative pre-request reservation are recorded in [budget-policy.json](budget-policy.json), verified against [official DeepSeek pricing](https://api-docs.deepseek.com/quick_start/pricing/). Estimates are not billing receipts. Every live command loads the key with `uv run --env-file .env`; the agent does not read, print or copy it.

| Run id | Screenshot | Requests | Peak USD |
|---|---|---:|---:|
| 20261021T185946Z-c21c92 | city-production__de__2400x1080__probe-clean__1271045.png | 1 | 0.0006264 |
| 20261021T185948Z-4ba077 | city-production__de__2400x1080__probe-clean__1271045.png | 1 | 0.000097584 |
| 20261021T185950Z-bbbee4 | tech-picker__de__2400x1080__probe-clean__1271045.png | 1 | 0.0005868 |
| 20261021T185953Z-6b3140 | tech-picker__de__2400x1080__probe-clean__1271045.png | 1 | 0.000097584 |
| 20261021T185955Z-e3cd99 | city-production__en__2400x1080__probe-clean__1271045.png | 1 | 0.0005868 |
| 20261021T185957Z-cbf5a7 | city-production__en__2400x1080__probe-clean__1271045.png | 1 | 0.000097584 |
| 20261021T190000Z-d845c8 | tech-picker__en__2400x1080__probe-clean__1271045.png | 1 | 0.0005868 |
| 20261021T190002Z-c1ff72 | tech-picker__en__2400x1080__probe-clean__1271045.png | 1 | 0.000093984 |
