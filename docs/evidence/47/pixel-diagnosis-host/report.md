# Issue 47 — Tech Picker pixel diagnosis handoff

2026-10-22. Fork-only, host-only follow-up to device attempt 2.

**No reliable local cause has been demonstrated. No production fix, new commit,
version allocation or replacement APK was made. Strict pixel acceptance remains
failed.** The next useful step is the parent's bounded same-APK v1/v2 device
experiment, subject to a new exact-operation plan and Anton's separate approval.

## Unchanged implementation and scope

- Checkout: `/Users/antonborodin/Documents/Codex/2026-10-21/task-issue-47-https-github-com/work/Unciv`
- Branch: `feat/47-engine-text-dump`
- HEAD: `b534a8ae67c390412984869c7a03b168d532c36c`
- VersionCode: **1271048**; retained APK SHA-256:
  `91d9a900f8204880e590de7fb90f0fc15e2aa5cf5d94a3ae77364497d7b0541e`.
- All new fork diagnostics are ignored files under
  `Unciv/build/issue47-pixel-evidence/`. The tracked fork worktree is clean.
- No device command, install, app launch, settings/save write, provider request,
  checker edit, push, PR or outgoing chat message was performed in this follow-up.
- No reference, screenshot, metric, threshold, translation, fixture, baseline/OCR,
  detector, accepted decision or hold-out data was changed or accessed beyond the
  explicitly supplied screen evidence. No dotenv or credentials were read.

The parent report `device-execution-2/report.md` reports successful 1271048
installation, recovery/lifecycle checks, final settings/save preservation and an
available emulator. Those device operations were not repeated here. Emulator
availability is not authorization for another device phase.

## Independent pixel verification

Inputs were the supplied `device-execution-2/tech-picker-pixel-deltas.json`, PNG
evidence, current captures under `checker/data/issue-47/capture-approved-2` and the
approved effective #41 PNG set under
`checker/data/issue-47/reference-1271045-effective`. No checker implementation or
baseline/OCR implementation was read.

`PixelCompare.java` independently decoded the PNGs with Java ImageIO, required an
sRGB color model and compared complete integer RGBA values. It did not rescale,
round, modify images or allow a tolerance. All 64 comparisons completed:

| Comparison | Result |
|---|---|
| 40 current captures against their supplied #41 counterparts | 36 exact; four differing Tech Picker files |
| 20 forward/reverse current PNG pairs | All exact |
| Two recovery-primer PNGs against the German reference | Both have the same 72-pixel delta |
| Those two recovery-primer PNGs against the current German capture | Both exact |

| Language | Changed pixels per pass | Exclusive bounds | Maximum absolute channel delta |
|---|---:|---|---:|
| EN | 40 | `[751,469,768,484]` | 1 |
| DE | 72 | `[214,239,237,258]` | 2 |

All differing pixels retain their alpha channel. EN has 21 RGB `(-1,-1,-1)` and
19 RGB `(+1,+1,+1)` deltas. DE has predominantly single-unit changes and one
RGB `(-1,-1,-2)` change. The original/reference and current Tech Picker PNGs have
the same dimensions, RGBA8 format, sRGB chunk and sBIT values; no differing
gamma/ICC metadata explains the result. This excludes a file-encoding-only
difference and a changed alpha channel for these images. It does not establish a
GPU, geometry or font-rasterization cause.

Current v2 dumps place the EN delta over `h`/`e` in **The Wheel**, and the DE
delta over `n`/`g` in **Tierhaltung**. Both labels report full visibility,
effective alpha 1, font scale `0.14000000059604645` and physical scale about
0.252. These are current geometry observations. There is no equivalent historical
v2 geometry/UV/atlas trace, so old/new geometry equality is not established.

Current dump SHA-256:

- EN: `0a787dcc3815170eef91fa8621e80e9853c093b7b2957df2b3dea45e069e4cd8`
- DE: `1d6e5c2e7b62e3007445ea846d1afe3ba726530b4d0a5ae3ef86e73c6cd59fdb`

The compared primer files are **primer-2-0.png and primer-2-1.png**, both v2
recovery Tech Picker screenshots. The short diagnostic labels `primer-0` and
`primer-1` in `pixel-comparisons.jsonl` refer to those two files, not protocol v1.
The actual v1 primer has READY/event evidence but no retained screenshot. Existing
evidence therefore cannot decide whether the same 1271048 delta occurs in v1.
The recovery/fresh-batch equality only excludes that particular history change
as the differentiator in these German samples.

## Source and cache investigation

The source audit compares the fork's known source base
`877b0dc2ee706dbbdb4a17e14b4522408d197390` with current HEAD. Byte-for-byte
unchanged files are:

- `MipmappedFontTexture.kt`: incremental upload and deferred mipmap machinery.
- `FontLodBiasBatch.kt` and `TextureArraySpriteBatch.java`: batch/shader/filter path.
- `AndroidFont.kt`: Android glyph rasterization implementation.
- `TechButton.kt` and `TechPickerScreen.kt`: label construction and screen layout.

The substantive font changes are the L10nBitmapFont/cache subclass and the
NativeBitmapFontData getGlyphs trace wrapper. Inspection found no explicit change
to glyph creation, packing parameters, filtering or cache positioning. Cached
libGDX 1.14.2 bytecode confirms that the new one-argument BitmapFontCache
constructor obtains the same `usesIntegerPositions` field used by the original
newFontCache constructor; a changed integer-position default is not supported.
The observer copies the batch matrix before multiplying/projecting; its GL calls
query state rather than set it.

The lifecycle change from ordinary rendering while loading to suppressing those
draws is real and shared by v1/v2. A changed glyph/atlas warmup chronology remains
a hypothesis, not a reproduced cause. Reverting lifecycle fixes, prewarming
arbitrary glyphs, rounding coordinates or changing texture/filter/shader settings
would be speculative and was not done.

## New bounded host A/B diagnostic

`CacheAB.java` uses the existing cached test runtime, actual libGDX Labels,
GlyphLayout, BitmapFontCache and current NativeBitmapFontData. It compares:

- Plain libGDX BitmapFont/cache with trace disabled.
- L10nBitmapFont/cache with trace and draw observation enabled.

Thirty actual Tech Button heading strings from the supplied EN/DE dumps were
replayed at font scale 0.14, label width 140 and ellipsis enabled. Each run drew
twice. Both a no-extra-warmup recipe and an alphabet/digit/punctuation-warmup
recipe ran in plain/observed/observed/plain order: **eight successful runs,
exit 0**.

Within each recipe, all four runs matched exactly for:

- Raw float bits of submitted position/UV/color arrays and texture handles.
- GL mutation/upload call hashes, including immediate copies of pixel buffers.
- Glyph creation order.
- Texture-binding invalidation counts: 101 without extra warmup, 128 with warmup.

Observed runs added 184 GL state queries each; plain runs added none. Both recipes
reached one atlas page and 60 draw submissions per run. Warmup changed the atlas/
UV and upload hashes between recipes in both arms, demonstrating sensitivity to
input history, not a causal link to the device delta.

**Limits:** GL and the Batch submission sink are mocked; glyph Pixmaps are
deterministic synthetic inputs. The plain arm uses current NativeBitmapFontData
with tracing disabled, not the historical APK. Multipage atlases, actual batch
shader execution, Android Skia, GPU interpolation/final framebuffer pixels and
loading-screen scheduling are not exercised. The result narrows a deterministic
CPU/cache mutation hypothesis in this fixture; it does not prove device pixel
equivalence or exclude a v2 query/timing effect on an actual GPU.

One diagnostic import compile error and two harness initialization failures
(Mockito self-attachment, then missing initial Gdx.graphics) preceded the passing
run. The harness now starts with the already-cached Byte Buddy Java-agent and
initializes the required mocked globals; no dependency was downloaded or changed.
Those setup failures are not production test failures. Earlier full build/test/
lint evidence for b534a8a remains retained; it was not rerun because production
source did not change. The new A/B diagnostic is separate evidence.

## Smallest useful next experiment — proposal only

Use the **same installed 1271048 APK**, German/original settings and the same
approved Tech Picker state, with no install and no regular settings write:

1. Cold v1 Tech Picker, then warm v2 Tech Picker.
2. Cold v2 Tech Picker, then warm v1 Tech Picker.

The parent should bind four fresh tokens, four exact screenshot paths and two
declared v2 dump paths in a new exact-operation plan. Retain events and exact
image bytes for all four requests, including v1. Compare all four with each other
and with the current 1271048 German PNG and approved #41 German PNG using the
unchanged zero-pixel criterion. Device preparation, preservation checks and the
final stopped/free state belong in that plan. This handoff authorizes none of
those operations.

Interpretation should stay bounded:

- A stable protocol-dependent difference in both orders would focus investigation
  on the v2-specific path, without identifying a particular observer operation.
- All four matching the current delta would shift focus toward the shared 1271048
  lifecycle/font path or rendering environment; it would not prove a cause.
- Order/cold-vs-warm dependence would establish a history-sensitive effect worth
  tracing. Each hook request already resets fonts, so this is not a promise of a
  persistent atlas between requests.
- If the original pixels reappear or results vary, preserve every result and
  investigate the changed conditions before choosing a source fix.

No new APK is justified by the current host findings. If that experiment cannot
distinguish the paths, a later separately approved diagnostic build would need
actual affected-glyph atlas positions/UVs, pixel/upload hashes and batch inputs;
those measurements cannot be recovered from the existing v2 JSON alone.

## Retained evidence and preservation

All paths below are relative to the fork's ignored
`build/issue47-pixel-evidence/` directory:

- `PixelCompare.java`, `comparisons.tsv`, `pixel-comparisons.jsonl`: independent
  strict image comparison, exact input paths, RGBA hashes and channel histograms.
- `png-metadata.json`, `affected-glyphs.json`: PNG chunks and current dump mapping.
- `source-audit.json`, `*-from-base.diff`, `libgdx-font-cache-bytecode.txt`: source
  hashes, changed font/hook code and constructor bytecode.
- `CacheAB.java`, `replay-inputs.json`, `runtime-classpath.txt`, `cache-ab.log`,
  `cache-ab-result.json`: passing A/B harness, inputs, cached runtime and limits.
- `cache-ab-attempt-1.log`, `cache-ab-attempt-2.log`: retained harness setup failures.
- `artifact-preservation.json`: seven retained 1271047/1271048 APK/sample/provenance
  artifacts still match their earlier recorded hashes.
- `diagnosis.json`, `evidence-sha256.json`: final machine-readable conclusion and
  diagnostic evidence hashes.

The failed strict comparison remains failed. Human confirmations, D-025 scroll
checks and final issue acceptance remain with the parent/user workflow.
