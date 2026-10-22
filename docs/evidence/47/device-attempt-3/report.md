# Issue 47 — device attempt 3 Report

**The bounded diagnosis completed, but strict acceptance remains failed.** All four German Tech Picker requests on the same installed 1271048 reached exactly one READY. V1 and v2, cold and warm, produced identical PNG pixels. Every image retains the same 72-pixel difference from the effective #41/1271045 German image. The experiment found no protocol-dependent or cold/warm-order-dependent difference in these samples. It does not establish a root cause.

## Authorization and pins

Anton explicitly answered “Подтверждаю план №3” to the separate exact-operation question. The original proposal bytes remain unchanged; `authorization.json` records the approval rather than rewriting the proposal’s historical pending status.
- Plan ID: `i47-diag-78ba3557bc0d407888e7bd8e4ad463e4`; JSON SHA-256 `ec3cf8f267e7b0770feea342f72852aa73d3448720797d247cd3918ad941fb6e`.
- Runner SHA-256 `c7069568159d2456854aa1156ce0b5e1645d36b64e2be78c235562b9c03ac8ca`; existing host validation and missing-approval guard passed before device use.
- Checker during execution: `981d73dcda9181f470ddd08a8280b750c1307d69`; production runtime remains identical to `2e6f595506c8df47e70e270f510793658e2bed1a`.
- Fork/APK: `b534a8ae67c390412984869c7a03b168d532c36c`, **1271048**, APK SHA-256 `91d9a900f8204880e590de7fb90f0fc15e2aa5cf5d94a3ae77364497d7b0541e`. No build, install, downgrade, rollback or data clear.
- Manifest SHA-256 `b80d9a8c976fdff19cb97d300b264efdcc926ea4baeb88d45e7cdbcea929276a`; exact canonical state SHA-256 `7a30c97c5cce346d532f9630e0b4272070a680ad821a1217fbf27d9ae2e28139` in all four requests.
- Device checked: `emulator-5554` / `unciv_api34`, API 34, arm64-v8a, 420 dpi, disabled cutout, 2400×1080 captures; original German settings.

## Actual observations

| Request | Terminal time (s) | Difference vs 1271045 | Difference vs retained 1271048 |
|---|---:|---:|---:|
| cold-v1 | 1.999 | 72 | 0 |
| warm-v2-after-v1 | 0.848 | 72 | 0 |
| cold-v2 | 2.304 | 72 | 0 |
| warm-v1-after-v2 | 0.626 | 72 | 0 |

Times run from the launch call to the matching terminal, excluding logcat-barrier setup. SDK runner exit code: **0**. All four have the expected PANES; the two v1 requests produced no DUMP, the two v2 requests each produced one valid hash-bound DUMP before READY. No crash, timeout, retry or extra request occurred.

Eight PNGs were retained: two snapshots per request at least 2 seconds apart. All four terminal-repeat comparisons and all six cross-mode comparisons have **0 changed pixels**. Every PNG decoded RGBA SHA-256 is `8b2d74c23959e568fddfbf9e7c8f15a8da5aa603dfc8e4fa6d7877b74d7efc37`. All eight differ from 1271045 at the same **72 pixels**, exclusive bounds `[214,239,237,258]`. The effective #41 and retained #47 input-summary hashes and both reference-image hashes were checked before offline comparison. No screenshot or comparison threshold was changed.

Both v2 dumps are byte-identical to each other and the retained 1271048 German dump: SHA-256 `1d6e5c2e7b62e3007445ea846d1afe3ba726530b4d0a5ae3ef86e73c6cd59fdb`. Strict schema, state, language, build and dimensions were validated. Two exact declared final files exist (145635 bytes each); neither declared temporary file remains. V1 creates no dump. No file was overwritten or deleted.

For each request, the SurfaceFlinger layer latency rows and gfxinfo total-frame counts remained unchanged between the sampled snapshots. This supports no additional presented frames during these intervals; it does not prove absence of CPU work or indefinite freezing.

## Interpretation and limitations

The observer-only hypothesis is not supported as the sole necessary explanation of this German delta: it also occurs with protocol v1, where v2 draw collection/dump publication is disabled. The shared 1271048 font/lifecycle path and the rendering environment remain candidates. A shared change in loading draws or glyph/atlas warmup chronology is a hypothesis, not an established cause. The four source states are logically identical and the experiment changed no font, atlas, filter, shader, fixture or threshold.

English was not launched in this plan. Its earlier 40-pixel delta remains a retained failure; this German experiment cannot establish its cause or resolve the full 40-image acceptance criterion. No new reference or defect label was created. The existing 20 review candidates remain unconfirmed and tied to 1271048. D-025 scroll checks remain human-owned.

The evidence was sent to the existing fork chat for continued host-only diagnosis within the approved implementation scope. Any later APK/telemetry run or new request namespace requires another exact-operation approval. No further device action is authorized by this report.

## Writes, preservation and final device state

- **0 installs, 0 explicit settings writes, 0 save writes.** The conditional original-settings restoration was not needed. Audit commands contain no `exec-in`, install, uninstall or push.
- Exactly four approved hook requests and two v2 output publications; no unlisted input event, ordinary launch, language/template change or device pytest.
- The fresh preflight settings/save backup remains private, outside public bundles. Each request checked unchanged original settings bytes. The final independent readback checked settings bytes/metadata and all four saves again.
- Original settings SHA-256 `7fc6dff53a9ff0b1a87e75c530edcf98fc000ee3dfa6f04d6feccd7085f9bfa7`, uid/gid/mode/size `10196 10196 600 873`; all saves match their approved hashes.
- Final APK 1271048 and APK hash verified. App stopped, adbd **shell**, new hook files retained. **The emulator is free.**

## Verification scope and remaining work

No production checker or Unciv code changed in this device phase. The previously retained checker full-host and fork build/test/lint results were not rerun for documentation/evidence-only changes. The phase-2 main-menu device test remains the real `1 passed` result; it was not repeated because plan 3 explicitly excluded device pytest. The old 1271045-pinned hook test was not weakened or run against the new version. Actual phase-3 verification is the four READY/dump checks, 26 strict offline pixel comparisons, dump-byte comparison and final preservation above.

The strict #41 comparison remains failed. #47 and #44 are not complete or closed; #44 closes only when #47 merges. D-038 stays Accepted for v1 unchanged and the two D-0XX entries stay Proposed. No provider/model calls, spend, baseline/OCR, detector, matching, metric, golden, translation, hold-out, secret access, push/PR or merge. **Provider requests 0; spend USD 0.**

## Changed files in the checker

`docs/engine-text-reference.md` gains a current-evidence pointer. This phase adds the public files listed below under `docs/evidence/47/device-attempt-3/`; full PNGs, dumps, driver and audit commands are preserved in the task output archive, without private backups.

- `authorization.json`
- `execution-result.json`
- `result.json`
- `analysis.json`
- `final-preservation.json`
- `output-readback.json`
- `runner.txt`
- `report.md`
- `evidence-receipt.json`
- `device-plan.json`
- `diagnostic-runner.sha256`
