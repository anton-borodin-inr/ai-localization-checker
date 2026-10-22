# Issue 47 — device attempt 4 Report

**The exact APK control completed and establishes a binary-dependent German Tech Picker difference. Strict acceptance is still failed.** In the same current emulator environment and original German settings, the exact retained 1271045 APK reproduces the historical #41 image with **0 different pixels**. Restoring the exact 1271048 APK reproduces the retained #47 image with **0 different pixels**, including its **72-pixel difference** from #41. This does not establish which source change caused the difference.

## Authorization and frozen inputs

Anton answered “Согласовано” to the separate exact plan-4 proposal. The frozen proposal retains its original historical pending wording; `authorization.json` records the subsequent approval.

- Plan ID `i47-control-86938c3fd2a64844b96330d477918a25`; JSON SHA-256 `4d8b08cef5077e62551813fe4e55678f352ab6a2ad4be15fd720c23fbf32828a`.
- Runner SHA-256 `13db065b92a307b6b83ecbc59a149b65128afcc5083d072bb54083cc97e4f51f`. The approved runner was executed unchanged. Its nine pre-device host recovery-policy tests and static input/missing-approval guards are retained in the output bundle; they were not rerun for this evidence-only change.
- Checker execution commit `3c3231536188d63ffc1ca8b1d939a39014b30938`; production `src/` remains identical to `2e6f595506c8df47e70e270f510793658e2bed1a`.
- Fork target commit `b534a8ae67c390412984869c7a03b168d532c36c`.
- Temporary reference APK 1271045: SHA-256 `16b6e07eaa8f7ca35b71f361f0bdcceb7015987b60e796d15d2f3b53bb61af1a`.
- Restored target APK 1271048: SHA-256 `91d9a900f8204880e590de7fb90f0fc15e2aa5cf5d94a3ae77364497d7b0541e`.
- Both APKs were host-verified debug builds with signer SHA-256 `b4752f8cee80842f55883ca2a9b62ca75c898df5a1b7cefd63959ba1b8fecb99`. Installed bytes/version were independently checked before and after updates.
- Device: `emulator-5554` / `unciv_api34`, API 34, arm64-v8a, 420 dpi, cutout disabled, PNGs 2400×1080.
- Both requests use protocol **v1**, original German settings and identical canonical state SHA-256 `7a30c97c5cce346d532f9630e0b4272070a680ad821a1217fbf27d9ae2e28139`. Exact request argv and unique tokens are retained in `device-plan.json` and the audit.

## Actual operations and observations

Exactly two data-preserving PackageManager updates succeeded, each once, in the approved order: `install -r -d` for the retained 1271045 APK, then `install -r` to restore 1271048. Both exit codes were 0 with `Success`. No retry, uninstall, data clear, alternative APK, ordinary launch or device input occurred. PackageManager manages its own staging/install/cache paths.

Exactly one cold v1 Tech Picker request followed each verified install. Both produced exactly one PANES with `tech-tree,description`, then one READY with `frames=2`, and no ERROR or DUMP. The runner exit code was **0**, with an empty error ledger. No crash, timeout or recovery occurred.

| Build/request | READY time (s) | PNGs | Difference vs historical 1271045 | Difference vs retained 1271048 |
|---|---:|---:|---:|---:|
| 1271045 / i47-control-86938c3fd2a64844b96330d477918a25-0 | 2.143 | 2 | 0 | 72 |
| 1271048 / i47-control-86938c3fd2a64844b96330d477918a25-1 | 1.912 | 2 | 72 | 0 |

Times are from the launch call to matching READY, excluding the fresh logcat barrier. Each pair has two snapshots at least two seconds apart. **18 unchanged strict pixel comparisons** were run offline: 12 comparisons with hash-verified historical/retained/plan-3 inputs, two terminal-repeat comparisons and four cross-build comparisons. Both within-build repeats are identical; all four cross-build pairs differ at the same 72 pixels, exclusive bounding box `[214,239,237,258]`. No threshold, image normalization, reference byte or expected value was changed.

- Both 1271045 PNGs: file SHA-256 `37789ea25484d22c3b14f97dba3520c3fbd5dd87667ba5db9e1ba3daaf6ee4f0`; decoded RGBA SHA-256 `1cb4db62b170fd01e5f80c31589335e215ce69651237effc6ba0e1749544fefa`.
- Both 1271048 PNGs: file SHA-256 `386641974edb33edae4f38e4b186fb4cd1d684730e3fc43adfd35052e52a63c3`; decoded RGBA SHA-256 `8b2d74c23959e568fddfbf9e7c8f15a8da5aa603dfc8e4fa6d7877b74d7efc37`. They also match the plan-3 cold-v1 PNG exactly.
- Historical effective #41 summary SHA-256 `42e1882fe04b5739f7b4e7f628fe27c9a80e9a6426b74b9bf7558efa38119aec` and retained #47 summary SHA-256 `24d748f1334eaf925c8a939ea72da0d8292e72968e22524c14356838e8c96b4e` were checked before comparison. Historical inputs and the baseline were not changed.

For 1271045, SurfaceFlinger latency rows changed between snapshots while PNG pixels and gfxinfo totals remained identical. This is retained pre-#44 control behavior. For 1271048, SurfaceFlinger latency rows, gfxinfo totals and PNG pixels remained identical during the sampled interval. These are bounded observations, not proof of no CPU work or indefinite freezing.

## Preservation and final device state

Preflight checked the exact installed 1271048 source, device pins and original data before either update, then made a verified private settings/save backup. Five data checkpoints cover preflight, both package updates and both captures. Final independent readback repeats installed APK/version, settings bytes and ownership/mode/size, all four saves and all 45 individually pinned prior hook outputs.

- **0 explicit settings writes, 0 save writes, 0 new hook output files.** The single conditional settings restoration was not needed. No `exec-in`, push or uninstall command appears in the device audit. V1 emitted no dump.
- Original German settings SHA-256 `7fc6dff53a9ff0b1a87e75c530edcf98fc000ee3dfa6f04d6feccd7085f9bfa7`, uid/gid/mode/size `10196 10196 600 873`, are unchanged.
- All four save hashes and all 45 prior dump-file hashes are unchanged. Nothing was deleted or overwritten. Private backups remain outside public evidence and archives.
- Final installed build **1271048** and SHA-256 `91d9a900f8204880e590de7fb90f0fc15e2aa5cf5d94a3ae77364497d7b0541e` are verified, app stopped, adbd **shell**. **The emulator is free.** No subsequent device action is included in this report.

## Interpretation and next work

The current environment can reproduce historical 1271045 pixels using the exact old binary and the same current request/settings. Restoring 1271048 restores the same delta. This bounds the observed German difference to the binary/control cycle rather than a failure to reproduce the historical pixels across both binaries. It does not isolate the loading gate, glyph/atlas chronology, any individual code change or a GPU input difference. The earlier synthetic shared-path probe remains mechanism evidence, not proof of the Android cause.

The result was sent to the existing isolated fork chat for further **host-only** source diagnosis and a tested fix or minimal diagnostic proposal. No new device request, telemetry run or APK install is authorized by completing plan 4; another concrete exact-operation approval is required. No speculative font/shader change or equality waiver was made here.

English was not launched; its retained 40-pixel difference remains unresolved. The full 40-image strict acceptance criterion remains failed. The 20 engine-derived review candidates remain unconfirmed; only Anton can edit/confirm a reference. No OCR/model output was used to create a reference or defect label. D-025 human scroll checks remain pending.

## Verification and scope

Actual phase-4 checks are the two exact APK updates/readbacks, two v1 event checks, four retained PNGs, five data checkpoints plus final preservation, and 18 offline pixel comparisons. No production checker or Unciv code changed in this phase. The retained checker full-host tests/lint and fork tests/build/lint were not rerun for documentation/evidence-only additions. The real phase-2 device pytest remains its reported `1 passed`; no device pytest was run in plan 4, which explicitly excludes it. No old version pin or failing test was weakened.

#47 and #44 remain open/incomplete; #44 closes only when #47 merges. D-038 remains Accepted for v1 unchanged, and the two new D-0XX decisions remain Proposed. No baseline/OCR, detector, metric, matching, golden, translation, hold-out or secret access/change; no push, PR, merge or issue closure. **Provider/model requests 0; spend USD 0.**

## Changed files

`docs/engine-text-reference.md` updates the current evidence pointer. This phase adds the following files under `docs/evidence/47/device-attempt-4/`. Full PNGs, frame observations and analysis scripts are preserved in the task output archive; neither APK nor any private backup is committed.

- `authorization.json`
- `execution-result.json`
- `result.json`
- `analysis.json`
- `final-preservation.json`
- `captures.json`
- `data-checks.json`
- `old-build.json`
- `restored-build.json`
- `runner.txt`
- `temporary_reference_debug_downgrade-result.json`
- `restore_current_target_apk-result.json`
- `device-plan.json`
- `report.md`
- `evidence-receipt.json`
