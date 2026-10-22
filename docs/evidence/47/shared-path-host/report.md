# Issue 47 — shared loading/render path diagnosis

2026-10-22. Fork-only, host-only follow-up after device plan 3.

**The shared loading gate can change atlas history in a bounded host fixture,
but the actual Android 72-pixel regression has not been reproduced or assigned
to that gate. No production correction or replacement APK is justified yet.**
Recommend the saved original 1271045 binary control before building telemetry.
Both possible device steps below are proposals requiring a new exact-operation
plan and Anton's separate approval; neither was executed here.

## Current provenance and scope

- Fork: `/Users/antonborodin/Documents/Codex/2026-10-21/task-issue-47-https-github-com/work/Unciv`
- Branch: `feat/47-engine-text-dump`
- HEAD remains `b534a8ae67c390412984869c7a03b168d532c36c`, versionCode **1271048**.
- Retained 1271048 APK SHA-256:
  `91d9a900f8204880e590de7fb90f0fc15e2aa5cf5d94a3ae77364497d7b0541e`.
- Tracked fork source unchanged. No new commit, APK or version allocation.
- New diagnostics: ignored `Unciv/build/issue47-shared-path-evidence/`.
- This follow-up performed **zero device commands, provider/API requests or spend**.
  No checker edit, baseline/OCR implementation read, hold-out/env/credential
  access, screenshot/reference/fixture/metric change, push, PR or outgoing message.
- All prior reports/APKs remain intact. The prior pixel-handoff/evidence manifest
  and seven retained APK/sample/provenance hashes were checked again: **27 hashes
  match**. See `prior-evidence-preservation.json` in the new diagnostic directory.

The parent's plan-3 evidence is at `work/device-execution-3/`. I inspected the
supplied analysis and recorded hashes of analysis/result/command/preservation
JSONs in `phase-3-inputs.json`. Device execution and preservation remain parent
evidence, not operations repeated by this host session.

## What plan 3 establishes

In the supplied German sample, cold v1, warm v2 after v1, cold v2 and warm v1
after v2 all have decoded RGBA SHA-256:

`8b2d74c23959e568fddfbf9e7c8f15a8da5aa603dfc8e4fa6d7877b74d7efc37`

All eight PNGs are stable, match retained 1271048 exactly, and retain the same
72 differing pixels against effective #41/1271045, exclusive bounds
`[214,239,237,258]`. Both v2 dumps match each other and the retained dump:
`1d6e5c2e7b62e3007445ea846d1afe3ba726530b4d0a5ae3ef86e73c6cd59fdb`.

This excludes a protocol-dependent or tested cold/warm-order difference in that
sample. It does not isolate a particular shared source change or exclude a
rendering-environment/reference-history difference. The new font/cache classes
are shared by v1 and v2. The original zero-pixel requirement remains failed.

## Shared-path audit against 877b0dc

Source base: `877b0dc2ee706dbbdb4a17e14b4522408d197390`.

1. **The pending-work target-draw suppression is unchanged.** The complete
   `if (hasPendingWork(screen))` block in L10nScreenHook.render is byte-for-byte
   identical to the base. Do not attribute this existing barrier to #47.
2. **The loading return changed:** base `if (loading) return false` allowed
   UncivGame's ordinary renderer to run; current `return true` suppresses it.
   Ordinary BaseScreen rendering already uses `stage.act(0f)` in hook mode.
3. LoadingScreen still explicitly renders its previous screen when taking its
   background screenshot. The hook still explicitly sets `world.shouldUpdate`
   and calls `world.render(0f)` before building Tech Picker. These paths were not
   removed. Consequently, extra ordinary loading frames need not introduce any
   new glyphs; their actual timing/content must be observed.
4. **The loading window changed too.** Base published target and set loading=false
   inside the same GL completion callback. Current code publishes target in the
   build callback, then clears loading in a later withGLContext in finally.
   A callback/frame opportunity can exist between them. Merely restoring the old
   return value would allow ordinary target rendering during that interval,
   before the hook applies its pending-work/layout barrier.
5. Source hashes from the previous audit still show unchanged AndroidFont,
   MipmappedFontTexture, FontLodBiasBatch, TextureArraySpriteBatch, TechButton and
   TechPickerScreen. The other shared changes include the new cache/data trace
   wrappers, guarded font retirement and request ownership/callback scheduling.
   The previous plain/cache A/B narrowed deterministic mutation in its fixture;
   it did not eliminate all shared-path effects.

Evidence: `shared-source-audit.json`, `shared-path-from-base.diff`, and the prior
`build/issue47-pixel-evidence/source-audit.json`.

## Bounded host mechanism probe

`LoadingWindowReplay.java` ran actual current L10nScreenHook.render and
UncivGame.render, real libGDX Stage/Label layout and current NativeBitmapFontData.
Byte Buddy changed only the hook's return value **in JVM memory**, then restored
the original class bytes before exit. Fork source/class/JAR/APK files were not
rewritten. The alternate return permits an ordinary loading draw only when:

- The hook is active, the request still owns the work, and leave is not pending.
- Loading is in progress and **target is still null**.

The ordinary screen was a mock BaseScreen dispatching to the real fixture Stage.
It held a deferred-layout `Tierhaltung` Label. Final draws replayed 15 German
Tech Button headings from the supplied dump. Glyph Pixmaps were deterministic
synthetic inputs; GL and the Batch submission sink were mocked. This is a
mechanism fixture, not a reconstruction of WorldScreen's actual transient UI.

Eight ABBA runs completed with exit 0: current/guarded-legacy/guarded-legacy/current
for deferred layout and an already-validated layout control. Each arm received
three loading render callbacks, then two final draws.

| Observation | Deferred layout | Already-validated control |
|---|---|---|
| Current / guarded-legacy ordinary loading draws | 0 / 3 | 0 / 3 |
| Final position/color float bits | Identical | Identical |
| Final UV float bits | Different | Identical |
| Final CPU atlas bytes | Different | Identical |
| Mipmap generation calls, current / guarded-legacy | 12 / 12 | 11 / 12 |

With deferred layout, current created only the space glyph during loading;
the alternate arm also created the letters in Tierhaltung. Later final glyph
packing and UVs changed. With prior validation, glyph order, atlas bytes and UVs
matched despite an extra mipmap generation call. That last result also shows why
matching CPU pages alone cannot establish identical GPU mipmap history.

Six isolated checks of the alternate gate allowed one ordinary draw for a current
owner and zero for superseded, leave, terminal-ready, terminal-error and
target-published-before-finally states. They verify that particular dispatch
policy, not the full asynchronous lifecycle or device acceptance.

**Limits:** no historical APK execution, actual WorldScreen/LoadingScreen
construction, real background UI completion order, Android glyph rasterization,
GPU mipmap pixels, shader output or final screenshot. One atlas page was reached.
No link to the actual 72 changed pixels is proved. The early Label was a diagnostic
input; no arbitrary prewarming was added to production. Prevalidation is a negative
control, not a proposed fix. One initial harness setup error used the unsupported
setScreen API; the successful harness injects the mock screen into the base Game
field. Logs of the initial and intermediate variants are retained separately.

## Can an old-style render path preserve the four #44 fixes?

It is compatible with their design in principle, if it remains request-scoped;
it is not established as a correct production change by the mechanism probe.

| Requirement | Necessary boundary if this path is later tested |
|---|---|
| READY/ERROR freeze | Keep terminal handling and continuous-rendering shutdown; no fallback draw for a terminal owner, including one still draining work |
| Uninitialized Current font guard | Retain guarded font retirement; do not move font access before initialization |
| Actual construction failure | Retain exactly-once pending release and forwarding of the actual cause on GL; exercise failures alongside ordinary setup rendering |
| Queued/loading supersession and ordinary leave | Retain ownership checks on every delayed resource/load/UI callback, drain the old load, block its ordinary draws once retired, and wake the next request/leave |

The additional target-null boundary avoids bypassing the already-existing
pending-work target barrier in the new finally interval. It does not prove that
all ordinary WorldScreen update/callback side effects are harmless. An actual
candidate would need integrated render/failure/supersession tests, the full host
test/build/lint tasks, and a newly approved device comparison. A one-line loading
return revert is therefore not being shipped. The earlier b534a8a full host results
remain retained; no full rebuild was repeated with unchanged production source.

## Recommended next control: original installed 1271045 APK

The parent's proposed original-binary control is worth doing **before a telemetry
APK**, if Anton approves the two package updates. It tests the exact saved binary
in the current environment, avoids rebuilding the old source, and can stop an
unnecessary renderer investigation. Its cost is a data-preserving debug downgrade
and restoration update, which require explicit exact-operation approval.

Host verification completed without a device connection:

- Original APK: `work/device-phase-1/installed-original.apk`, 32,504,496 bytes.
- SHA-256: `16b6e07eaa8f7ca35b71f361f0bdcceb7015987b60e796d15d2f3b53bb61af1a`.
- aapt2: package `com.unciv.app`, versionCode **1271045**, versionName 4.22.10,
  debuggable.
- apksigner: exit 0, v1/v2 verification true. Certificate SHA-256
  `b4752f8cee80842f55883ca2a9b62ca75c898df5a1b7cefd63959ba1b8fecb99`,
  matching retained 1271048.

These facts establish the local file identity/signing metadata; they are not
an installation result or independent proof of its source commit.

Smallest useful proposed device scope:

1. Preserve/verify the approved original settings and four saves using the parent's
   established procedure; keep the German settings and exact Tech Picker state.
2. Update to that exact saved original APK using the approved data-preserving
   debug downgrade operation; no uninstall or data clear.
3. One cold **v1** German Tech Picker request, with a fresh token and two explicitly
   declared terminal screenshots. Record READY/events and repeat stability; old
   READY behavior must be observed rather than assumed to implement the new freeze.
4. Restore the exact pinned 1271048 APK in one update. One cold v1 request with
   another fresh token and two declared terminal screenshots verifies the restored
   current rendering result. No new v2 dump is needed for this binary control.
5. Independently verify original data preservation, installed identity, stopped app
   and free emulator. Compare the four PNGs using the unchanged zero-pixel rule.

This is **two package updates, two fresh requests and four PNGs**, not an approved
command plan. Parent must bind the hashes, exact operations/paths and any separately
declared conditional recovery before asking Anton to approve it. No ordinary
settings/save write is proposed. Do not assume a downgrade is accepted merely
because package/certificate metadata matches.

| Result of the control | Bounded implication |
|---|---|
| Original APK restores #41 pixels; restored 1271048 restores the 72-pixel delta | A binary-dependent difference is reproduced in the same tested environment. Continue shared-path telemetry; the loading gate is not yet singled out |
| Original APK also has the same 72-pixel delta | A code-change-only explanation is insufficient; investigate environment/reference-history/request conditions before changing the renderer |
| Original differs from both, varies, or restored 1271048 no longer reproduces its prior pixels | Preserve all results and identify the changed conditions. The experiment does not establish a corrective patch |

No result grants a tolerance waiver or turns a candidate PNG into a reference.

## Conditional diagnostic build plan

If the original-binary control reproduces a binary-dependent difference, the next
small diagnostic build should start at pinned b534a8a with one fresh, coordinated
versionCode. **Do not reserve/relabel 1271048, rebuild the old APK, or implement
this plan as part of this handoff.**

Use one Android debug APK with default behavior/telemetry off unchanged. Explicit,
strictly validated debug diagnostics would support current loading behavior and
the guarded alternate loading gate above. Keep every #44 guard and the original
pending-work barrier. Scope activation to the approved German Tech Picker state;
release builds ignore it. No fixed glyph warmup, timer/threshold relaxation,
coordinate rounding or reference change.

Three cold v1 requests on that same diagnostic APK would be sufficient initially:
current/telemetry-off control, current/telemetry-on, guarded-loading/telemetry-on.
Declare three tokens, six terminal PNGs, two telemetry JSON sidecars and up to two
named CPU-atlas PNG slots per instrumented request (only the pages actually holding
the affected n/g glyphs). No v2 observation/dump is needed. If telemetry-on changes
the current control image, stop causal interpretation and revise the probe.

Exact telemetry needed, captured from existing work without forcing layout,
requesting an absent glyph, drawing extra diagnostic content or reading GPU pixels:

| Data | Collection point and fields |
|---|---|
| Provenance | APK/source/diagnostic mode, token, protocol, request-state hash, language, font family identifier/size/metrics, image/viewport size; no settings contents or device-private backups |
| Frame and owner chronology | Monotonic event/frame sequence; loading/target/retired/terminal flags; screen class and owner; resource/font resets, LoadingScreen snapshot, world construction/show, ordinary loading draws, explicit pre-build world draw, target publication, finally release, pending barrier, target draws and READY |
| Glyph creation order | On each actual cache miss: font-generation id, codepoint/string, caller phase, glyph raster dimensions and raw RGBA hash, packed page/x/y, xadvance/offsets and raw float bits of UV; never call getGlyph just to inspect it |
| CPU atlas | Page dimensions/ids/hashes after explicit world draw, before first target draw and before READY. Retain the final CPU page(s) containing Tierhaltung n/g in the two bounded atlas slots per instrumented request; no new rendering/readback |
| Upload/mipmap history | Existing full/subupload and mipmap operations only: event/frame, font generation/page/texture handle, target/mip level/rectangle, buffer hash before disposal; every full upload, dirty transition and actual regeneration ordered in the same sequence |
| Affected final cache inputs | Actual Tierhaltung Label/cache identity, glyph-to-page mapping, raw position/color/UV bits, projection/transform copies, font scales and actor bounds at submission. Bind identity by the technology key without mutating actor names/text. No validation or extra cache generation |
| Actual batch submission | On flushes containing those vertices: vertex/index hashes, texture slots/handles, relevant LOD-bias values, shader identity, framebuffer/viewport/scissor state and flush reason. Prefer already-maintained CPU state; label any state query and use the same collection in both instrumented arms |

Record all glyph creation and upload ordering for the relevant font generations,
not only n/g: earlier glyphs determine packing and adjacent mipmap sampling. Keep
telemetry bounded (for example 8,192 events, 128 frames, 16 atlas pages and 16 MiB
per JSON); overflow marks it incomplete and forbids an equivalence conclusion.
Atomic sidecar publication must not weaken exactly-once terminal handling.
These telemetry caps are diagnostic limits, not acceptance tolerances.

CPU page/upload equality and matching batch inputs still do not prove equal GPU
mipmap texels or shader output. This initial plan deliberately avoids adding FBO
readback/state-restoration machinery. If only GPU pixels differ after all captured
inputs match, a later GPU-specific plan is needed; do not infer the cause from
matching CPU hashes.

Before any use of that future build, host checks must cover diagnostics-off
equivalence, state/sidecar validation and bounds, no extra layout/glyph calls,
loading-target-finally dispatch, READY/ERROR, supersession/leave, font initialization
and background/GL construction failures. Then run full tests, debug build and lint,
retain a distinct APK, verify its signing/hash/version, and hand off those actual
results. A fresh exact-operation plan must precede any device install/request.

## Evidence index

New files below are under the fork's ignored
`build/issue47-shared-path-evidence/` directory:

- `LoadingWindowReplay.java`, `loading-window.log`, `loading-window-result.json`:
  final eight-run mechanism probe and six policy checks.
- `loading-window-attempt-1.log`, `loading-window-unguarded-mechanism.log`,
  `loading-window-ownership-only.log`: earlier harness stages, not the final policy.
- `shared-source-audit.json`, `shared-path-from-base.diff`: verified source facts.
- `original-apk-signing.txt`, `original-apk-badging.txt`, `original-apk.json`:
  host-only original binary identity/signing evidence.
- `phase-3-inputs.json`, `prior-evidence-preservation.json`: supplied input and
  prior-artifact provenance.
- `diagnosis.json`, `evidence-sha256.json`: final conclusion and evidence hashes.

Strict acceptance is still incomplete. No human confirmation, D-025 scroll
judgment, candidate approval, issue closure or publication is implied.
