# Issue #47 delivery Report

The production target is fork **b534a8a / APK 1271048**, with 40/40 captured
PNG/dump pairs, 20 identical pixel/dump repeats, 20 human-confirmed references,
and both D-025 manual scroll checks passed. Cross-build Tech Picker differences
are recorded under **D-042**. The three new decisions **D-040–D-042 remain
Proposed**. Human review duration is unmeasured; no QA-time savings claim is
made. These are draft PRs for final review; Anton owns merge acceptance.

## What changed

Protocol v2 opts into correlated engine dumps while preserving v1. Each v2
PNG is bound to exact dump/state/build/image hashes and an atomic capture pair.
Missing, invalid or nonrepeatable dumps fail the capture. The manifest pins
1271048 and retains all D-039 save/state/settings inputs. Candidate generation
preserves occurrences, wrapped/composed units, clipped visible fragments and
provenance. Fully visible icon/markup rows stay primary unless another warning
makes them uncertain; only engine-reported icon characters are omitted.
Local review pages support explicit human edits, timing and hash-bound exports.

The separate fork implements rendered cache/glyph observation and #44 lifecycle
hardening, plus the Android component-key parser crash fix. Production code
stays at `b534a8ae67c390412984869c7a03b168d532c36c`; diagnostic `c8eb6fb`
remains on local `diag/47-render-diagnostics` and is excluded from publication.
The exact production PR base is `877b0dc2ee706dbbdb4a17e14b4522408d197390`.

## Human acceptance and portable references

Anton approved all **20** references in chat: **712 nonempty rows, 441 primary /
271 diagnostic**, with **21 empty clipped records retained separately**.
All 25 diagnostic bullets, nonempty text, order, geometry, flags and regions
are unchanged. No hidden input was completed. The original r1/r2/preparation
sets and every original capture remain available in task outputs.

[Confirmed set and format notes](reference-confirmation/README.md),
[portable ZIP](reference-confirmation/confirmed-reference-set.zip),
[20-screen index](reference-confirmation/reference-index.json),
[explicit authorization](reference-confirmation/chat-authorization.json),
[independent artifact validation](reference-confirmation/validation.json),
[unresolved appendix](reference-confirmation/unresolved-diagnostics-index.json).
The ZIP SHA-256 is `70db55a62819fc7e913af051626c268703517ccf07b0c23d515e185f99dccd51`.
Per-screen JSON snapshots and the ZIP retain exact approved bytes and hashes.

The accepted set uses `explicit-chat-approval-v1`: review timing is
`not_recorded` and null, by Anton's explicit decision. The existing browser-only
`l10n-reference confirm` requires measured timing and was not invoked or
weakened for these records. Task-local preparation/validation, rather than a
simulated browser approval, created the portable references. D-041 records
this disposition. Artifact recording timestamps are not review durations.

Both [D-025 human checks](manual-acceptance/README.md) passed on German 1271048
on 2026-10-26. Anton reports that scrolling reveals all Victory Status headings/
conditions and all Civilopedia category captions fully and legibly. Exact
[Victory report](manual-acceptance/issue-47-victory-status-scroll-check-20261026.json)
and [Civilopedia report](manual-acceptance/issue-47-civilopedia-scroll-check-20261026.json)
bind their verified setups. These are human results, not agent reruns or new
EN/pixel evidence. Private backup payloads and raw UI logs are excluded.

## Verification

[Publication command receipts](publication/checks.json) and accompanying logs
record the fresh offline pytest, Ruff check/format, full checker/fork diff
checks and artifact audit with actual exits. No device test, APK build or
provider call is part of publication. The source fixture/production pin is
unchanged; device tests remain opt-in and are not rerun for docs/evidence.

New candidate regressions reproduced 7 failures before the fix, then all
30 focused dump tests passed: [red output, lossless gzip](review-fixes/regression-before-fix.txt.gz),
[green output](review-fixes/focused-tests.txt). The previously independently
reviewed checker head is `952daa2`; this publication adds evidence/docs and
numbers Proposed decisions without changing its runtime/tests/dependencies.
Both actual Kotlin host samples remain consumed verbatim by contract tests.

Retained fork production checks (not rerun): **937 passed / 20 existing skips**,
all 49 l10n tests passed; full test/build/lint exited 0; lint 0 errors / 36
warnings. [Host verification](replacement-host/fork-host-verification.json),
[test/skip list](replacement-host/fork-test-summary.json),
[full log](replacement-host/fork-host-checks.log.gz),
[lint XML](replacement-host/fork-lint-results-debug.xml),
[Android regression](replacement-host/fork-regression-before-fix.xml),
[focused green](replacement-host/fork-focused-after-fix.log.gz),
[APK metadata](replacement-host/fork-apk-badging.txt),
[signature](replacement-host/fork-apk-signing.txt).

## Device evidence and pixel criterion

[1271048 capture report](device-attempt-2/report.md) retains raw history;
[summary](device-attempt-2/capture-summary.json),
[v1/fault/recovery primer](device-attempt-2/primer-result.json),
[supersession](device-attempt-2/lifecycle-result.json),
[freeze observations](device-attempt-2/freeze-analysis.json),
[ordinary input](device-attempt-2/ordinary-visual-inspection.json),
[real capture pytest](device-attempt-2/legacy-device-test.txt),
[write ledger](device-attempt-2/execution-ledger.json) and
[restoration](device-attempt-2/final-preservation.json) remain. The legacy hook
pytest pins 1271045 and was not weakened to run on 1271048. The
[same-build v1/v2 analysis](device-attempt-3/analysis.json) samples four German
Tech Picker cold/warm arms, not an all-screen paired v1/v2 run. The
[last diagnostic restoration](device-attempt-5/final-preservation.json) restores
exact 1271048 and original settings/saves. Later ordinary manual setups also
verified unchanged settings/four saves before human handoff. The app was left
open for Anton; no post-human-check device-state or emulator-free claim is made.

[Pixel summary](pixel-summary.md): EN 40 pixels, box `[751,469,768,484]`, max
channel delta 1; DE 72 pixels, box `[214,239,237,258]`, max delta 2; alpha
unchanged, no text/layout change found. Raw comparison exit 2/status `failed`
is retained. D-042 replaces the cross-build zero-pixel gate with exact
same-build/repeat checks plus recorded/visually checked cross-build differences.
Root-cause work stays closed; no production correction or numeric tolerance
was invented.

## Deviations, limitations and proposed decisions

Optional clipped-fragment region refinement was explicitly waived by Anton;
regions remain based on element glyph boxes. Draw/scissor visibility does not
prove final opaque occlusion or visual readability. The four fork limitations
are documented in both PR descriptions: undrawn back-buffer swaps on unplanned
terminal callbacks; advisory background ownership reads; ordinary-play
construction exception propagation; helper-only lifecycle host tests.
A [separate hook-test follow-up](publication/hook-tests-follow-up.md) is proposed,
not created or implemented here. The explicit chat/untimed confirmation above
is an approved departure from measured browser export; no timing is fabricated.

D-040 (protocol v2), D-041 (candidate units/hash-bound review) and D-042
(non-interference) remain **Proposed**. Numbers were allocated after verifying
main `63b6534` still ends at D-039; `git rebase origin/main` was already up to
date. Every Accepted decision byte is unchanged. Recheck numbering if main
changes before merge; parallel #45/#48 proposals retain their own scope.

## Publication scope and file accounting

[Scope receipt](publication/scope.json) records the user's publication request,
exact bases/pins and numbering. [Changed files](publication/changed-files.json)
lists the final PR's complete file scope; [accepted artifact hashes](publication/accepted-artifacts.json)
cover all newly included evidence. All 128 old paths removed/relocated during
review cleanup were byte-verified in the retained output archive before
removal; [receipt](review-fixes/archive-check.json) lists each path/hash/ZIP
entry. Git rename detection reports 124 deletions plus four relocations.
The old snapshots are historical evidence, not current acceptance status.

No baseline/OCR, detector, label, translation, matching, metric, golden,
fixture input or dependency change was made during publication. No Accepted
decision changed, and no private settings/save backup or secret was included.
No live provider requests were made for #47; total **USD 0**. No further pixel
or device work is authorized by publication. The checker PR closes #47/#44
only on its coordinated merge after the companion fork; nothing is merged or
closed by draft publication. Anton retains final review/merge ownership.
