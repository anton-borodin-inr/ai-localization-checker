# Issue #41 Report

**Capture implementation and New Game correction verified. Pending: Anton's
gallery review, the two D-025 on-device checks and independent code review.
D-039 remains Proposed. The review set explicitly combines 18 original pairs
with two corrected New Game pairs; a new full ten-screen run after the template
fix was not performed.**
The installed CLI still needs this Mac's existing hidden-`.pth` workaround
(`PYTHONPATH=src`); this task does not fix packaging or the filesystem flag setter.

Branch `feat/41-screen-capture`, based on checker main `eb5616d`.
Implementation under test: `e0d2888`; fixtures/decision commit: `05fa997`.
New Game fixture/test correction under test: `383a13f`.

## New Game correction before review

Anton identified a missing "Auf Standardwerte zurücksetzen" button. Independent
decoded-RGBA comparison against `issue-40-screenshots-1271045.zip` confirms
44,997 changed pixels in the original #41 `new-game/de` capture, bounding box
`[1616, 950, 2131, 1040]`. The other nine German screens match #40 with zero
changed pixels (`reference-comparison-before-fix.json`). Repeatability of the
original run did not establish equivalence with the intended #40 screen.

At [NewGameScreen.kt:107 in 877b0dc](https://github.com/anton-borodin-inr/Unciv/blob/877b0dc/core/src/com/unciv/ui/screens/newgamescreen/NewGameScreen.kt#L107),
the button is conditional on `settings.lastGameSetup != null`. Both original
templates omitted that field and therefore used the null default. Both now
contain the same fixed `lastGameSetup` object from the verified #40 settings
backup (SHA-256 `7fc6dff53a9ff0b1a87e75c530edcf98fc000ee3dfa6f04d6feccd7085f9bfa7`).
No personal fields were copied. The displayed fields still come from the
unchanged D-038 `new_game` state (SHA-256
`72b95927042892b69c9693646c449a1c5b8e945b33c585cdd862c330be83886a`).
No hook, protocol, runner or CLI change was needed. The fixture contract test
now checks the fixed setup in both languages and the distinct D-038 setup seed.
Before the correction writes, checked the complete setup structure and all
string values: `players` contains only `{"playerType":"Human"}` and three
empty objects. There is no `playerId`, multiplayer user id, UUID, email or other
personal identifier. Both templates remained unchanged after approval;
`settings-privacy-check.json` records their unchanged approved payload hashes.

Updated settings SHA-256: EN
`853e1a055177314c866ae4427e697adeb6f79cab051d31bff0d6160b149c1776`, DE
`397ddd96452874b01d9f096311049c0d076492297d557a9fb7c3d2abf1f3cdea`.
The full updated manifest SHA-256 is
`2c181c26f0f924d47036846f6eeadaf1366eaac361ccb0c106b99544e8d8700d`.
For this targeted correction, a frozen copy under
`data/issue-41/new-game-fix-inputs/` retains only the `new-game` screen entry;
all remaining fields and referenced bytes are unchanged. Its manifest SHA-256
is `442813d4b81cca8ce7434c9d731e1a85049ce82b28b33b25c2e488ebf6a5e06f`
(`new-game-fix-inputs.json`). The executed loop was pass 1 EN/DE, then pass 2
EN/DE, with one screen each: four cold launches and four captures. A single
screen cannot itself test order dependence; the original ten-screen reverse
pass remains the evidence for that check. The other nine screens are not
recaptured in this correction. Old raw summaries, PNGs and audit are retained.

After Anton confirmed exactly the five settings writes, ran:

```sh
PYTHONPATH=src uv run l10n-capture \
  --manifest data/issue-41/new-game-fix-inputs/screens.json \
  --lang en --lang de --repeat 2 --timeout 90 \
  --device-plan data/issue-41/new-game-fix-preflight-20261021/device-plan.json \
  --output-dir data/issue-41/new-game-fix-capture-20261021
```

Exit **0**, **4/4 READY/captured**, five matching panes per request, no ERROR,
timeout or recovery restart. Independently decoded/hashed all four PNGs and
recomputed comparisons without the runner's comparison helper:

| Comparison | Differing pixels | Share | Bounding box |
|---|---:|---:|---|
| Corrected EN pass 1 vs pass 2 | 0 | 0.0 | null |
| Corrected DE pass 1 vs pass 2 | 0 | 0.0 | null |
| Corrected DE pass 1 vs #40 | 0 | 0.0 | null |
| Corrected DE pass 2 vs #40 | 0 | 0.0 | null |

Visually inspected both corrected primary images: the reset button is visible
in both languages. Preview, player list and requested fields remain fixed; no
English-specific state override was required. All comparisons contain
2,592,000 pixels. `new-game-fix-audit.json` records the independent audit;
`new-game-fix-summary.json` preserves raw run output (SHA-256
`e077a8c04e81063dd9ff5405a1bd5608943c58c473d9136aa1cf8d182a586364`).
`reference-comparison-after-fix.json` also compares the other nine German
screens from the original run with #40 in both passes: all 20 effective German
comparisons differ by zero pixels. Per-image manifest, settings, state, source
run and PNG hashes are explicit in `review-set-provenance.json`.

Checks after the template/test change: `uv run pytest -q` **1448 passed,
2 skipped**, 9.32 s; both skips are device opt-in tests. Final offline rerun
`uv run pytest -q --junitxml=data/issue-41/pytest-offline-final.xml`: **1448
passed, 2 skipped**, 7.89 s, exit 0 (`pytest-offline-final.txt`). Final
`uv run ruff check .` and `uv run ruff format --check .` both passed (74 files).
`git diff --check` also passed. The prior full `--run-device` result
predates this correction; it is not claimed as a rerun of the corrected
templates. Runtime capture/device code did not change. The correction was
verified by four live captures instead; the approved correction batch permits
five settings writes only, so a full device-suite rerun (two additional legacy
test writes) was not performed.

## What changed

- Two committed hash-verified saves and provenance, fixed EN/DE settings and ten
  D-038 states from the #40 archive. Screen 09 explicitly has empty notifications
  on turn 1. Screen 10 alone uses the accepted Belgrade fixture and retains the
  ordinary first-contact effects (+30 gold); other in-game screens use the base.
- Strict file/hash/manifest validation and configured languages. Each visible pane
  has one instruction, including zero-range panes; anchors are preferred and the
  world camera follows D-038. Complete language overrides are explicit hash-pinned
  files. **No English override was required for any of the ten screens.**
- Manifest CLI sends three extras with unique ids, establishes fresh logcat
  barriers and waits for PANES/READY/ERROR matching both screen and request.
  There is no fixed settle delay in manifest capture. Failures produce no PNG;
  uncertain/timeout requests force-stop before another request. D-038 and the hook
  are unchanged; #44 robustness work remains outside this task.
- Forward and reverse passes keep languages outside the screen loop and start
  fresh per language. The runner checks foreground, cutout, build, settings and
  complete PNG decoding, then produces pixel comparisons, a write/error journal
  and a review gallery. Existing output requires explicit overwrite and the old
  run is preserved, preventing stale success images after a failed rerun.
- Preparation verifies private settings/save backups without writing app data.
  Execution checks the prepared plan before writes, restores original settings
  bytes/metadata, retains backups and verifies saves. Matching saves are never
  copied or replaced. No new dependencies.
- The existing ordinary-APK mode and D-024 manual capture / Stage 1 replay remain
  available; the removal inventory below records why they were retained.

### Every changed file

- `docs/capture.md`
- `docs/decisions.md`
- `docs/evidence/41/app-data-operations.json`
- `docs/evidence/41/capture-audit.json`
- `docs/evidence/41/capture-summary.json`
- `docs/evidence/41/data-preservation.json`
- `docs/evidence/41/new-game-fix-audit.json`
- `docs/evidence/41/new-game-fix-data-preservation.json`
- `docs/evidence/41/new-game-fix-device-plan.json`
- `docs/evidence/41/new-game-fix-inputs.json`
- `docs/evidence/41/new-game-fix-summary.json`
- `docs/evidence/41/pytest-device.txt`
- `docs/evidence/41/pytest-device.xml`
- `docs/evidence/41/pytest-offline-final.txt`
- `docs/evidence/41/reference-comparison-after-fix.json`
- `docs/evidence/41/reference-comparison-before-fix.json`
- `docs/evidence/41/report.md`
- `docs/evidence/41/review-set-provenance.json`
- `docs/evidence/41/settings-privacy-check.json`
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

The checks below describe the original ten-screen run, before the New Game
template/test correction documented above. They ran after its last runtime
Python change; the correction leaves runtime code unchanged.

- `uv run pytest --run-device --junitxml=data/issue-41/pytest-device.xml`:
  **1450 passed, 0 skipped, 0 failures/errors**, 42.76 s, exit 0. This includes
  the real ordinary-APK capture and real D-038 transport smoke. Exact stdout is
  `pytest-device.txt`; the complete JUnit file is `pytest-device.xml`.
- `uv run pytest -q`: **1448 passed, 2 skipped**, 9.66 s, exit 0. Both skips are
  device opt-in tests, subsequently passed in the full device run above.
- `uv run ruff check .`: passed; `uv run ruff format --check .`: passed,
  74 files already formatted. Initial lint/style findings were fixed. No failing
  test or golden expectation was removed, weakened or changed.
- `git diff --check`: passed and checked again for the evidence commit.
- Initial `uv sync --offline` failed at sandbox cache access, then succeeded with
  approved cache access. No dependency/lockfile change.
- Ordinary CLI help and the initial prepare invocation failed at import with
  `ModuleNotFoundError`, before device access. Editable `.pth` had `UF_HIDDEN`;
  a local `chflags nohidden` attempt did not persistently resolve it. CLI help,
  preparation and capture all succeeded with `PYTHONPATH=src`. This is a host
  source-path workaround, not an editable-install fix (D-019).
- `PYTHONPATH=src uv run l10n-capture --manifest fixtures/stage2/screens.json
  --prepare-only --output-dir data/issue-41/preflight-20261021`: exit 0,
  settings/all-save backup readback verified; no app-data writes.
- After Anton separately approved the exact seven-write batch:
  `PYTHONPATH=src uv run l10n-capture --manifest fixtures/stage2/screens.json
  --lang en --lang de --repeat 2 --timeout 90
  --device-plan data/issue-41/preflight-20261021/device-plan.json
  --output-dir data/issue-41/capture-20261021`: **exit 0, 40/40 captured,
  20/20 decoded-pixel-identical pairs, no ERROR, timeout or recovery restart**.
- Independently recomputed all file hashes, complete decoding, both-id terminal
  correlation, pane sets, unique request ids, forward/reverse order and RGBA
  pixel equality from all 40 files, without calling the capture comparison
  helper. Results are in `capture-audit.json`; raw run summary is preserved in
  `capture-summary.json` (SHA-256
  `450082325c429e52f2383a4634f1a54442fa748bb2349e5e557e7b0575b98809`).
- Visually inspected all 20 primary screenshots against target states and the
  generated contact sheet. No changed selection/tab/anchor/camera/fixture state
  was needed for English. Normal EN/DE layout differences remain, for example
  the Statistics row composition and Civilopedia entry order. This is capture
  state verification, not a localization-defect check or human ground truth.
- Final read-only preparation into `data/issue-41/after-device-tests-20261021`:
  exit 0. Original settings bytes/uid/gid/mode/size, all four save hashes and
  installed APK matched the pre-write baseline; app stopped, adbd confirmed as
  shell. Portable evidence is `data-preservation.json`.
- GitHub main rechecked after capture: still `eb5616d`, with D-038 last; D-039
  remains the next free number. No hook, detector, evaluator, matching, metric,
  label, golden or Stage 1 replay inputs changed.

### Repeatability by source screen

Each effective pair has 2,592,000 pixels, differing share **0.0**, and bounding
box **null**. The original pass is 01 to 10 for EN then DE; its second pass is
10 to 01 for EN then DE. All 40 original requests reached READY. The New Game
row below uses its four corrected captures instead; the other nine rows retain
the original run. This composition is explicit in the gallery and provenance.

| Screen | EN differing pixels | DE differing pixels | EN state override |
|---|---:|---:|---|
| options-gameplay | 0 | 0 | None |
| new-game | 0 | 0 | None |
| tech-picker | 0 | 0 | None |
| city-production | 0 | 0 | None |
| empire-stats | 0 | 0 | None |
| policy-picker | 0 | 0 | None |
| victory-status | 0 | 0 | None |
| civilopedia | 0 | 0 | None |
| world | 0 | 0 | None |
| city-state-diplomacy | 0 | 0 | None |

### Review artifacts (local, not committed)

- 20-image gallery: `/Users/antonborodin/Documents/Codex/2026-10-21/next-task-issue-41-https-github/outputs/issue-41-gallery/gallery.html`.
- Contact sheet: `/Users/antonborodin/Documents/Codex/2026-10-21/next-task-issue-41-https-github/outputs/issue-41-gallery/contact-sheet.png`.
- Review ZIP: `/Users/antonborodin/Documents/Codex/2026-10-21/next-task-issue-41-https-github/outputs/issue-41-screenshots-1271045.zip`.
- Full 44-image/evidence ZIP: `/Users/antonborodin/Documents/Codex/2026-10-21/next-task-issue-41-https-github/outputs/issue-41-evidence-1271045.zip`.

The gallery and review ZIP contain the effective 20 primary images: 18 from the
original run plus corrected EN/DE New Game. Every PNG retains its D-003/D-016
name and original 2400 x 1080 pixels. The evidence ZIP retains all 40 original
PNGs and four correction PNGs under distinct run folders, both input versions,
and public verification records. Private settings/save backups are excluded.
The previous public gallery/ZIPs/index were preserved under
`outputs/issue-41-before-new-game-fix/`; no run record was deleted.

## Emulator app-data operations

Anton explicitly confirmed each batch before its app-data writes. **Exactly
twelve agent-initiated settings writes were executed across the whole task**:
seven in the original capture/device-test batch and five in the correction.
All target
`/data/user/0/com.unciv.app/files/GameSettings.json`:

| # | Operation | Payload SHA-256 |
|---:|---|---|
| 1 | replace_settings / en | `008046f1fb619410aa930a68ff2bbb8f8ee20f5a90d3da463130fabaf98c675c` |
| 2 | replace_settings / de | `28d1b5df2733f372e466402981b8e6997093fb21a6d7760cd5090fbab4e8ec87` |
| 3 | replace_settings / en | `008046f1fb619410aa930a68ff2bbb8f8ee20f5a90d3da463130fabaf98c675c` |
| 4 | replace_settings / de | `28d1b5df2733f372e466402981b8e6997093fb21a6d7760cd5090fbab4e8ec87` |
| 5 | restore_original_settings | `7fc6dff53a9ff0b1a87e75c530edcf98fc000ee3dfa6f04d6feccd7085f9bfa7` |
| 6 | legacy_device_test_apply_english | `99f9b6b293c1e6268d6d18891805872e1546c177775680f2718e8c206dcb4b23` |
| 7 | legacy_device_test_restore_original | `7fc6dff53a9ff0b1a87e75c530edcf98fc000ee3dfa6f04d6feccd7085f9bfa7` |

The first five are individually journaled and read back by capture. The last
two are the retained real main-menu test: `unciv_language` verifies the written
payload and restoration; that test passed, and final independent readback
confirmed the original baseline. The English-only payload hash is derived
from the verified original bytes using the unchanged tested helper. The ledger
records this evidence distinction in `app-data-operations.json`.

Original settings SHA-256:
`7fc6dff53a9ff0b1a87e75c530edcf98fc000ee3dfa6f04d6feccd7085f9bfa7`;
original and final uid/gid/mode/size: `10196 10196 600 873`.
All four saves stayed byte-identical by SHA-256. **Save copies/replacements/
deletions, app installs/uninstalls, data clears and translation changes: zero.**

Original-batch device operations: root/unroot and force-stop; four capture cold starts;
40 sequential hook requests; one ordinary startup and one hook request in device
tests; SDK screencaps; unique diagnostic markers in Android logs. No timeout
recovery occurred in that batch. The test's ordinary main-menu PNG is
under `data/device-tests/`; the hook smoke validates PNG bytes without saving a
Stage 2 image. Private preflight, capture and final-verification backups remain
under `data/issue-41/`, outside Git and public exports.

Correction preparation completed with exit 0 and **zero app-data writes**:
`PYTHONPATH=src uv run l10n-capture
--manifest data/issue-41/new-game-fix-inputs/screens.json --lang en --lang de
--prepare-only --output-dir data/issue-41/new-game-fix-preflight-20261021`.
Fresh settings/all-save backups were read back and verified. APK, original
settings bytes/metadata and all four saves still match the original baseline;
no save copies are needed. The app is stopped and adbd was unrooted on exit.

The following **five additional writes were separately confirmed and executed**,
all to the same `GameSettings.json` path and with unchanged approved hashes:

| # | Operation | Payload SHA-256 |
|---:|---|---|
| 8 | pass 1 / en, capture new-game | `853e1a055177314c866ae4427e697adeb6f79cab051d31bff0d6160b149c1776` |
| 9 | pass 1 / de, capture new-game | `397ddd96452874b01d9f096311049c0d076492297d557a9fb7c3d2abf1f3cdea` |
| 10 | pass 2 / en, capture new-game | `853e1a055177314c866ae4427e697adeb6f79cab051d31bff0d6160b149c1776` |
| 11 | pass 2 / de, capture new-game | `397ddd96452874b01d9f096311049c0d076492297d557a9fb7c3d2abf1f3cdea` |
| 12 | restore original bytes/uid/gid/mode | `7fc6dff53a9ff0b1a87e75c530edcf98fc000ee3dfa6f04d6feccd7085f9bfa7` |

Other correction operations: temporary adb root/unroot, force-stop, four cold hook
launches/unique sequential requests, fresh-log matching waits, SDK screencaps,
and final read-only settings/save/build verification. All five write/readbacks
were verified against the approved plan. A final successful prepare-only run
into `data/issue-41/new-game-fix-after-20261021` independently confirmed original
settings SHA-256 `7fc6dff5…`, uid/gid/mode/size `10196 10196 600 873`, all four
save hashes and installed APK unchanged. App stopped; adbd unrooted. Portable
evidence: `new-game-fix-data-preservation.json`; private backups retained.
There were no additional writes beyond these twelve and no save copies.

## Deviations from the task

No scope changes. The old ordinary-APK fixed-delay path remains supported and
isolated from manifest capture; retention reasons are listed above. This host's
CLI source-path workaround is recorded. Images/review ZIPs stay outside Git;
paths and public hash evidence are supplied. No new dependencies.

## Decisions proposed

D-039, **Proposed**: ten source ids (World replaces map editor), accepted empty
turn-1 notifications for screen 09, separate accepted Belgrade fixture for
screen 10 only, and reverse-order pass 2 with languages still outside the screen
loop. D-038 remains Accepted and unchanged, pinned to fork merge `877b0dc`.

## Open questions for Anton

- Review the 20-image gallery, then arrange independent code review and decide
  on D-039 / eventual merge. Author has not approved its own changes.
- Two on-device checks under Accepted D-025 remain exactly as requested:
  horizontal clipping on victory-status; whether Civilopedia's category bar
  actually scrolls. No rule change or label is inferred from those screenshots.
- Push and draft PR are approved. Independent review and Anton's acceptance /
  merge remain separate from that authorization; the author has not approved
  its own changes.

## API usage

Live provider requests **0**, tokens **0**, spend **USD 0**; no provider run ids.
No detector/baseline run, labels, split, truncation check or hold-out access.
