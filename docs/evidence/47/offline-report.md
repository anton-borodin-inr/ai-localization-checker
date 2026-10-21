# Issue 47 offline Report (checker checkpoint)

**Status:** checker host implementation is verified. Fork integration/build metadata, all device acceptance, independent PR review and Anton's reference confirmations remain pending. This is not completion of issue #47 or #44.

## What changed

Added the opt-in v2 DUMP transport while retaining v1's extras/state/events, strict dump validation, preallocated device-output paths, raw-dump/PNG/hash sidecars and repeated-byte checks. Added offline `l10n-reference generate`, `confirm` and `compare-captures`: engine-only candidates, local editable/zoomable review pages, hash-bound explicit human exports with timing, portable source assets and decoded-pixel comparison against the 1271045 capture run. No reference was approved by the agent.

## How it was verified

- Full host suite after checker source changes: **1463 passed, 2 skipped**, exit 0. Both skips are the existing device tests (`test_capture_device.py` and `test_hook_device.py`), intentionally not enabled while #45 occupies the emulator. See `checker-checks.json` and command output files here.
- Ruff check and format check: exit 0. `git diff --check`: exit 0.
- Focused fake-adb/engine/transport/reference tests passed. They cover all 40 fake pairs, corrupt/missing/stale outputs, deterministic versus changed dumps, exact state bytes, coordinate/grid rules, repeated and wrapped units, clipped hidden-input exclusion, explicit decoration grouping and hash invalidation after edits or changed image bytes.
- Browser export interoperability ran with the installed host Node.js; no Node dependency was added to the Python tool. Source text resembling HTML/script is safely embedded as data.
- Local IAB smoke on an explicitly synthetic image: text editing, glyph/owner controls, 2x image zoom, timer start/pause, inline human-row addition/edit/removal. No Anton confirmation checkbox was selected and no real reference or QA timing was produced. The native prompt did not work in IAB; replaced it with inline row creation and verified that path.
- `uv build --wheel --offline` succeeded; inspected the wheel to confirm the JS asset and `l10n-reference` entry point are packaged. An earlier mistaken `uv run build` invocation failed and was corrected. Initial network-restricted dependency download failed; the approved retry installed only existing locked dependencies.
- Device tests/captures, APK installation, forced construction failure, cold/warm startup and PNG equality against 1271045: **not run**, waiting for emulator release and exact-write confirmation.

The suite is host evidence, not evidence that all ten physical screens are fully covered by the engine observer or that new PNGs match 1271045. Those remain required device checks after the fork build is integrated.

## Deviations from the task

No scope/methodology changes and no new dependencies. Two coordinated repository branches/PRs are needed, as the approved plan specifies. `scene_to_pixels` is retained as a small independent coordinate oracle for cross-language contract tests; production dumps already use physical pixels. Existing v1 fixture/settings/state bytes and Accepted decisions are unchanged.

## Decisions proposed

Two entries named D-0XX, both Proposed: additive hook v2/rendered outputs; engine candidate units/human confirmation. Assign actual numbers only when rebasing before merge. D-038 stays Accepted for v1; D-033's status, D-037 and the #10 reference are unchanged.

## Open questions / gates for Anton

No additional input is needed for the remaining host integration. Device work begins only after Anton says the emulator is free, and then requires approval of its exact writes. Candidate references require Anton's later per-screen review/confirmation. Push/PR publication and independent review have not happened. Do not close #44 before #47 merges.

## API usage

0 live provider requests; USD 0. No detector, OCR or baseline runs. No hold-out or `.env` contents were accessed.

## Files changed at this checkpoint

- `docs/decisions.md`
- `docs/engine-text-reference.md`
- `docs/evidence/47/checker-checks.json`
- `docs/evidence/47/checker-diff-check.txt`
- `docs/evidence/47/checker-format.txt`
- `docs/evidence/47/checker-pytest.txt`
- `docs/evidence/47/checker-ruff.txt`
- `docs/evidence/47/offline-report.md`
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
