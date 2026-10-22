# Issue 47 — diagnostic APK host Report

**A temporary diagnostic APK is ready; the Tech Picker cause and strict acceptance remain unresolved.** Exact APK control 4 established a binary-dependent German 72-pixel delta. The new opt-in experiment compares current/owned-loading gate × telemetry off/on, without changing default capture behavior or confirming a reference. Plan 5 is proposed, not authorized or executed.

## Implementation and artifacts

Fork commit `c8eb6fb7e42fc29cdc2b20a813f475d645fbf4be`, isolated `work/Unciv` branch from `877b0dc2ee706dbbdb4a17e14b4522408d197390`. All Kotlin/Java changes remain in that fork. The last device-tested target stays 1271048 / `b534a8ae67c390412984869c7a03b168d532c36c`; the checker v2 manifest is unchanged.

- Diagnostic APK **1271049**, SHA-256 `cdf597ffc34f8b30cc0f4c2600ba0879851cd8fa0e89967ffa410b5ea9a138f1`.
- Signer certificate SHA-256 `b4752f8cee80842f55883ca2a9b62ca75c898df5a1b7cefd63959ba1b8fecb99`; v1/v2 signatures verified. Parent independently ran aapt/apksigner against the copied APK and checked versionCode/debuggable/hash/certificate.
- `l10n_diagnostics` supports current-off/current-on/owned-loading-off/owned-loading-on only for the bounded v1 German Tech Picker experiment. Without opt-in, the current gate and no telemetry remain. Experimental gate and sidecars are outside the v2 text-dump contract.
- The alternate gate permits an ordinary loading draw only for the current nonterminal owner, before target publication, with no leave pending. The pending-work barrier and all four #44 fixes remain. Parent inspected the gate and ownership diff; this is not independent PR approval or device acceptance.
- On-arms publish one bounded, atomic `<token>.diag.json` and emit hash-bearing DIAGNOSTICS before READY. Off-arms create no sidecar. Telemetry covers glyph raster/UV/packing, CPU atlas, uploads/mipmaps, actual affected cache/batch/LOD/shader/state observations. It may perturb timing and requires off/on PNG controls.

## Verification

Fork host test/build/lint completed successfully after the final source change. Parent inspected actual JUnit totals, successful Gradle log and lint XML; it did not independently rerun Gradle.

- **947 passed, 20 existing skips** (967 total), with all **59 l10n tests passed**. Skips are listed in `fork-test-summary.json`.
- Android debug APK built; lint **0 errors / 16 warnings**, severities independently checked.
- Parent compared **205 packaged assets/native-library entries** with exact 1271048: no differences. This does not establish identical DEX behavior, glyph ordering or Android/GPU pixels.
- New host off/on tests use actual NativeBitmapFontData/FontLodBiasBatch with synthetic glyphs and mock GL; equal host mutating-call/cache observations do not prove Android equivalence.
- Fork host sidecar sample: SHA-256 `fc99736e63c9e3b1a1542ec4ef482e5e23737b53a74609abaf5dfea2a95b5d36`, **62 events / one CPU atlas page**. Parent parser independently validated binding types, sequence, embedded base64/dimensions/RGBA hashes. This sample is synthetic transport evidence, never a reference or device coverage.
- Parent controller/event/sidecar tests: **25 passed**, Ruff check/format passed. Static exact-plan validation and missing-approval rejection passed with **0 Device constructor calls**. No plan-5 execution directory or SDK command exists.

The initial Gradle attempt stalled while reading prior class outputs; an isolated build/project cache preserved previous evidence. The first focused test attempt had two harness failures, reported by the fork as missing GameSettings and a one-time shader capability probe; those attempts and the successful reruns are retained. Parent also retained a failed host-test invocation that incorrectly resolved the venv interpreter symlink to system Python without Pillow; the valid rerun used the unchanged checker venv, without a dependency/test/production change. These failures did not access a device and are not reported as successful checks.

## Proposed device gate

Plan ID `i47-diag-f060af2f0b2d453c8a03a4c23d08d7ea`, JSON SHA-256 `2e38e2a5c87f9772948ce3a650833c79aac47c23a22a9ebda57b462ad82ac7d0`. Runner SHA-256 `521a2ab7de546e6bed0599916d188f71a010d921579172ca5b7c1f349eafbbbd`.

The separate exact plan proposes two data-preserving APK updates: install 1271049 once, run four cold v1 German requests with eight PNGs and two exact final/two exact temporary sidecars, then explicitly downgrade to exact 1271048 once with `-r -d`. It includes verified private backup/preservation of original German settings, four saves and 45 old hook files, zero normal settings/save writes, and one contingent exact original-settings recovery. Any failure stops later hooks and uses only the same one listed target restoration, with no retry or cleanup. No device operation is authorized by this host report.

Current-off must first match retained 1271048. Each on-arm must match its off-arm before telemetry can support a gate interpretation. A gate-dependent match with #41 is candidate-correction evidence; it does not complete the 40-image criterion or establish all GPU causes. English and its retained 40-pixel delta are not launched in this proposal. A later production correction/full acceptance run would need its own concrete host evidence and device approval.

## Scope and remaining work

No production checker/test/fixture/runtime change was made here. The old full checker tests/lint and phase-2 device pytest were not rerun for documentation/evidence additions. D-038 remains Accepted and unchanged; the two new D-0XX decisions remain Proposed. Twenty engine candidates and D-025 human scroll checks remain unconfirmed. No baseline/OCR, detector, metrics, matching, golden, translation, label or reference change; no hold-out/secrets, provider/model calls or spend, push/PR/merge or issue closure. #47/#44 remain incomplete; #44 closes only on #47 merge.

The last verified device state after plan 4 is exact 1271048 stopped, adbd shell, original settings/saves/45 outputs unchanged, emulator released. No later device command has been executed by this task. **Provider requests 0; spend USD 0.**

## Changed checker files

Only `docs/engine-text-reference.md` and the files listed in this directory's `evidence-receipt.json` are added/updated. Full diagnostic fork code/patch, APK and parent orchestration sources remain in separate task output artifacts; no Unciv implementation code is placed in the checker repository.
