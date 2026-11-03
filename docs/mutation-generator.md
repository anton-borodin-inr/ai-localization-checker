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

## Frozen recipes and occurrence accounting

`fixtures/stage3/recipes-v1.json` pins fork `b534a8a`, the source behind the
1271048 static inventory. A recipe specifies an immutable ID, language, intended
class/mechanism, literal source key, exact original RHS (empty is distinct from
absent), replacement or deletion, source evidence and clean target selectors.
Only the English/German translation asset paths can be emitted. Source keys are
never renamed. Unsupported escaped/multiline property edits are rejected rather
than normalized; a future recipe-format change must define their encoding.

The current catalog plans the following **intended occurrences**, not labels:

| Intended class | EN | DE |
|---|---|---|
| `overflow` | `?` -> `Help`, `Help!` | `?` -> `Hilfe`, `Hilfe!` |
| `truncated_text` | Two fixed Mining length variants | Two fixed Mining length variants |
| `wrong_language` | Worker -> Arbeiter, in two visible widgets | One Mining deletion and one explicit English Mining value |
| `other` | Broken Research placeholder | Broken Research placeholder |

There are equal planned quotas of the three primary classes per language;
placeholder cases are separate. A one-class qualification plan is permitted but
carries the `primary_class_balance` production blocker. The manifest reports
both recipe counts and per-language intended-occurrence balance, never detector
quality. Similar variants on the same widget do not establish interface breadth
or independent quality evidence.

### Source-qualified overflow candidate, not runtime evidence

The main-menu help circle behind Gameplay Options is one fully visible logical
text occurrence in each dev language. At the pinned fork,
`MainMenuScreen.kt:216-227` creates a plain 48-unit translated label;
`IconCircleGroup.kt:23-29` resizes it to 45x45 scene units without enabling wrap
or ellipsis. The current owner is
`root/3:IconCircleGroup/1:IconCircleGroup/1:Label`.

Qualify `Help` and `Hilfe` first, then their exclamation variants. Require actual
horizontal **own-label** overflow, N compliance, the pixel gate and unchanged
unmutated dump elements. Any failing overflow singleton means **stop**, not
substitution of the old global hourglass recipe. That recipe affects many
visible counters and is intentionally absent from this catalog. Worker long
text is also not an overflow recipe: issue 45 observed wrapping/panel growth.
No injected help-circle screenshot has been produced in this PR.

### Other boundaries

- EN can show `wrong_language` through explicit foreign values. Only the
  source-English missing-entry fallback is inapplicable as wrong-language in EN.
- A packaged DE deletion is genuine fallback. Replacing its value with English
  is a distinct foreign-text recipe even when both display the same word.
  Omission from a mod would expose the packaged German value, not remove it.
- Research keeps source key `Research [technology]` and changes only the value's
  token to `[amount]`. It is not the Worker literal-token recipe.
- Mining remains unselected, with Archery selected. D-023's full-text-elsewhere
  exception and D-025's viewport exclusion must still be checked at qualification
  and human review. Dump flags do not create labels. D-047 is unchanged.

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

1. **Zero changed RGBA pixels outside the mask.**
2. **No moved/changed unmutated dump element**, including inside masked areas.
3. Every intended mutation is visible and within the occurrence limit.

Incremental font-atlas allocation may change unrelated pixels (D-042). If the
calibration has outside-mask differences, **stop before production** and report
counts, exclusive bounding boxes and maximum channel deltas. No tolerance,
font-atlas workaround or gate weakening is authorized. D-042's historical
cross-build allowance is not itself the mutation gate.

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
