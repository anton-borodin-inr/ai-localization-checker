# Stage 3 dev mutation planning

## Delivery boundary

Issue #59 is delivered in three PRs, as approved by Anton on 2026-11-02:

1. **This PR: recipes, planner and manifest, fully offline.**
2. Translation-only APK builder in the separate Unciv fork/session.
3. Device orchestration, calibration, qualification and verification.

`l10n-mutate plan` neither builds nor installs APKs, captures screens, calls a
provider/detector/baseline, nor writes labels. Its output is always
`stage: offline_plan`, `production_ready: false`. Static acceptance is not a
claim of non-interference. Dynamic checks and the split rate remain unrun/null.
There is no owner runner or excluded-screen bypass in this command.

## Fresh device runs under D-059 and Proposed D-060

Use a dedicated task directory under `~/Developer/sandbox/` and an approved
output root under `data/runs/`. The fork builder supplies a compact
`builds.json` with `source_commit`, `builder_commit`, `reference` and
`artifacts`. The reference and each artifact have a local APK filename
(`file`) and its `sha256`. Artifact keys are IDs from `build-requests.json`.
The checker validates the pinned reference, signer, version, exact translation
edits and unchanged nontranslation APK payloads before device access.

```sh
PYTHONPATH=src uv run l10n-mutate run \
  --plan "$PLAN" --manifest fixtures/stage2/screens-v2.json \
  --recipes fixtures/stage3/recipes-v1.json --catalog "$BUILDS" --sha256 "$BUILDS_SHA" \
  --task-dir "$TASK" --approved-output-root "$RUN_ROOT" --output-dir "$RUN" \
  --serial "$SERIAL" --sdk "$SDK" --jdk "$JDK" --calibration-only
```

Start with the empty control and EN-help singleton. On a calibration pass,
assemble the three planned batches and reuse the original two APKs. Run
without `--calibration-only` twice with separate output folders and compare
the manifests. Both runs reuse one task snapshot and restore the reference
APK and saved settings/saves before release. Use the D-057 emulator profile.

The live D-060 comparison permits outside-mask RGB deltas up to two with
unchanged alpha. It checks unmutated elements and exact same-build decoded
RGBA/raw-dump repeats independently. `run.json` records tolerated counts and
maximum deltas by calibration screen, language and pass. Stop on a gate or
operational failure. A production split handoff is a proposal for the owner
and fork builder to approve. No child builds are launched by the checker.

Keep `run.json` and the PNGs and manifest entries submitted for manual
acceptance. The other capture is used to verify repeatability. Delete
duplicate PNGs, APKs and scratch files at task end, and delete the snapshot
after final restoration. The earlier catalog and replay sections below
describe historical tooling.

## Inputs and command

Install the existing locked dependencies with `uv sync --locked`. No dependency
was added. On the affected Mac, CLI commands still need `PYTHONPATH=src` because
of the existing hidden editable `.pth` problem (D-019); the planner does not
attempt to repair the environment.

```sh
PYTHONPATH=src uv run l10n-mutate plan \
  --manifest fixtures/stage2/screens-v2.json \
  --recipes fixtures/stage3/recipes-v1.json \
  --inventory /path/to/dev-inventory/inventory.json \
  --split dev --seed 59 --output-dir data/stage3/offline-plan
```

A repeatable `--screen-id` may replace `--split dev`. Selection is required;
unknown, duplicate, mixed or excluded IDs fail before recipe/inventory payload
reads and output creation. Recipe targets must belong to the selected dev
screens. The split registry beside the original manifest is authoritative;
membership is not duplicated in the generator. Original manifest and split
hashes bind the output.

The **static inventory must cover every dev screen in EN and DE**, even for a
smaller target selection, so shared-key impacts are not checked against an
arbitrary subset. Inventory format 1:

```json
{
  "schema_version": 1,
  "pairs": [
    {
      "screen": "tech-picker",
      "language": "en",
      "path": "tech-picker__en/capture.pair.json",
      "sha256": "<SHA-256 of the exact pair sidecar bytes>"
    }
  ]
}
```

The example shows one entry, not a complete inventory. Paths are relative to
the index and cannot escape its directory. Each pair binds original PNG,
decoded RGBA and dump hashes. Screen, language, canonical state hash, resolution,
versionCode and full APK/source provenance must match the manifest. Only dev
states and supplied dev pair payloads are read. Missing, duplicate or excluded
inventory records fail before reading pair payloads.

The committed issue-47 **dev-only** PNG/dump/pair members may supply static
inventory. They are neither production clean controls nor mutation evidence.
Tests construct their exact archive member names from `split.dev` and read only
those payloads, without extracting/scanning the other samples or reading review
references/labels.

Output must be a new directory, external or within this checkout's `data/`.
Existing directories, symbolic-link ancestors, other in-repository destinations
and roots containing the checkout are refused. No overwrite option is provided.

## Recipe catalog, freeze boundary and occurrence accounting

`fixtures/stage3/recipes-v1.json` pins fork `b534a8a`, the source behind the
1271048 static inventory. This unmerged PR has not frozen a builder catalog or
production recipe set, so the requested completion stays in `stage3-v1` rather
than introducing a second pre-release catalog. Freeze the accepted catalog's
exact bytes/commit before PR (b); a later change to that frozen input needs a
new catalog version, never silent reuse of the old identity.
A recipe specifies an immutable ID, language, intended
class/mechanism, literal source key, exact original RHS (empty is distinct from
absent), replacement or deletion, source evidence and clean target selectors.
Only the English/German translation asset paths can be emitted. Source keys are
never renamed. Unsupported escaped/multiline property edits are rejected rather
than normalized; a future recipe-format change must define their encoding.

The current catalog plans the following **intended occurrences**, not labels:

| Intended class | EN | DE |
|---|---|---|
| `overflow` | `?` -> `Help`; add `-` -> `Decrease`, `+` -> `Increase` | `?` -> `Hilfe`; add `-` -> `Verringern`, `+` -> `Erhöhen` |
| `truncated_text` | Mining, Masonry and Construction: three different TechButton titles | Mining, Masonry and Construction: three different TechButton titles |
| `wrong_language` | Foreign values for Mining, Worker (two widgets), population requirement, idle-unit checkbox, Tile yields and Civilopedia's New Game entry | Packaged deletion and explicit foreign value for Mining, population requirement, idle-unit checkbox, Tile yields and Civilopedia's New Game entry |
| `other` | Broken Research and population-requirement placeholders | Broken Research and population-requirement placeholders |

All **32 recipes bind 33 intended occurrences** (29 primary, 4 `other`) in the
existing static dev inventory. This is a pre-runtime count, not 33 observed
defects or independently labeled examples. A **distinct target** is the owning
actor path within one screen/language and intended class, counted once across
recipes. An **occurrence** is a bound logical mutation occurrence across planned
variants. The same widget can be a target for different classes; do not sum
class-specific target counts as unique physical widgets across all classes.

Distinct targets by class × language × screen:

| Screen | Language | overflow | wrong_language | truncated_text | other |
|---|---|---:|---:|---:|---:|
| options-gameplay | en | 3 | 1 | 0 | 0 |
| options-gameplay | de | 3 | 1 | 0 | 0 |
| tech-picker | en | 0 | 1 | 3 | 1 |
| tech-picker | de | 0 | 1 | 3 | 1 |
| city-production | en | 0 | 3 | 0 | 1 |
| city-production | de | 0 | 1 | 0 | 1 |
| empire-stats | en | 0 | 1 | 0 | 0 |
| empire-stats | de | 0 | 1 | 0 | 0 |
| civilopedia | en | 0 | 1 | 0 | 0 |
| civilopedia | de | 0 | 1 | 0 | 0 |

Intended occurrences by class × language × screen:

| Screen | Language | overflow | wrong_language | truncated_text | other | Total |
|---|---|---:|---:|---:|---:|---:|
| options-gameplay | en | 3 | 1 | 0 | 0 | 4 |
| options-gameplay | de | 3 | 2 | 0 | 0 | 5 |
| tech-picker | en | 0 | 1 | 3 | 1 | 5 |
| tech-picker | de | 0 | 2 | 3 | 1 | 6 |
| city-production | en | 0 | 3 | 0 | 1 | 4 |
| city-production | de | 0 | 2 | 0 | 1 | 3 |
| empire-stats | en | 0 | 1 | 0 | 0 | 1 |
| empire-stats | de | 0 | 2 | 0 | 0 | 2 |
| civilopedia | en | 0 | 1 | 0 | 0 | 1 |
| civilopedia | de | 0 | 2 | 0 | 0 | 2 |

Seed 59 produces 3 batches and 5 builder requests (including empty control and
standalone calibration), with 11 static-conflict pairs. N never exceeds 2;
single-occurrence shares are EN 7/11 and DE 8/13. These are planner counts,
not measured runtime split rates. Repeated Mining and Help exclamation variants
were removed: there are exactly three distinct truncation targets and three
distinct overflow targets per language, each with one recipe per target/class.
Reassess actual visibility, glyph-level duplicates and all counts in PR (c),
rather than treating these tables as human labels.

### Same-key/language equivalent-text guard

DE foreign-text values use authored **French** text, not the source-English
fallback. The capture languages remain EN/DE; no third capture language is added.

| Source key | DE foreign value (French) | DE deletion fallback (English) |
|---|---|---|
| `Mining` | `Minage` | `Mining` |
| `Tile yields` | `Gains du sol` | `Tile yields` |
| `New Game` | `Nouvelle partie` | `New Game` |
| `Check for idle units` | `Unités inactives` | `Check for idle units` |
| `Requires at least [amount] population` | `Requiert au moins [amount] habitants` | `Requires at least [amount] population` |

`RecipeSet` rejects two recipes with the same literal key/language and identical
effective translated input: packaged deletion resolves to the source key/template;
add/replace resolves to the literal replacement. This also catches matching
templates before identical argument substitution. The shared validator is used
before inventory reads in `create_plan` and again by `load_plan`, so recomputing
patch/batch hashes cannot admit a fallback/foreign alias. Exact semantic-edit
uniqueness remains a separate check. Different keys or languages are not merged.

This is a proof of equivalent translation inputs, **not a libGDX rasterizer**.
Different values may still shorten to identical visible glyphs or differ only
in markup/shaping; runtime qualification/review must detect those remaining
duplicates. An offline pass never proves unique pixels or independent quality
evidence. Original source values/tokens are not normalized or repaired.

Class balance is a target, **not a cap or production blocker**, following Anton's
2026-11-03 clarification. Do not discard valid wrong-language/truncation cases
to equal a scarce overflow count. Placeholder cases remain separate. The
manifest reports recipe counts and actual per-language intended-occurrence
balance, never detector quality. The policy explicitly records
`primary_class_balance: target_not_cap`; the four runtime/builder blockers
remain mandatory. Similar variants on one widget do not establish interface
breadth or independent quality evidence.

### Source-qualified overflow targets and accepted v1 coverage limitation

The main-menu help circle behind Gameplay Options is one fully visible logical
text occurrence in each dev language. At the pinned fork,
`MainMenuScreen.kt:216-227` creates a plain 48-unit translated label;
`IconCircleGroup.kt:23-29` resizes it to 45x45 scene units without enabling wrap
or ellipsis. The current owner is
`root/3:IconCircleGroup/1:IconCircleGroup/1:Label`.

Two additional distinct targets are the slider's decrease and increase labels.
`UncivSlider.kt:87-88,201-220` creates translated 18-unit `-`/`+` labels in
20-unit circles; `IconCircleGroup.kt:26` assigns each label 15x15 scene units
without wrap/ellipsis. Both keys are **absent**, not empty, in both pinned
translation assets, so these recipes use `add` with `original: null`. Each
has one full logical occurrence per language across the complete dev inventory.
The libGDX 1.14.2 plain-Label draw path does not clip to these own bounds.

**Anton accepted the narrower translation-only v1 coverage on 2026-11-03:**
three distinct actor targets (help, decrease, increase), all on
`options-gameplay`, with **no scoped injection**. Language/length variants do
not add targets. Other dev paths grow/wrap, ellipsize, have only scroll clipping,
are not visible, or—in the global hourglass case—exceed N. This is a documented
v1 limitation in D-050, no longer an unresolved two-screen scope decision.
The same independent qualification procedure may find no qualifying overflow
target on hold-out; in that case overflow recall there is **undefined**, not
zero or one. Report that limitation, without fabricating positives, changing
the injection mechanism or inspecting that cohort in this dev task. Metric
implementation and the zero-denominator rule are unchanged.

Qualify `Help` and `Hilfe` first, then other overflow singletons. Require actual
horizontal **own-label** overflow, N compliance, the pixel gate and unchanged
unmutated dump elements. Any failing overflow singleton means **stop**, not
substitution of the old global hourglass recipe. That recipe affects many
visible counters and is intentionally absent from this catalog. Worker long
text is also not an overflow recipe: issue 45 observed wrapping/panel growth.
No injected help-circle screenshot has been produced in this PR.

### Source limits of class coverage on the selected dev states

Wrong-language foreign injection is qualified in both languages on all five
screens; packaged missing-translation fallback is qualified in DE on all five.
Broken placeholders are qualified on Tech Picker and City Production. No
supported visible bracket-template target was found on the other three paths.

- **Empire Stats:** `StatsOverviewTab.kt:71-91,105-119,165-172` sizes tables
  from preferred widths, packs them and creates ordinary translated labels.
  It supplies the Tile yields wrong-language target, but no own-label
  truncation/overflow constraint. Tabs use natural-width IconTextButtons in a
  horizontally scrollable header, not an ellipsis path.
- **Civilopedia:** `CivilopediaScreen.kt:131-170,246-259,281-289` creates
  naturally sized, translated-name-sorted entry rows and scrolling category/
  entry panes. `FormattedLine.kt:314-329` wraps article labels at fixed width;
  `MarkupRenderer.kt:82-87` grows/packs the content. These are not finite
  own-label truncators. The selected heading is scroll-clipped, with its full
  title also visible in the entry list. Neither D-025 nor D-023 permits using
  that clipping as the requested truncation case. The New Game wrong-language
  recipe changes a different, fully visible entry; sorting still needs the
  dynamic unchanged-element gate.
- **City Production:** `CityConstructionsTable.kt:550-595` wraps list/rejection
  labels; `ConstructionInfoTable.kt:57,76-94` naturally sizes/wraps and packs the
  selected panel. That supports wrong-language and placeholder recipes, not
  own-label overflow/truncation. A fixed button or row-cell dimension alone
  does not establish a fixed label bound.
- **Gameplay Options:** the nine checkbox labels and tab labels naturally
  size; the tab header scrolls. Only the three circle-owned labels qualify
  for own-bounds overflow. No own-label truncator or visible source template
  was found in the selected tab.
- **Tech Picker:** `TechButton.kt:28-38,77-78` supplies fixed-width ellipsized
  titles and fixed-width plain counters. Mining, Masonry and Construction are
  three distinct, fully visible, unselected truncation targets per language;
  the global counter edit is rejected for its complete visible multiplicity.

These are source-qualified boundaries of the **frozen selected states**, not a
claim that every possible UI state of a screen has been exhaustively ruled out.

### Other boundaries

- EN can show `wrong_language` through explicit foreign values. Only the
  source-English missing-entry fallback is inapplicable as wrong-language in EN.
- A packaged DE deletion is genuine fallback. Replacing the same key with that
  English fallback would duplicate its visible input and is rejected, not
  counted as another case. French values keep the two mechanisms distinct.
  Omission from a mod would expose the packaged German value, not remove it.
- Research keeps source key `Research [technology]` and changes only the value's
  token to `[amount]`. It is not the Worker literal-token recipe.
- Mining, Masonry and Construction remain unselected, with Archery selected.
  Their fixed-width 140, font-14 ellipsis path is `TechButton.kt:28-33,77`, fed
  by `TechPickerScreen.kt:253`. The new literal assets are Masonry EN empty /
  DE `Mauerarbeiten` (`English.properties:8540`, `German.properties:5137`) and
  Construction EN empty / DE `Baukunst` (`English.properties:8565`,
  `German.properties:5150`). Each has one full clean title in the complete dev
  inventory and no full selected-detail copy. D-023's full-text-elsewhere
  exception and D-025's viewport exclusion still require actual runtime/human
  review. Source-qualified is not observed mutated truncation; dump flags do
  not create labels. D-047 is unchanged.

Selectors use the observed full input only for target binding; actual rendered
text stays separate. Known key metadata discovers additional occurrences;
undeclared dev-screen impact stops planning. Missing source keys, especially EN,
are not guessed: source-backed selectors are explicit and the later dynamic
check must cover all dev screens. Unknown owners, partially clipped targets and
missing selectors stop planning. Explicit decorative draws share their engine
logical occurrence and keep all draw IDs. Worker is two occurrences, not one.

## Static planning and deterministic split

Anton amended the original issue's layout criterion: fork layout metadata is
**not a prerequisite**. Current dump data supplies a conservative pre-filter:

- Different translation keys within a language.
- Different owning actor paths on each affected screen/language.
- Non-overlapping unions of clean owner/glyph rectangles, with an 8-physical-pixel
  gap. This is a conservative planner setting, not a pixel-difference tolerance.

No Table row/column or parent-container metadata is fabricated from paths.
Conflict reasons are recorded. Seeded SHA-256 ordering and stable greedy merging
keep at most **2 visible logical occurrences per screenshot**, and at least
**50% single-occurrence screenshots separately per language**. Controls,
unaffected screenshots and forward/reverse repeats are excluded from that
fraction. A global-key recipe exceeding N stops; it cannot be repaired by
splitting recipes. An inadequate singleton cohort also stops instead of adding
duplicate samples silently.

`split_after_interference` is a pure offline partition operation for the future
verifier: sort recipe IDs, bisect, retain parent/reason/child IDs, recompute
density. An interfering pair has a regression test. A failing singleton stops;
transport/readiness errors are not accepted as interference. This PR does not
produce or claim measured dynamic failures. Static-conflict counts are not the
dynamic split rate. The latter must be reported as split multi-mutation batches
over all dynamically tested multi-mutation batches in PR (c).

## Manifest and builder hand-off

Two canonical, deterministic files are written:

- `plan.json`, mutation manifest version 1: source/split hashes, seed and
  generator/recipe versions, path-independent inventory hashes, exact edits,
  clean target occurrences, observed input/rendered text/geometry/flags,
  per-screenshot mutation mapping, static conflicts, density, balance, required
  calibration and production blockers. `load_plan(raw, manifest=original_manifest)`
  requires the original source manifest and its adjacent split registry as the
  authority, verifies their exact byte hashes and complete dev/language inventory
  coverage, and checks edit/batch/hash consistency and pending gates. It reads
  only manifest/split metadata, not fixtures or pair payloads; it is not
  authorization.
- `build-requests.json`, requests version 1: the plan SHA-256, pinned source,
  unique patch sets, their full SHA-256 and deterministic IDs/roles. It includes
  an **empty patch set** plus any standalone calibration build not already a
  batch. No APK hash or versionCode is invented before the fork builder exists.

Request IDs, clocks, absolute output paths and operation journals do not enter
these deterministic content files. Reordering inventory records or recipe
enumeration does not change the plan. Unsuccessful/non-repeatable executions
must not be normalized into a successful manifest.

PR (b) must consume this frozen contract in its own fork worktree/session,
validate exact original values and translation-file-only changes, build every
variant independently from the pin (never accumulate patches), allocate and
freeze versionCodes/APK hashes and record toolchain/builder identity. Clean and
mutated builds must use the **same builder**; stock 1271048 is not a substitute
for the empty-patch control. Frozen catalog reuse, not fabricated reproducible
APK hashes, supplies repeated inputs.

## Required calibration and authoritative dynamic gate — PR (c)

Before production, capture the empty-patch builder APK and one **single-mutation
builder APK** across all dev screens/languages with the approved backup/restore.
The offline plan selects the basic EN help recipe for the current catalog; a
separate build is requested even when it was combined in the main plan.

Compare decoded RGBA using a versioned mask derived from all matched before/after
mutated extents, including overflow glyphs/decorations with fixed outward
rounding. Never mask a whole parent panel to hide layout reflow. Require:

1. **Zero changed RGBA pixels outside the mask, or the separately proven D-054
   glyph exception below for fresh normal runs.** Strict v1 measurements remain raw.
2. **No moved/changed unmutated dump element**, including inside masked areas.
3. Every intended mutation is visible and within the occurrence limit.

Incremental font-atlas allocation may change unrelated pixels (D-042). If the
calibration has outside-mask differences not proven under D-054, **stop before
production** and report counts, exclusive bounding boxes and maximum channel
deltas. No general tolerance or font-atlas workaround is authorized. D-042's
historical cross-build allowance is not itself the mutation gate.

PR (c) retains dev-only EN/DE forward/reverse capture and hash/readiness checks,
verified backup/restore and frozen-catalog installation. Its authorization is
conditional on the actual approved output folder/catalog; stop for another kind
of operation. This offline PR performs no device preparation or environment
checker invocation. The current checker's default remains 1271048; future
builder artifacts must use their actual pinned manifest, not a weakened check.

Only after successful calibration/qualification may dynamic interference split
production batches automatically. Preserve operational failures separately;
report the split rate. A high rate is evidence to discuss a separate fork
metadata task, not permission to introduce one here.

## Device runtime interface — part (c)

This section describes the part-(c) interface, not a claim that empirical
qualification has succeeded. A failed preservation/calibration run stays failed;
retain its manifest, backups and operational evidence. The first local device
attempt stopped on app-data changes after the empty control, before calibration.
The second full end-to-end run remains required after the first complete run
and every gate pass. D-051 below records the separately authorized four-file
preservation exception; no pixel tolerance is implied, and no historical failed
run is reclassified as successful.

### Explicit catalog and effective manifests

Select one catalog by its independently approved full digest and exact path,
never by a newest-directory search. The initial catalog SHA-256 is
`790b21921ca3d4988b6257a6da235817c8b8407b2f029871c74a05598efaf354`;
its builder-content SHA-256 is
`e9ec71c5bb0d8816bfa84c1eab911e6b7a0d3300d0bc54ae2b8357a058478086`.
The companion reader contract is the fork's `docs/l10n-apk-builder.md` at
`3935ffe41ab6876d210a4ad913825f358c44c14e`.

The reader checks canonical catalog/input bytes, every contained file reference,
the authoritative plan and exact request projection, builder/toolchain/signing
provenance, native APK signature/package/version/debuggable metadata, actual
APK translation bytes reconstructed from the original assets and approved
patches, and invariant payload evidence. It performs no build or install.

Capture `Inputs` selects dev before reading state/fixture payloads. Each artifact
gets an effective manifest with its verified `build` object; original fixture
authority and source-manifest hash remain separate. Never edit
`screens-v2.json`, the split, or the environment checker to match a generated APK.

### Preparation, downgrade proof and preservation

Before using the emulator, check `pgrep -fl l10n-capture` and
`adb shell pidof com.unciv.app`; an existing capture or app owner means stop.
Start the existing emulator only as documented in `environment.md` if needed.
Run the authorized `scripts/prepare_emulator.sh` after startup: the cutout
overlay is re-enabled by a boot. AVD recreation, wipes and other environment
changes are not fallbacks. The environment checker requires exactly one online
emulator; the runtime also serializes device ownership independently of output
root selection. The per-emulator lock is anchored in the checker's shared Git
common directory, so linked worktrees and different output roots share the
same authority; independent clones are not separate authorized device owners.

Before the first replacement, pull/verify the installed APK and compare its
certificate with the catalog reference. Keep verified private, device-encrypted
and external app-data backups with file inventories. Installation is only
`adb install -r -d`; no uninstall. Check app-data preservation immediately after
replacement under the exact D-051 policy below. A successful actual downgrade
back to 1271048 is mandatory before captures. A certificate match alone is not
this proof.

After **each** catalog-artifact installation, run
`scripts/check_env.sh --version-code <that artifact's actual code>`.
After restoring 1271048, run the default `scripts/check_env.sh`. Do not skip or
relax either check. Compare data again after capture and final restoration;
new exact planned hook outputs are distinct from pre-existing app data. An
unexpected delta stops the run and retains backups. No broader
database/profile/cache exception or app-data repair is authorized.

#### D-051: four private-root AndroidX files only

Anton explicitly authorized a narrow comparison-only exception on 2026-11-05,
recorded as Proposed D-051. The exact package-relative paths are:

- `files/profileInstalled` — ProfileInstaller marker;
- `no_backup/androidx.work.workdb` — WorkManager database;
- `no_backup/androidx.work.workdb-shm` — shared-memory sidecar;
- `no_backup/androidx.work.workdb-wal` — write-ahead log.

Only `DATA_ROOTS["private"]` qualifies (inventory keys start with `private:`).
The same names in external/device-encrypted roots, prefix/suffix matches,
descendants, and all other app-data paths stay strict. Only regular-file bytes,
SHA-256, absence/creation/deletion and UID/GID/mode may differ under Proposed
D-056's extension of D-051; all other fields stay strict. Directory/symlink
substitutions are unexpected. Settings and saves stay byte-exact. The code never
writes or restores these four files:
backups/readbacks retain observations, not permission to repair app data.

Every comparison records all four before/after inventory entries, including
size/hash for present regular files and explicit `null` for absence, even when
unchanged. Raw `inventory_changes`/install `data_changes`/capture `changes` and
`restoration_data_changes` are not filtered by D-051. Separate ledgers partition
actual exempt deltas from unexpected deltas; only an empty unexpected set may
qualify or proceed to another capture/catalog install. Reference restoration is
never gated by preservation. Declared-new hook outputs retain their existing
separate handling;
pre-existing hook files are never made mutable by that declaration.

Checks cover original backup readback, continuity into each install, per-install
backup readback and both before/readback-to-after comparisons, capture preflight
and before/after, and each reference verification. The readback-to-after check
keeps every non-exempt field strict, including files first created at readback.
Probe and final reference inventories/ledgers are retained separately as
`private/reference-NNN-inventory.json` and journal `restoration_checks`, rather
than overwriting the probe observation with the final one. Unexpected drift
between transactions stops before the next catalog install/capture, not the
authorized reference reinstall.

This exception addresses AndroidX startup bookkeeping, not game-state or
rendering variability. D-053 separately supersedes only D-050's outside-pixel
clause; RGBA masks, unmutated-element layout checks and forward/reverse
RGBA/raw-dump equality remain unchanged. D-054 supersedes only D-053's RGB cap.

Under Proposed D-056, the finalizer always attempts the pinned reference with
`adb install -r -d` after an entered device-stage stop/cancellation, including
early backup/current-identity/environment failures. Only the reference APK's own
unverified or mismatched hash/version/signer blocks the command. Observe all
preservation/readback/environment failures independently, still verify installed
certificate/hash/version after the command, and retain the first error plus
cleanup receipts. Ordinary catalog/mutation installs keep their strict guards.
`reference_validated`, `install_attempted` and `identity_verified` in a reference
install receipt are distinct from `app_data_preserved` and its overall status.
Run `restoration_verified` means the installed reference identity was verified,
not that preservation passed: unresolved non-exempt preservation still fails
the run and cannot qualify captures. No duplicate finalizer reinstall follows
an already attempted reference command; a failed pre-install observation is
not itself an install attempt. No app-data repair or generic retry is added.

### Operator command examples, not execution evidence

Substitute the approved exact catalog, SDK/JDK and output paths. Every output
directory must be fresh and below that session's approved root. The commands
below do not authorize a device operation by themselves.

```sh
PYTHONPATH=src uv run l10n-mutate probe \
  --catalog "$CATALOG_JSON" --sha256 "$APPROVED_CATALOG_SHA256" \
  --manifest fixtures/stage2/screens-v2.json \
  --recipes fixtures/stage3/recipes-v1.json \
  --sdk "$SDK" --jdk "$JDK" --serial emulator-5554 \
  --approved-output-root "$APPROVED_OUTPUT_ROOT" --output-dir "$FRESH_PROBE_DIR"

PYTHONPATH=src uv run l10n-mutate run \
  --catalog "$CATALOG_JSON" --sha256 "$APPROVED_CATALOG_SHA256" \
  --manifest fixtures/stage2/screens-v2.json \
  --recipes fixtures/stage3/recipes-v1.json \
  --sdk "$SDK" --jdk "$JDK" --serial emulator-5554 \
  --approved-output-root "$APPROVED_OUTPUT_ROOT" --output-dir "$FRESH_RUN_DIR"
```

`probe` performs the certificate/backup/replacement/downgrade/restoration proof,
not captures. `run` repeats the preflight and proof, captures the empty control,
then the EN-help singleton across all five dev screens, EN/DE and forward/reverse
passes. Only successful calibration under the narrow D-054 rule permits production batches.
Same-build pass repeatability remains mandatory in addition to cross-build
isolation. Timeouts and transport failures are operational failures, not observed
interference or clean results.

### Owner-authorized nonqualifying measurement mode (Proposed D-052)

The separate 2026-11-05 authorization collects the complete diagnostic matrix,
especially DE, before Anton decides whether to propose a different calibration
rule. It is **not** a new accepted rule, tolerance or production authorization.
Use the exact approved catalog path with SHA-256
`790b21921ca3d4988b6257a6da235817c8b8407b2f029871c74a05598efaf354`, empty control
`1888080431` and EN-help calibration `1808820362`, and a fresh directory below
the approved root. The configured entry point checks the catalog and both actual
versionCodes before constructing a device. Only the existing authorized control,
calibration and reference APKs are installed; no new build is permitted.

Invoke the existing Python interface explicitly; the ordinary `run` and `probe`
commands gain no measurement CLI flag. Fresh normal runs use D-054 separately;
measurement mode retains the original strict, nonqualifying behavior:

```python
from pathlib import Path
from l10n_checker.mutation_run import run_config
from l10n_checker.screen_manifest import json_bytes

config = json_bytes(Path("/approved/exact/measurement-config.json").read_bytes())
result = run_config(config, measurement_only=True)
assert result["measurement_complete"] is True
assert result["calibration_status"] == "failed"
assert result["capture_set_qualified"] is False
```

Alternatively, **only after separate device approval**, select precisely the new
device test with the existing approved configuration option:

```sh
uv run --offline pytest --run-device \
  tests/test_mutation_integration_device.py::test_real_dev_calibration_measurement \
  --mutation-device-config "$APPROVED_CONFIG_JSON" -q --tb=short
```

A passing measurement test means **diagnostic completion, not qualification**.
The existing `test_real_dev_mutation_generation` still requires a qualified run;
do not run it under the measurement-only authorization. This interface does not
combine with `probe_only` or resume. Only the probe, clean capture and calibration
capture execute; production callbacks are never constructed, and no dynamic
test, split or builder handoff is emitted.

Apply the same `verify_screen` measurements to all 20 clean/calibration pairs:
all five dev screens × EN/DE × two passes. Retain exact `passed: false` results,
RGBA counts, exclusive bounding boxes and maximum channel deltas, target masks,
occurrence qualification and changed-unmutated-element results. Do not stop at
the first outside-mask difference and do not manufacture a passing comparison.
Same-build RGBA/raw-dump repeat differences remain in each role's original
capture summary. `measurement_captures` links those summaries and reports their
actual repeatability outcome, including failures after all 20 role captures.

The capture wrapper still uses `fail_fast=True` for native, transport, readiness
and invalid-pair failures. Operational/cleanup errors, settings/save drift and
unexpected app-data changes remain fatal, even alongside comparison failures or
an otherwise complete 20-record summary. D-051 remains exact: four private-root
regular-file content/presence exceptions plus the same files' UID/GID/mode under
D-056, and no other delta. Every install/backup/input/readback/post/capture/
restoration check,
serial lock, containment boundary, `install -r -d`, per-artifact actual-version
environment check and default check after reference `1271048` remain unchanged.
Final restoration runs even after failure/cancellation and never retries an
already failed restoration transaction.

Throughout measurement checkpoints and final evidence,
`measurement_only: true`, `calibration_status: failed` and
`capture_set_qualified: false` are mandatory, including an all-zero matrix.
The final status is `failed` (or `restoration_failed`), never normal success.
`measurement_complete: true` means exactly 40 distinct authorized pairs, 20 per
role, with downgrade and final restoration verified and no operational error;
incomplete/error runs remain `false`. The normal manifest/journal and evidence
index v3 retain the flags. Complete diagnostic replay also checks the original
safety receipts and repeat observations without treating repeat differences as
qualification. Flag edits, recomputed outer hashes or deletion of mode markers
cannot supply missing production evidence or create a qualified run. Historical
failed evidence remains nonqualified and inspectable, never rewritten. Stop for
Anton's decision after reporting the full matrix; no labels/evaluation follow.

### D-058: visible text side effects

Fresh normal evidence uses run version **6**, index **7**. The manifest keeps
the strict cross-build comparison for inspection and records a separate
`qualified` result for intended occurrences. Each screenshot carries a
`side_effects` list with the actor and ordered visible text lines, visibility,
ellipsis and clipped fraction before and after any semantic change. Replay
recomputes these flags from the indexed screenshots and dumps. Anton reviews
the flags while labeling screenshots under D-012. D-050's remaining gates,
including exact within-build forward/reverse equality, still apply.

### Historical D-054: uncapped RGB with unchanged outside-mask glyph proofs

Anton authorized the rule on 2026-11-05 (Proposed D-053), superseding only
D-050's outside-mask clause. The pinned D-052 evidence and rationale are in the
decision entry. On 2026-11-06 Anton authorized Proposed D-054 to supersede only
D-053's numeric RGB cap, not any other gate or the existing usage pause.
Larger strings exposed RGB delta 47 across 3,228 glyph-confined pixels affecting
13 unchanged glyph IDs, unlike the four-glyph calibration's 406 pixels at <=2.
The rendering cause remains unestablished; glyph attribution is not causal proof.
The failed D-053 evidence root is
`0a2dc8504bd749cd6143183ee2a7ef5b1e9b6141fb5fb3005f285bdf64cb5994`, with
raw-results review SHA-256
`4072e586a17d72cf00ae74ca337ef6a1e3fe79a165b4b6523f5bfc608b656a10`.
Never reinterpret that failed run or historical measurement evidence as qualified.

The strict `verify_screen` result stays `mutation-dynamic-v1` and is never edited:
outside counts, exclusive boxes, channel maxima, mask, intended-occurrence and
unmutated-group results remain available even when its `passed` is false.
Each normal screenshot additionally carries `outside_rule` and a separate
`qualified` result. Controls carry an explicit non-use/control record. Every
comparison assessment binds the exact versioned policy, identity, mask, raw
outside measurements, sorted affected before/after draw IDs and actor paths,
signature/group hashes, and exact-coordinate/before-after-RGBA fingerprints.

All outside changes must fall within genuine **visible per-glyph bounds**, using
half-open physical pixel-centre membership and intersection with glyph visibility,
clip, viewport and screen. Hidden/undrawn/zero-alpha glyphs, owner-only bounds,
aggregate boxes and inferred parents do not qualify. All unmutated ordered groups
must remain exactly equal under the existing ID exclusions, including secondary
draws. RGB magnitude has no acceptance cap; alpha delta must still be 0. The
exact policy is `decision: D054`, `version: 2`, `max_rgb_delta: null`,
`max_alpha_delta: 0`, with unchanged pixel/repeat criteria. The 0..255 RGB
statistic range validates physical 8-bit measurements, not an acceptance
threshold of 47 or 255. No mask expansion, broad image tolerance or PNG
encoding rule change is introduced.

Pass 1 stays `pending`, `used: false`, `qualified: false`. Only an exact pass-2
comparison identity/mask, changed coordinate set **and original before/after RGBA
values** confirms both proofs. Pair bindings identify both controls and both
mutations. Equal counts/boxes/max deltas alone are insufficient. Missing reverse
measurements, invalid geometry, any local/repeat failure or changed unmutated
record cause a fatal STOP, not a split/handoff. Intended mutations and N <=2 still
must qualify independently. Existing same-build decoded-RGBA and full raw-dump
equality, operational, settings/save, installation/environment, shared-lock,
D-051 preservation, cleanup and restoration gates remain mandatory.

`outside_rule_usage` records expected/observed frames, needed/pending/confirmed
use, unique pairs and expected/observed rates globally and by batch, role,
language and pass. Clean controls never enter these denominators. Undefined
zero-denominator rates are `null`. A first partial 1/1 is not an engineering
pause: its expected batch scope is still normally 20 EN+DE frames. After each
complete calibration or production batch, **more than 10%** exception use in that
batch's expected combined EN+DE scope stops before the next batch and recommends
discussion of a separately approved fork-side alternative. The predeclared
threshold uses D-052's 2/20 baseline; exactly 10% is not a pause. This remains
the predeclared agent engineering recommendation, not a new owner-specified
threshold; D-054 supersedes only the RGB cap. Per-language
shares are reported independently, not used as a separate 50% cutoff. Future
batches and controls cannot dilute a broad current batch. No builder/fork change
is automatic. Invalid captures stop first, even in an incomplete batch.

D-054 evidence is run version **5**, index **6** (D-055 below), with exact D-054 policy and complete
usage required. Semantic replay authenticates the retained raw pair/PNG/dump
bytes at their reads, rederives strict metrics, assessments, IDs, fingerprints,
paired repeat bindings, qualification and usage, and rejects rehashed alterations,
deleted proofs/policy/counts and version downgrades. Producer hashes bind both
`mutation_outside_rule.py` and its executable `mutation_diagnostics.py` dependency.
Every producer digest must equal the exact current frozen source bytes; matching
manifest/journal claims alone do not establish authority. D-053 run v3/index 4
is rejected by the current producer, never silently upgraded. Replay it with
the exact archived `09acc674516196be2badfae247cc1ff76228fa17` producer without
rewriting or promoting its evidence. D-052 remains run v2/index v3 and strictly
nonqualifying; legacy strict failed evidence remains inspectable, without
promotion. Freeze and review the new producer before
fresh normal calibration/production, then perform the required second full run
under separate exact device authorization. Host synthetic tests are not device
qualification, labels or evaluation.

### D-055: bounded reads and verified exact hook-output cleanup

App-data backup/readback reads use exactly **300 seconds**, including package-root
inventories, inventory-only readbacks, SaveFiles, settings observations and final
reference reads. Other native defaults (30 s), environment checks (180 s) and
hook deadlines are unchanged. Each attempt durably retains a numbered JSON
receipt and private raw `.bin` bytes, even on native failure. Receipts record
root/path/purpose/command, observed bytes/hash, monotonic start/end/duration,
bytes/second, outcome/validation, limit and `over_60s`. A zero duration has
`null` throughput. Enumerate **every** `over_60s: true` read in the Report,
including failed reads. A failed, incomplete or malformed read stops; tar
member readability without terminal tar blocks is not completion. Binary
partial stdout stays in private evidence, not public error text.

Both standalone v2 capture and mutation capture establish a complete starting
inventory, rederive exact final/temporary paths and reject collisions before
the first write. The hook directory must already exist as a regular directory;
this task neither creates a new baseline directory nor authorizes removing it.
After settings restoration, cleanup force-stops the package and verifies its
stopped state. The operator must exclusively own the released device; the
mutation device lock remains in force. No concurrent root/ADB operator is
permitted within this quiescent boundary. Before the first unlink, authenticate
the whole present planned-new set against retained host bytes re-read from
disk, the complete before-cleanup inventory and safe device identity. A present
unpulled final/temp is pulled and retained exactly (raw diagnostic bytes may be
invalid as a TextDump); otherwise cleanup fails closed. Symlinks, hard links,
ancestor aliases, unsafe paths, changed identity/hash and unavailable guard
capabilities stop. A single guarded shell operation rechecks the stopped
writer, identities and content hash and unlinks one exact private-root path.
There is no glob, recursive removal, directory deletion or namespace sweep.

`hook-cleanup.json` and the capture summary bind a versioned `D055` policy,
starting/before/after inventories, exact path states, host byte/hash bindings,
identities and guarded commands. Missing planned files are `absent`, not
successful captures. Partial cleanup retains successful deletions and the
remaining attempted/verified/unavailable paths, attempts a fresh post inventory,
and remains fatal/nonretrying. Compare post-cleanup inventory to start with
**D-051 only**, without a hook-root exemption or accumulated allowed-output
union. Preparation, following installs and final restoration must maintain
that continuity. Native/callback/cancellation and cleanup failures remain
separate; no operational failure can cause a split or make failed pixels qualify.

Offline replay authenticates every new observation/raw byte at use, derives
coverage from completed workflow boundaries, reconstructs inventories, checks
numeric/duration/throughput/completion claims and rederives exact cleanup
authority/transitions/host bindings. Available failed/partial attempts are
validated too, without inventing later captures. `app_data.py` is included in
the exact current producer hashes; matching producer-controlled copies alone
are insufficient.

The current reader refuses **D-054 run v4/index5**, rather than reinterpreting it
as D-055. Preserve its index, manifest and payloads unchanged. Use the exact
archived `960dae205aafcc679e8a2b7e7cbfd569a14deb88` producer (the pre-D055
producer archive is retained under `host-verification-9/source-before-D055/`,
bound by `before-archive.json`) and its compatible host environment. For an
owner-provided complete archive/environment, the read-only recipe is:

```sh
# D054_ARCHIVE must be the authenticated exact 960dae2 producer, not current src.
PYTHONPATH="$D054_ARCHIVE/src" "$D054_PYTHON" -m l10n_checker.mutation_cli verify \
  --catalog "$CATALOG_JSON" --sha256 "$APPROVED_CATALOG_SHA256" \
  --manifest "$D054_ARCHIVE/fixtures/stage2/screens-v2.json" \
  --recipes "$D054_ARCHIVE/fixtures/stage3/recipes-v1.json" --sdk "$SDK" --jdk "$JDK" \
  --run-dir "$RUN_DIR" --evidence-sha256 "$PINNED_EVIDENCE_INDEX_SHA256"
```

Do not downgrade fields, combine old/current producer modules, rewrite evidence
or promote historical failures. D-053 v3/index4 still needs its separately
documented exact archive; older strict failures and permanently nonqualifying
measurement evidence retain their documented reader path. Host synthetic
checks do not prove Android command support or device qualification. Fresh host
checks and independent review/freeze precede the separately authorized scoped
audit, calibration/production and second full run. D-054/v2 and every nonpixel,
N/density, exact repeat, >10% completed-batch pause, catalog, fixture, install,
environment, reference-restoration, lock, split and approval gate is unchanged.

### Evidence and split handoff

`mutation-manifest.json` maps every screenshot to state, build/patch identity,
effective manifest, pair, PNG, decoded RGBA and dump hashes and records intended
occurrence qualification, unmutated-element checks, masks/differences, split
lineage/rate and nonqualified statuses. `observed_occurrence_matrix` excludes
controls and repeat passes and counts distinct owning targets separately.
No label files are produced. Intended class is not a human label.

Keep the runtime manifest, journal, installation/backup/environment receipts and
all screenshot payloads together. The final `evidence-index.json` needs its own
independently pinned digest; a mutable neighboring checksum is not authority.
Offline verification must authenticate that root, require complete evidence,
replay same-build repeatability and cross-build gates, and reject contradictory
status/qualification flags.

New normal evidence uses `mutation_run_version: 5` and evidence-index version `6`
(D-055 operational proof plus unchanged D-054/v2 pixels). D-054 v4/index5 and
D-053 v3/index4 require their exact archived producers as above.
Nonqualifying measurement keeps run version `2`/index `3`,
with the exact `preservation_policy` in the manifest, journal and install
receipts. Policy version 2 binds D-056's extension of D-051, the same four exact
private paths, allowed changes `bytes`, `sha256`, `presence`, `uid`, `gid`, `mode`,
and `app_data_writes: 0` for this exception. Existing run/index versions and
current-source producer hashes bind the new reference-restoration receipts;
old failed evidence remains immutable/nonqualified under its archived producer.
Every ledger's full observations and delta partition are recomputed from
authenticated retained inventories (tar inventories are also regenerated).
Missing/modified/widened policies or ledgers, incomplete observations, and
recomputed outer hashes do not bypass semantic verification. Dropping or
downgrading the policy/manifest/index cannot recover a success claim. Pre-policy
manifest version 1/index versions 1–2 remain inspectable for non-successful
runs only; historical successful pre-policy evidence is not requalified by this
verifier. Archived evidence is never rewritten. The following command remains
read-only with respect to the device:

```sh
PYTHONPATH=src uv run l10n-mutate verify \
  --catalog "$CATALOG_JSON" --sha256 "$APPROVED_CATALOG_SHA256" \
  --manifest fixtures/stage2/screens-v2.json \
  --recipes fixtures/stage3/recipes-v1.json --sdk "$SDK" --jdk "$JDK" \
  --run-dir "$RUN_DIR" --evidence-sha256 "$PINNED_EVIDENCE_INDEX_SHA256"
```

Real multi-recipe interference may produce an immutable
`builder-handoff/{plan.json,build-requests.json,handoff.json}`. It records the
parent catalog and exact plan/request/builder hashes and deterministic split
lineage. A failing singleton stops; splitting cannot repair an operational
failure. The denominator of the split rate is unique dynamically tested
multi-recipe nodes, not static conflicts or capture repeats; no tested nodes
means `null`, not a zero success claim.

**Pause before building.** Transfer the exact bundle to the separate part-(b)
Unciv-59b fork session. Only after owner approval may that session call the fork
builder with exact plan/request digests and explicitly pinned parent-catalog
reuse. The new catalog must bind that pending bundle and frozen builder;
its digest/path needs separate device authorization. Nothing here invokes the
builder automatically.

Resume uses a fresh run directory, the separately authorized new catalog, and
`--resume-from "$PARENT_RUN" --resume-sha256 "$PINNED_PARENT_MANIFEST_SHA256"`.
The pinned parent's embedded handoff is the authority for the sidecar and payloads;
paths cannot escape the approved root. Preserve prior dynamic tests and lineage
in the resumed split rate. A successful host replay or synthetic fake-device test
does not replace the required actual calibration or second end-to-end run.

## Target-qualification procedure for a later owner session

This procedure starts from source and that session's authorized clean inventory,
not from dev outcomes, detector findings, labels, class quotas or these examples.
It specifies how to author a cohort-specific recipe catalog after the generator
is frozen. It does not supply any later-cohort recipes, identify their targets,
authorize access/capture, implement an owner runner or bypass the public dev guard.
The owner must approve a separate session, its input/output boundary and any
necessary runner before this procedure is executed outside dev.

### 1. Freeze the input authority and create a candidate record

Record the fork commit, actual translation asset, intended language, selected
screen state, resolution and complete authorized screen/language inventory.
Use hash-bound pair sidecars and text dumps; never OCR/model output or human
labels to discover or count targets. Trace from a visible logical draw back to
its translated call site, literal source key, placeholder/fragment substitutions,
widget creation, sizing and final layout. Record source `path:line` locations
against that exact commit, not the current branch name.

For each candidate record: key, exact original RHS, replacement/deletion,
mechanism/intended class, translation/render/layout evidence, clean input-text
selectors, owner actor paths, full logical occurrence counts on every affected
screen/language, and qualification status. An empty English RHS is different
from an absent entry. Confirm the effective key/value is unambiguous in the
pinned assets. Reject unsupported escapes/multiline edits instead of repairing
tokens or silently changing the key. Keep source predictions, clean observations
and subsequent mutation observations separate.

### 2. Qualify the mechanism before selecting a value

| Mechanism / intended class | Required target and source evidence | Reject when |
|---|---|---|
| Lengthen / `overflow` | A translated, visible label/field with a finite assigned size. Trace both the constraints that retain that size and the actual draw path showing glyphs can extend beyond **its own** bounds, without wrapping/ellipsis/own-bound clipping. Choose a deterministic longer value in the intended language and identify which axis should overflow. | The label/container instead grows, wraps, shrinks to fit, clips/ellipsizes; only another widget is collided with; visibility depends on opening a different state; or more than two occurrences of the global edit affect any screenshot. Parent-cell size alone does not prove the label's own size. |
| Lengthen / `truncated_text` | A translated, finite label with an explicit ellipsis or non-scrollable own-field clipping path. Trace its width/height assignment and shortening/clipping code. Check every occurrence and whether the complete mutated string can appear anywhere else on the same screenshot. | Text merely wraps or a container grows; loss is only at a scroll viewport and scrolling reveals it (D-025); or an ellipsized value remains fully visible elsewhere on the same screenshot (D-023). Do not classify a growing panel's collision as truncation. |
| Remove / `wrong_language` | A populated non-English translation of user-facing text. Trace packaged-entry lookup and the source-English fallback, including later substitutions. Physically remove that language's packaged entry; record the unchanged source key and original RHS. | The intended language is English, the fallback is identical/shared/proper-name/symbol/numeric text, another active override still supplies the translation, or omission only uncovers an existing packaged translation. |
| Foreign text / `wrong_language` | A translated user-facing word/phrase with an unambiguous meaning. Replace its active value with unmistakable text from a different language, preserving required placeholders. Trace the active table and composition path. Prefer a short value so another geometry defect is not the intended mechanism. | The replacement is a legitimate shared word/proper name, only a raw key/symbol/number, does not reach the visible draw, or creates an undeclared additional mechanism/occurrence. English supports this mechanism despite being the source language. |
| Broken placeholder / `other` | A visible translated template whose actual source contains a bracket token used by the call site's substitution path. Keep the key unchanged and replace one value token with a different, unmatched token. Trace why the mismatched token survives into user-facing rendered text. | There is no source template token, the string bypasses that substitution path, the replacement token is consumed/hidden, or it is merely inserting technical text into an unrelated literal string. Do not relabel it as a primary class. |

No mechanism is required on every widget or screen. Record unavailable classes
with the concrete source limitation; do not add game code or silently substitute
a different mechanism to fill a table. Source qualification is a hypothesis for
later runtime qualification, not proof of visible mutation or a human label.

### 3. Count the complete impact, not recipe rows

For each language-specific global edit, inspect **all authorized screens** in
the complete inventory, including screens not initially selected for that
candidate. Enumerate every visible logical draw reached by the key or a
translated component, plus the source-backed selectors needed where provenance
is absent. Check composed sentences/templates and repeated list/table uses, not
only exact whole-string matches. Absence of key metadata, especially in English,
does not establish absence of impact; resolve it from source and clean inputs or
reject the candidate as unqualified. Never conceal a global edit's extra uses by
choosing a narrower text selector.

Count distinct logical occurrences once, grouping only explicit engine
decorative duplicates. Two widgets with the same displayed text are two
occurrences; a wrapped/composed logical unit is one. Preserve every draw ID.
Hidden text is not visible evidence. Reject partial, ambiguous, ownerless or
unbound targets rather than completing their hidden spans. Declare all affected
screens/selectors in the recipe and reject the whole recipe if a single screen
would contain more than two intended occurrences. Splitting batches cannot fix
an over-broad single global edit.

Count the resulting plan again from each mutation's bound occurrences, grouped
by intended class, language and screen. Sum the per-screenshot counts in the
mutated batches independently and require the same total. Controls, unaffected
screens and forward/reverse repeats add **zero** intended defect occurrences.
Length variants can add planned occurrences but not distinct interface targets.
Report both counts; never replace an occurrence total with the number of recipes.
For each class/language/screen, also group by the owning actor path across
recipes to report distinct targets. Different mutation mechanisms on one widget
can produce different occurrences but still represent one target. Reject
same-key/language equivalent translated inputs before planning; do not inflate
volume by counting provenance-only aliases of the source fallback.

### 4. Check the candidate catalog against planner validation

1. Parse the catalog with `mutation_recipes.load_recipes`. It must pass literal
   edit semantics, class/mechanism/operation checks, exact IDs/selectors and
   duplicate semantic-edit and equivalent translated-input rejection. This
   parser does **not** verify that the
   original RHS exists in the fork or that the selected class will manifest;
   source qualification and the builder/runtime checks supply those proofs.
2. For a dev catalog, run `l10n-mutate plan` with the authoritative manifest,
   full dev inventory, explicit `--split dev` and a recorded seed. A later
   owner runner must be separately approved; do not change IDs or the registry
   to make this dev-only command accept another cohort.
3. Require exact source/split provenance, complete inventory, every declared
   selector matched, no contradictory explicit key, no undeclared known-key
   impact, full visibility and provable actor/bounds. Missing provenance still
   needs the source analysis above; a successful selector is not proof of scope.
4. Inspect the manifest's **occurrences**, class/language/screen totals, static
   conflicts and density. Require N <= 2 and >=50% single-occurrence mutated
   screenshots separately by language. Class balance is a reported target, not
   a quota cap: do not discard valid cases merely to match scarce overflow.
   If volume/coverage cannot be reached, record the shortfall and seek the
   owner's choice instead of padding samples or weakening validation.
5. Round-trip `plan.json` through
   `mutation_plan.load_plan(raw, manifest=original_manifest)` and generate
   `build-requests.json`. Run again into a fresh output directory with the same
   inputs/seed; both files must be byte-identical. Check exact source RHS and
   translation-only patch scope again in the separate builder.
6. Keep runtime gates pending. Later, use same-builder empty controls, run the
   mandatory empty-vs-single calibration, then qualify each mutation's actual
   glyph/owner behavior, D-023/D-025 boundaries and cross-screen impact. Any
   outside-mask calibration change not proven by D-054 stops with counts/bboxes/max
   deltas. A source-qualified overflow that does not visibly
   overflow its own label stops qualification. Only real batch interference
   may trigger deterministic splitting, with the split rate reported. An
   operational error is not interference or a clean result.

### Dev-only worked examples (not a target-selection dependency)

- `Mining`, `Masonry` and `Construction` on different TechButtons illustrate the
  ellipsis path and distinct-target accounting. Their unselected state avoids a
  selected-description full-value exception; this does not justify
  assuming that every other title shortens, or that scroll clipping is a defect.
- The Gameplay Options backdrop's `?` -> `Help`/`Hilfe` illustrates a small,
  source-fixed label without wrapping. Both languages refer to the same widget;
  adding exclamation variants would not add a target. Source qualification is
  not runtime evidence.
- `Worker` -> `Arbeiter` in EN illustrates two visible logical widgets from one
  recipe. Its growing/wrapping title is not an overflow or truncation example.
- `Research [technology]` with an unmatched `[amount]` value token illustrates
  broken-template `other`, not a wrong-language case or an ordinary literal
  string into which any bracket token may be inserted.

## Labels, owner workflow and verification

Every production screenshot and intended mechanism still needs Anton's visual
review. The manifest is only a labeling aid. Even the empty-patch capture is
uninjected, not automatically a human-confirmed clean label. No labels, including
empty-label files, are generated. Exploratory images never become production
labels/evaluation inputs (D-012/D-024).

The future owner runner is **not implemented** in this task. A separately
approved owner session may later reuse the frozen core with owner-controlled
external output. No protected location, data access, execution or bypass is
needed to document that future boundary.

Offline gates:

```sh
uv run pytest
uv run ruff check .
uv run ruff format --check .
git diff --check
```

Device tests and empirical calibration are intentionally not run for PR (a).
The issue's full runtime acceptance remains with PR (c); an offline plan and
synthetic split test do not satisfy it by themselves.
