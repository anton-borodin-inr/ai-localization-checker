# Issue 47 — device attempt 5 Report

**The diagnostic matrix completed, but strict acceptance remains failed. The tested alternate loading gate does not correct the German Tech Picker delta.** All eight PNGs from four cold v1 requests are identical to retained 1271048 and still differ from #41/1271045 at the same 72 pixels. Telemetry off/on does not change PNGs in either gate in these samples. Selected CPU glyph/atlas/cache/batch observations also match between the two on-arms; this is not proof of GPU equality or a root cause.

## Authorization and pins

Anton answered “Действуй” to the separate exact final plan-5 question. `authorization.json` binds that answer; the frozen proposal retains its historical not-authorized wording.

- Plan ID `i47-diag-f060af2f0b2d453c8a03a4c23d08d7ea`; JSON SHA-256 `301b207483112563fda281da03181f31440a4e7b867a631e19541eefed87aa15`.
- Approved runner SHA-256 `1f8960cfb2f0c4a6f74390489d48f60b07fb7ede6b12cb96cec7edba4869ac9d`, executed unchanged. SDK process session 89970 exit **0**, empty error ledger.
- Checker execution commit `d8e40256c0a02b585d30a18a94ca6b7e68c0da45`; production runtime unchanged from device-tested `2e6f595506c8df47e70e270f510793658e2bed1a`.
- Diagnostic fork commit `c8eb6fb7e42fc29cdc2b20a813f475d645fbf4be`; temporary APK **1271049**, SHA-256 `cdf597ffc34f8b30cc0f4c2600ba0879851cd8fa0e89967ffa410b5ea9a138f1`.
- Original/final target **1271048**, SHA-256 `91d9a900f8204880e590de7fb90f0fc15e2aa5cf5d94a3ae77364497d7b0541e`.
- Both APKs are debug builds with verified signer certificate SHA-256 `b4752f8cee80842f55883ca2a9b62ca75c898df5a1b7cefd63959ba1b8fecb99`; installed bytes/version read back after each update.
- Device preflight: emulator-5554 / unciv_api34, API 34, arm64-v8a, 420 dpi, cutout disabled, 2400×1080 PNGs. All arms use original German settings and canonical state SHA-256 `7a30c97c5cce346d532f9630e0b4272070a680ad821a1217fbf27d9ae2e28139`.

## Operations and PNG observations

Exactly two approved PackageManager updates succeeded once each: install diagnostic 1271049 with `-r`, then restore exact 1271048 with the explicitly approved debug downgrade `-r -d`. Both returned exit 0 / Success. No retry, alternative APK, uninstall, data clear, ordinary launch, input or device pytest occurred.

Exactly four approved cold requests reached one PANES and one READY (`frames=2`), no ERROR or DUMP. Each on-arm emitted one valid hash-bound DIAGNOSTICS before READY; off-arms emitted none. No crash, timeout, incomplete telemetry or recovery occurred.

| Arm | Mode | READY time (s) | Difference vs #41 | Difference vs retained 1271048 |
|---|---|---:|---:|---:|
| current-off | current-off | 1.984 | 72 | 0 |
| current-on | current-on | 2.410 | 72 | 0 |
| owned-off | owned-loading-off | 1.908 | 72 | 0 |
| owned-on | owned-loading-on | 2.433 | 72 | 0 |

Times start at the launch call and exclude logcat-barrier setup. Two snapshots per arm were taken at least two seconds apart. All eight decoded RGBA hashes equal `8b2d74c23959e568fddfbf9e7c8f15a8da5aa603dfc8e4fa6d7877b74d7efc37`.

The unchanged zero-pixel comparator produced **50 comparisons**: 40 against five hash-verified historical/retained/plan-3/plan-4 images, four within-arm repeats and six cross-mode comparisons. The 16 comparisons against the two historical 1271045 inputs each differ at exactly 72 pixels, exclusive bounding box `[214,239,237,258]`. All other 34 comparisons are identical. No screenshot, threshold, normalization, expected value or reference was changed.

The intervention was exercised: current-on records **23 blocked-loading / 0 ordinary-loading** phases; owned-on records **23 ordinary-loading / 1 blocked-loading** phase. The latter retains the late published-target barrier. Thus this bounded negative result is not explained by an unused alternate arm.

For all four arms, sampled SurfaceFlinger latency rows, gfxinfo frame totals and repeat PNGs remained unchanged after READY. This supports stability during those sampled intervals, not no CPU work or indefinite freezing.

## Sidecar readback and selected CPU comparisons

- **current-on**: SHA-256 `c60157e979cbadc6746b4dd8f343763c1ebe5684acc3593950f9272610fcfcce`, 5670546 bytes, 280 events / 24 hook callbacks, complete=true / no issues.
- **owned-on**: SHA-256 `c6e7921b8b2f1b3fae18026fc98ac20552ea23fb2308074ccffa5543c82368da`, 5670622 bytes, 282 events / 25 hook callbacks, complete=true / no issues.

Both raw sidecars passed strict event hash and token/state/build/mode/schema/language/protocol checks, sequence/cap checks and independent base64/size/RGBA hash verification. Each embeds one 1024×1024 CPU atlas page (4,194,304 bytes), SHA-256 `06e9b545502da9fe05cc5db519258ef1638b34184928c7a82e910d3de63f3d4d`. Actual callbacks stay below the frozen 1,024 diagnostic capacity; no limit was changed during execution.

`cpu-comparison.json` makes the projection explicit. It excludes only transport chronology/object-name fields `seq`, `frame`, `phase`, `handle`, `shader_handle`; raw sidecars remain unchanged. Equality holds for:

- Actual glyph creation order, raster hashes/dimensions, packing positions, UV/advance/offset bits.
- Full/subupload input records and actual mipmap-regeneration records, including their combined ordered glyph/upload/mipmap timeline.
- Affected Animal Husbandry/Tierhaltung cache glyphs, vertex bits, live/layout scales and projection/transform matrices.
- Real batch flush vertex hashes/counts/slots, shader source hash, framebuffer/viewport/scissor observations and LOD bits.
- Atlas checkpoints and final embedded CPU atlas pages.

Each on-arm records 91 glyph creations, 89 subuploads, two full uploads, three mipmap regenerations, two affected cache draws and 14 real batch flushes. Raw sidecars are not byte-identical: request/mode and callback/phase counts differ (280 versus 282 events). These selected equal CPU inputs do not cover every earlier draw/framebuffer effect, GPU mipmap texel or final shader output. No Android telemetry was collected from the old 1271045 binary, so this is not a direct CPU-input comparison with that binary.

## Data preservation and final state

The preflight verified source APK/device/original data and made a private byte-checked settings/save backup. Seven data checkpoints cover preflight, diagnostic update, four arms and final target restore, followed by an independent final preservation readback.

- **0 normal/explicit settings writes, 0 save writes, 0 v2 dump files.** The one conditional settings restoration was not needed. Audit commands contain no exec-in, push or uninstall.
- Original settings SHA-256 `7fc6dff53a9ff0b1a87e75c530edcf98fc000ee3dfa6f04d6feccd7085f9bfa7`, uid/gid/mode/size `10196 10196 600 873`, unchanged. All four save hashes and all 45 pre-existing hook-file hashes are unchanged.
- Exactly two declared diagnostic final paths are retained with the hashes above. Both declared temporary paths and all off-arm final/temp paths are absent. No file was overwritten, deleted or cleaned up. Future plans must preserve **47 total retained JSON outputs** (45 original dumps plus two diagnostic sidecars).
- Exact 1271048 APK/version restored and verified, app stopped, adbd **shell**. **The emulator is free.** Private backups are excluded from public evidence and archives.

## Interpretation and remaining work

The new build's current-off arm reproduces retained 1271048, and both off/on controls are pixel-identical. Within this bounded matrix, the tested current-owner loading fallback is insufficient to restore #41. A production gate correction is not justified by these observations. Plan 4 still establishes binary dependence; the broader common font/cache/layout/build path remains to be isolated. The result was sent to the existing fork chat for continued host-only source diagnosis and a discriminating experiment, with no further device authorization.

English was not launched and its earlier 40-pixel delta remains unresolved. The strict 40-image acceptance criterion remains failed. Twenty engine-derived candidates and D-025 human scroll checks remain unconfirmed; only Anton can approve a reference. No OCR/model output supplies reference content. #47/#44 remain incomplete, and #44 closes only when #47 merges.

No production checker/Unciv code changed in this device phase. The retained 26 parent host tests and fork host tests/build/lint were not rerun for evidence-only changes. No device pytest was run because plan 5 explicitly excludes it; the earlier real phase-2 `1 passed` remains its own evidence. No failing test or old version pin was weakened.

D-038 remains Accepted for v1 unchanged; two new D-0XX decisions remain Proposed. No baseline/OCR, detector, matching, metric, golden, translation, label/reference, hold-out/secret, push/PR/merge or issue-closure change. **Provider/model requests 0; spend USD 0.**

## Changed checker files

`docs/engine-text-reference.md` updates the current evidence pointer. This phase adds the following files under `docs/evidence/47/device-attempt-5/`. Full PNGs/raw sidecars/frame observations/scripts/commands are in the task archive; neither APK nor any private backup is committed.

- `authorization.json`
- `execution-result.json`
- `result.json`
- `analysis.json`
- `cpu-comparison.json`
- `final-preservation.json`
- `captures.json`
- `data-checks.json`
- `diagnostic-build.json`
- `restored-build.json`
- `install_diagnostic_apk-result.json`
- `restore_current_target_apk-result.json`
- `runner.txt`
- `report.md`
- `device-plan.json`
- `evidence-receipt.json`
