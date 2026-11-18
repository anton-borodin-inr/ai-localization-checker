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
after final restoration.

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

## Calibration and isolation gate

Before production, capture the empty-patch control and one single-mutation
build on all dev screens in EN and DE. The plan selects the basic EN help
recipe; it is built separately even when it is also part of a batch.

Compare decoded RGBA using a mask derived from all matched before/after
mutated extents, with fixed outward rounding. Never mask a whole parent panel
to hide layout reflow. A comparison passes when:

1. every outside-mask difference is within D-060: each R/G/B delta at most 2,
   alpha unchanged;
2. no unmutated dump element moved or changed, including inside the mask;
3. every intended mutation is visible and within the occurrence limit.

Anything else stops before production with pixel counts, bounding boxes and
maximum channel deltas. D-042's font-atlas effect is the known source of small
cross-build differences.

After a calibration pass, dynamic interference may split production batches.
The split is a proposal for the owner and the fork builder; the split rate is
reported. Operational failures are recorded separately from interference.

`mutation-manifest.json` maps each screenshot to its state, build, pair, PNG
and dump, and records intended-occurrence checks, unmutated-element checks,
masks, tolerated pixels and split lineage. No label files are produced; an
intended class is not a human label.

D-058 (Proposed): visible side-effect flags for review are implemented in
`mutation_verify.semantic_side_effects`, but `l10n-mutate run` does not record
them yet.

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
   outside-mask calibration change beyond D-060 stops with counts/bboxes/max
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
