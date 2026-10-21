# Issue #41 Report

**Pending: separate approval for device writes, the 40-image capture and
`uv run pytest --run-device`. English layouts and repeatability remain unverified.**
The installed CLI also needs this host's existing hidden-`.pth` workaround
(`PYTHONPATH=src`); this task does not fix packaging or the filesystem flag setter.

Branch `feat/41-screen-capture`, based on checker main `eb5616d`.

## What changed

- Hash-pinned inputs: two hash-verified saves and provenance, fixed
  English/German settings and ten D-038 states from the #40 evidence archive.
  Screen 09 explicitly has empty notifications on turn 1. Only screen 10 uses
  the accepted Belgrade save, retaining ordinary first-contact effects (+30 gold).
- Strict file/hash/manifest validation; language configuration rather than a
  code change. Complete per-language state overrides are explicit and hash-pinned.
- Manifest CLI, sequential three-extra requests, fresh logcat barriers, exact
  screen/request correlation, complete pane-set checks and no fixed settle delay.
  ERROR/timeout saves no screenshot and continues; uncertain requests force-stop
  before another request. No hook changes or #44 fixes.
- Two passes, forward then reverse, languages outside the screen loop. Full PNG
  validation, decoded-RGBA pixel comparisons, error/write journal and review gallery.
- Read-only preparation backs up settings and all saves. Execution verifies the
  prepared plan, journals every settings write, restores original bytes/metadata,
  retains backups and checks saves. Existing matching saves are never copied.
- The old ordinary-APK path and Stage 1 replay/manual capture remain available.

### Every changed file

- `docs/capture.md`
- `docs/decisions.md`
- `docs/evidence/41/report.md`
- `docs/stage2-capture.md`
- `fixtures/stage2/README.md`
- `fixtures/stage2/provenance.json`
- `fixtures/stage2/saves/issue-40-belgrade-metissue-8-pair`
- `fixtures/stage2/saves/issue-8-pair`
- `fixtures/stage2/screens.json`
- `fixtures/stage2/settings/de.json`
- `fixtures/stage2/settings/en.json`
- `fixtures/stage2/states/city-production.json`
- `fixtures/stage2/states/city-state-diplomacy.json`
- `fixtures/stage2/states/civilopedia.json`
- `fixtures/stage2/states/empire-stats.json`
- `fixtures/stage2/states/new-game.json`
- `fixtures/stage2/states/options-gameplay.json`
- `fixtures/stage2/states/policy-picker.json`
- `fixtures/stage2/states/tech-picker.json`
- `fixtures/stage2/states/victory-status.json`
- `fixtures/stage2/states/world.json`
- `src/l10n_checker/cli.py`
- `src/l10n_checker/hook.py`
- `src/l10n_checker/screen_capture.py`
- `src/l10n_checker/screen_manifest.py`
- `tests/test_hook_device.py`
- `tests/test_screen_capture.py`

## Removal inventory (recorded before any removal)

No removal is currently planned. These candidates were inspected:

| Candidate | Disposition and reason |
|---|---|
| `capture.capture`, `unciv_language`, `DEFAULT_SETTLE_S` | Retain: the single-screen path supports ordinary APKs without D-038. The new manifest path uses hook events and never calls its fixed delay. |
| CLI `--screen`, `--variant`, `--settle` | Retain for the existing single-screen mode. Manifest mode rejects mixing these options. |
| Existing capture/CLI/language tests and real main-menu device test | Retain: they verify the supported ordinary-APK path and settings restoration. Add independent manifest-mode tests. |
| Existing `docs/capture.md` ordinary-APK recipe | Retain and distinguish from Stage 2; it remains an executable workflow. |
| D-024 manual-capture recipes, source-build evidence, Stage 1 pair manifest, replay CLI and tests | Retain unchanged: historical capture provenance and offline slice replay remain available. Any removal changing Stage 1 replay requires Anton's approval first. |

## How it was verified

After the last Python change:

- `uv run pytest -q`: **1448 passed, 2 skipped**, 9.66 s. Both skips require
  `--run-device`: retained main-menu test and new hook transport smoke.
- `uv run ruff check .`: passed. Initial import/format/type-style findings were
  corrected; no failing test was removed or weakened.
- `uv run ruff format --check .`: passed, 74 files already formatted after
  the last Python change.
- `git diff --check`: passed; rechecked before handover.
- Earlier focused capture/CLI tests: 46 passed. Full offline tests exercise
  golden/replay behavior; no matching, metric, label or replay inputs changed.
- `uv sync --offline`: initial sandbox cache access failed; repeated with approved
  cache access succeeded. No dependency or lockfile change.
- Ordinary `uv run l10n-capture --help` and initial prepare invocation failed at
  import with `ModuleNotFoundError`, before device access. The editable `.pth`
  carried `UF_HIDDEN`; a local `chflags nohidden` attempt did not persistently
  resolve it. With `PYTHONPATH=src`, CLI help and preparation succeeded. This is
  a local runtime workaround, not a product-level editable-install fix (D-019).
- `PYTHONPATH=src uv run l10n-capture --manifest fixtures/stage2/screens.json
  --prepare-only --output-dir data/issue-41/preflight-20261021`: exit 0.
  Independently checked installed APK SHA-256/version, density, dimensions,
  disabled cutout, original settings and all four save hashes. Backups verified
  by readback. Prepared plan SHA inputs are retained under that run folder.
- `uv run pytest --run-device`: **not run**, awaiting Anton's explicit approval
  of settings writes. Full captures/gallery: **not run** for the same reason.

## Emulator app-data operations

**Actual settings pushes, save copies, replacements and deletions: none.**
Preparation used adb root, force-stop and unroot, with reads only; app left
stopped, adbd confirmed as shell. Settings baseline: `7fc6dff53a9ff0b1a87e75c530edcf98fc000ee3dfa6f04d6feccd7085f9bfa7`,
uid/gid/mode/size `10196 10196 600 873`. All four saves were backed
up and read back; both fixture hashes match the committed files.

The prepared normal execution batch has five capture settings writes (EN, DE,
EN, DE, restore original) plus two writes in the retained main-menu device test
(English-only original settings, restore original). Exact hashes and order are
in the user-facing device operations document and plan. Save copies needed: none.
These are proposed operations, not a record of execution.

## Deviations from the task

No scope changes. The existing ordinary-APK delay path remains supported and
isolated from manifest capture; reasons are listed in the removal inventory.
This host's source-path CLI workaround is recorded above. No new dependencies.

## Decisions proposed

D-039, status **Proposed**: the ten ids, empty turn-1 notifications for screen 09,
separate accepted Belgrade save for screen 10 only, and reverse second-pass
order. D-038 remains Accepted and unchanged; its full semantics are pinned to
fork merge `877b0dc`. Current decision numbering was checked against `eb5616d`.

## Open questions for Anton

- Approve the seven planned settings writes and capture/device-test batch.
- Pending on-device checks under Accepted D-025: horizontal clipping on
  victory-status, and whether the Civilopedia category bar actually scrolls.
- English-specific states, repeatability differences and gallery review await
  actual device evidence; no result is inferred from #40's German run.

## API usage

Live provider requests **0**, tokens **0**, spend **USD 0**. No detector or
baseline runs, labels, split, truncation check or hold-out access in this task.
