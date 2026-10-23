# Issue #47 — review fixes Report

**Ready for draft PR preparation, not merge acceptance.** All 20 regenerated
references remain unconfirmed, the two D-025 scroll checks remain Anton-owned,
and the final changes need independent review. Cross-build Tech Picker
observations are **recorded under D-0XX**, not an acceptance blocker by
themselves. The historical comparison result is preserved.

## What changed

Implemented sections 1, 2a–2b, 3, 4 and 5 of Anton's 2026-10-23 review-fix list.
Fully visible text is no longer demoted solely for `icon_glyph:*` or
`markup_input`; warnings remain. Candidate transcription removes exactly the
characters identified by that element's engine icon warnings, with horizontal
whitespace collapsed and line breaks/unreported symbols retained. All other
uncertainty, clipping and numeric-only rules remain diagnostic. No Unicode
range is guessed and no reference is confirmed automatically.

The method document now describes the workflow rather than the attempt diary.
The history is summarized below, with exact prior evidence in output archives.
Three D-0XX entries remain Proposed; the new criterion was approved by Anton,
but numbering/status acceptance waits for coordinated rebase/merge. D-038,
D-039 and every previous decision byte are unchanged.

## Candidate regeneration and real checks

Generated 20 portable pages offline from existing `data/issue-47/capture-approved-2`
using `l10n-reference generate`, exit 0. No capture was run. The new output is
`issue-47-review-1271048-r2` and its ZIP. The old directory/ZIP remain untouched.
Each new JSON names its parent candidate hash and includes exact
`parent-candidate.json` bytes. PNG/dump/pair bytes are identical to the old pack.

| Rows across 20 candidates | Before | After |
|---|---:|---:|
| Primary | 405 | 441 |
| Diagnostic | 328 | 292 |
| Total | 733 | 733 |

Exactly **36** rows moved: **30** with icon warnings only (apart from
`source_unavailable`) and **6** with markup warnings only. 105 text fields
changed through warning-based icon removal, preserving unreported symbols,
and whitespace normalization; row identities/counts, geometry, warnings,
visibility and all other row fields stayed unchanged.

Real checks: `Kaufen 160¤` → `Kaufen 160`; `Arbeiter\n31⚙ 8⏳` →
`Arbeiter\n31 8`, both now primary; `Requires at least 2 population` retains
its text/markup warning and becomes primary. Standalone costs remain diagnostic.
The independent audit checked full units against raw dump text, all 20 hash
bindings and 30/6 promotions. Clipped rows remain diagnostic with hidden input
separate. See [per-screen counts/changed rows](review-fixes/candidate-changes.json)
and [the separate audit](review-fixes/candidate-independent-check.json).

## How it was verified

- New regressions on old production code: 7 failed / 2 passed, exit 1; after the fix the whole dump module passed 30 tests, exit 0. [Red evidence](review-fixes/regression-before-fix.txt.gz), [focused output](review-fixes/focused-tests.txt).
- Full offline `uv run --offline --cache-dir /private/tmp/issue47-uv-cache pytest -q -rs`: **1478 passed, 2 skipped**, exit 0. [Output](review-fixes/pytest.txt). Skips are the existing opt-in capture/hook device tests; `--run-device` was not run because this round expressly prohibits device commands.
- `uv run ... ruff check .`, `uv run ... ruff format --check .`, and `git diff --check`: exit 0; 82 Python files formatted. Exact command/exit receipts are in [checks.json](review-fixes/checks.json). The task delivery index carries the final committed revision and final-head check receipt.
- The pre-existing Kotlin host samples remain because the contract tests consume their exact bytes. Existing wheel packaging evidence remains; no wheel/APK/Gradle build was rerun.
- The real candidate examples were checked offline. Retained magnified EN/DE pixel-comparison images were visually inspected again; no text/layout change was found. No new pixel experiment was performed.

## Fork scope and evidence limits

Anton answered **“Да, разделить ветки”** on 2026-10-23. The clean local
`feat/47-engine-text-dump` now points to **b534a8ae67c390412984869c7a03b168d532c36c**;
`diag/47-render-diagnostics` preserves **c8eb6fb7e42fc29cdc2b20a813f475d645fbf4be**.
Production PR scope is `877b0dc..b534a8a`. Production source/APK are unchanged:
1271048, SHA-256 `91d9a900f8204880e590de7fb90f0fc15e2aa5cf5d94a3ae77364497d7b0541e`.
The diagnostic APK and all other retained APKs remain intact. See
[branch/approval/artifact receipt](review-fixes/fork-branch-split.json).

Retained production host evidence reports **937 passed, 20 existing skipped**,
49/49 l10n tests, test/build/lint exit 0, lint 0 errors/36 warnings;
[verification](replacement-host/fork-host-verification.json),
[test/skip list](replacement-host/fork-test-summary.json),
[full log](replacement-host/fork-host-checks.log.gz),
[lint XML](replacement-host/fork-lint-results-debug.xml),
[red regression](replacement-host/fork-regression-before-fix.xml),
[focused green log](replacement-host/fork-focused-after-fix.log.gz),
[APK metadata](replacement-host/fork-apk-badging.txt) and
[signature](replacement-host/fork-apk-signing.txt). These are retained results,
not a new Gradle/device run.

The PR descriptions record four known limitations without modifying this pin:
unplanned post-terminal callbacks can swap an undrawn back buffer; background
ownership reads (`terminal`/hook fields, unlike already-volatile `retired`)
are advisory; ordinary-play construction exceptions propagate through the
concurrency wrapper rather than failing on the GL thread; host lifecycle
tests exercise helpers, not hook `render()/start()/fail()` integration.
A separate hook-level host-test issue is proposed locally, not published.

## Retained device results and history

[Attempt 2 report](device-attempt-2/report.md) records 40/40 1271048 pairs and
20/20 identical pixel/dump repeats. [Summary](device-attempt-2/capture-summary.json),
[exit](device-attempt-2/capture-exit.json),
[v1/fault/recovery primer](device-attempt-2/primer-result.json),
[supersession](device-attempt-2/lifecycle-result.json),
[freeze observations](device-attempt-2/freeze-analysis.json),
[ordinary input](device-attempt-2/ordinary-visual-inspection.json),
[legacy device test](device-attempt-2/legacy-device-test.txt),
[test receipt](device-attempt-2/legacy-device-test.json),
[restoration](device-attempt-2/final-preservation.json),
[write ledger](device-attempt-2/execution-ledger.json),
[authorization](device-attempt-2/authorization.json),
[exact capture plan](device-attempt-2/capture-device-plan.json),
[install](device-attempt-2/install-result.json) and
[build verification](device-attempt-2/postinstall-verification.json) remain.
The old pinned hook pytest was not run on 1271048; its expectation was not weakened.

[Attempt 3 analysis](device-attempt-3/analysis.json) and
[raw results](device-attempt-3/result.json) establish the four German
Tech Picker same-build v1/v2 cold/warm arms; their sampled PNGs match. This is
not all-screen paired v1/v2 coverage. Its [preservation receipt](device-attempt-3/final-preservation.json)
and the [last restoration receipt](device-attempt-5/final-preservation.json)
are retained. The latter records 1271048 restored, original settings/four
saves unchanged and app stopped; this revision did not query the device.

[One short pixel history/decision summary](pixel-summary.md) replaces detailed
investigation files in the PR. Raw 1271045 comparison status `failed`/exit 2
is preserved; EN 40 pixels/max delta 1 and DE 72/max delta 2 are recorded
under the new D-0XX. Alpha, observed text and layout are unchanged. Binary
controls and diagnostic 1271049 did not establish a cause. Investigation
stays closed. The unisolated freeze-versus-redraw hypothesis is historical.
No diagnostic code is in the selected production PR.

## Publication cleanup and file accounting

Before removal, **all 163 original evidence files** were written to
`issue-47-pre-review-fixes-evidence.zip` and compared byte-for-byte against
readback. **128 removed files, 128 exact archive matches; zero missing or
mismatched files**. 35 original files remain (one historical report has a
current-status note); new concise reports/audits/checks accompany them.
The archive also preserves old output reports, PR drafts and delivery index;
a separate note archive preserves the original pixel host note. No task
output, run record or private backup was deleted. Nothing private was added
to a public bundle.

[Archive receipt](review-fixes/archive-check.json) lists every removed file,
SHA-256 and ZIP entry with byte equality verified before removal. The full
163-file receipt is also delivered in outputs. [Changed-files inventory](review-fixes/changed-files.json)
lists every checker file changed/added/removed this round. The three synthetic
samples and [wheel inspection](wheel-inspection.json)/[wheel log](checker-wheel.txt)
remain because tests or retained verification use them.

Unpublished PR drafts now select exact production revisions, include reciprocal
local draft links (actual URLs wait for authorized publication), all three
Proposed decisions and known limitations. **#44 closes through the checker
#47 merge**, not a fork-only merge. No push, PR, issue or merge occurred.

## Deviations and remaining acceptance

Optional 2c (clipped-fragment region refinement) was skipped to keep this fix
bounded; diagnostic regions still use the element glyph box. No new dependency,
baseline/OCR, label, translation, matching, metric, golden, detector or fixture
change. Every pre-existing decision byte is preserved. No secrets or hold-out
access. One host helper initially used system Python without Pillow (exit 1,
before candidate mutation); rerunning with the existing checker venv succeeded.
No package installation was needed. The staged diff check then caught trailing
spaces in raw pytest assertion output; the first commit command incorrectly
continued after that nonzero check. A follow-up preserves the exact log in
lossless gzip (also retained raw in outputs), with decompression hash receipt.
The complete branch diff is checked after correction; no evidence bytes were
normalized and no failing regression was weakened.

Anton still owns all 20 confirmations/timing and the Victory Status/Civilopedia
D-025 scroll checks. Final fixes require independent review, numbering on
rebase and merge acceptance. Draft publication requires separate authorization;
actual reciprocal PR URLs will be set then.

## API usage

This revision: **0 device commands, 0 APK builds, 0 provider requests, USD 0**.
Two read-only GitHub issue fetches checked #47/#44 contracts; no remote mutation.
