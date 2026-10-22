# Issue 47 — device attempt 2 Report (1271048)

**Acceptance is incomplete: the strict comparison against 1271045 failed on Tech Picker.** All 40 PNG/dump pairs were captured successfully; all 20 forward/reverse PNG comparisons and all 20 repeated dump byte comparisons passed. Of the 40 corresponding #41 PNG comparisons, 36 are identical. Tech Picker differs by 40 pixels in English and 72 in German in each pass. The zero-pixel requirement is retained. Human reference confirmation and the two D-025 scroll checks remain pending. No push, PR, merge or issue closure occurred.

## Authorization and provenance

Anton separately approved exact device plan 2 with “Подтверждаю” after the emulator was released. The approval receipt binds the unchanged proposal; its historical awaiting-approval wording has not been overwritten.

- Plan ID: `issue47-device-2-66ac1a0468f962d64057241bfc44f5e5`; plan SHA-256 `b5b78e4262618b992330cd16c1638b413a58a8dd085536eb801c7c9561de62f8`.
- Actual capture-plan bytes: SHA-256 `56d4738ede3e9a0427459125855358533d4fb8a9cf7d79b090f89681e44cf9bb`, activated only after installed-build/data verification.
- Checker revision during device execution: `2e6f595506c8df47e70e270f510793658e2bed1a`; fork revision: `b534a8ae67c390412984869c7a03b168d532c36c`.
- Installed target: **1271048**, APK SHA-256 `91d9a900f8204880e590de7fb90f0fc15e2aa5cf5d94a3ae77364497d7b0541e`; manifest SHA-256 `b80d9a8c976fdff19cb97d300b264efdcc926ea4baeb88d45e7cdbcea929276a`.
- APK v1/v2 signatures verified; signer certificate SHA-256 `b4752f8cee80842f55883ca2a9b62ca75c898df5a1b7cefd63959ba1b8fecb99` matches the source APK. One `install -r` updated 1271047. No uninstall, data clear, alternate APK, downgrade or rollback.
- Device: `emulator-5554`, `unciv_api34`, API 34 arm64-v8a, 420 dpi, cutout disabled, 2400×1080 capture size.

## Actual device results

| Check | Result |
|---|---|
| V1 Tech Picker primer | PANES and one READY, no DUMP; 15.020 s including cold launch/barrier setup |
| Forced construction-background failure | Exactly one ERROR with `forced_construction_background_failure`; 3.963 s, before the 60 s readiness timeout |
| V2 recovery/font reset | Exactly one READY and validated hash-bound Tech Picker dump; 0.872 s |
| Full forward/reverse EN/DE capture | Exit 0; 40/40 successful pairs; 20/20 pixel-identical repeats and 20/20 byte-identical repeated dumps |
| Cold A/B/C supersession | A and B each emitted exactly one ERROR `reason=superseded`; C emitted one READY and valid dump |
| Warm A/B/C supersession | Same result; supersession was actually exercised, not already-terminal requests |
| READY/ERROR freeze observations | Repeated screenshots match. SurfaceFlinger layer latency rows and gfxinfo total-frame counts remained unchanged in each sampled interval of at least 2 s |
| Ordinary warm leave and input | German main menu visible; first Back opened exit confirmation, second dismissed it; process remained running until force-stop |
| Retained ordinary real capture | `pytest --run-device tests/test_capture_device.py -q -rs`: **1 passed**, exit 0, 17.69 s pytest time |
| Old pinned hook test | Not run: `test_hook_device.py` requires 1271045. Its expectation was not weakened; target V1 compatibility was tested by the primer |
| Final preservation | Original settings bytes/metadata and all four save hashes match; installed 1271048 verified, app stopped, adbd shell |

SurfaceFlinger observations support no additional presented layer frames during those samples; they do not prove absence of all CPU work or indefinite freezing. Gfxinfo alone does not measure every libGDX frame. Host unit tests cover the initialized-Current font guard and callback-failure branches; the device recovery is not a direct pre-initialization unit test.

## Strict comparison failure retained

`l10n-reference compare-captures` returned **2**, report status `failed`. The reference is the independently hash-verified effective #41 set: 18 original screen/language pairs plus 2 corrected New Game pairs, including repeats, not one full run after correction. Its summary SHA-256 is `42e1882fe04b5739f7b4e7f628fe27c9a80e9a6426b74b9bf7558efa38119aec`.

| Screen | Language | Changed pixels per pass | Exclusive bounding box |
|---|---|---:|---|
| Tech Picker | EN | 40 | `[751,469,768,484]` |
| Tech Picker | DE | 72 | `[214,239,237,258]` |

The localized differences lie on letter edges. Recorded channel deltas are mostly ±1, with one -2 blue-channel delta. This is an observed property, not an established cause or a reason to waive equality. Unchanged geometry, atlas sampling and rendering precision need host diagnosis. Original PNGs, comparison results, exact pixel values and magnified diagnostic crops are preserved. No input, screenshot, threshold, reference or comparison algorithm was adjusted. No retry tokens were used.

The existing fork chat received the evidence for host-only diagnosis within the approved implementation scope. Any replacement APK requires a new exact-operation plan and separate approval before device use.

## Writes, recovery and final state

Seven normal explicit settings writes executed: EN/DE templates in pass 1, EN/DE in pass 2, exact original restore, retained-test compact English copy of the original, exact original restore. The first five have the capture write/readback journal. The last two are evidenced by the successful unchanged test path, its internal readbacks, approved payload hashes and independent final verification; there is no separate per-command trace for the legacy pytest. The optional contingent restoration was **not used**. No save write occurred.

49 hook requests used exactly the approved namespace: 40 capture requests and 9 lifecycle requests, including one v1. Of the 48 possible v2 outputs, **43 final JSON files are present and no temporary file remains**. The forced failure and four superseded requests published none. Exact declared paths were inspected, with no deletion or wildcard cleanup. Files are retained on device.

Original settings SHA-256: `7fc6dff53a9ff0b1a87e75c530edcf98fc000ee3dfa6f04d6feccd7085f9bfa7`; uid/gid/mode/size: `10196 10196 600 873`. Fresh preinstall, before-legacy and final private backups remain local and are excluded from public bundles. All four save hashes are in `final-preservation.json` and match the approved originals. The new APK remains installed. **The emulator is free.**

## Candidates and remaining gates

`l10n-reference generate` returned 0 and produced 20 portable review pages with exact PNG/dump/pair bytes. They remain unconfirmed candidates for 1271048. There are no unknown-owner draws in these observed dumps, but that does not prove full screenshot coverage or absence of later opaque occlusion. Known source-key gaps, icon records, clipped spans and empty diagnostic rows remain explicit. No hidden input was promoted into visible reference text.

The agent did not start Anton's review timer, check his confirmation box, export approval or create a confirmed reference. Every candidate still requires Anton's review/edits and hash-bound confirmation, including resolving empty rows. Victory-status/Civilopedia scroll judgments remain Anton-owned. These candidates must not silently become references for a future APK.

The four #44 fixes have the bounded device results above plus host coverage; #44 remains open until #47 merges. D-038 stays Accepted for v1 unchanged; both D-0XX decisions remain Proposed. No baseline/OCR, detector, matching, metric, golden, translation or hold-out work occurred. Provider requests **0**; spend **USD 0**.

## Failures and verification scope

The first local execution wrapper used system Python and failed at importing Pillow before any device command. It was rerun with the existing checker virtual environment, without installing dependencies. The install then completed once. Several host inspection commands used an incorrect relative path and were corrected; these did not alter device state. Capture and lifecycle request batches were not repeated. The failed strict comparison remains failed.

No production checker code changed during this device phase. The prior full host result remains 1470 passed / 2 opt-in device skips, with Ruff check/format passing. This phase separately ran the applicable real capture test above; it does not claim the old pinned hook pytest passed on 1271048. Host checks must be refreshed after any later code change. Evidence and documentation changes are checked with `git diff --check` before commit.

## Evidence index

`authorization.json`, exact plan files, install result/postinstall verification, `primer-result.json`, `lifecycle-result.json`, `freeze-analysis.json`, `ordinary-visual-inspection.json`, capture summary and write journal, `against-1271045.json`, `tech-picker-pixel-deltas.json`, `legacy-device-test.txt`, `execution-ledger.json`, `final-preservation.json`, `review-hashes.json` and `candidate-diagnostics.json` preserve the results. Raw runner scripts/command logs and public images are in the task output evidence archive; private backups are excluded. The prior failed 1271047 attempt remains intact.
