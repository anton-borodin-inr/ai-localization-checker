# Issue #47 — both D-025 manual checks passed

Anton directly reported both manual results on 2026-10-26 in the ordinary
interactive Unciv 1271048 session, German, loaded from `issue-8-pair`.

| Check | Human result | Status |
|---|---|---|
| Victory Status → Unser Status | After scrolling in all directions, all victory headings and conditions are fully visible and legible, without persistent clipping. | Passed |
| Civilopedia → Tutorials → Unterschiede zu Civilization V, top category ribbon | After scrolling in all directions, all category names are visible, legible and uncut. | Passed |

Civilopedia report, verbatim:

> Проверил скролл во все стороны, все названия категорий видны, читаемы и не обрезаны

Receipts: `issue-47-victory-status-scroll-check-20261026.json` and
`issue-47-civilopedia-scroll-check-20261026.json`. Their setup receipts/screenshots
retain the original viewport-clipped states and verified build/language/save.
These are Anton's human results, not an agent rerun. They establish that the
checked content is accessible through scrolling under Accepted D-025; they
do not assert new EN coverage, new pixel equality or a change to any label.

All 20 static visible-text references were already confirmed by Anton's
explicit chat approval. The final set remains 441 primary / 271 diagnostic,
with 21 empty diagnostic records preserved separately. Review time remains
unmeasured. No source, fixture, translation, metric, golden or Accepted decision
was changed; no device operation or provider call was made for this update.

The human reference and D-025 acceptance items are complete. Publication of
the two coordinated PRs is a separate next step: number the three Proposed
D-0XX entries on rebase, add reciprocal actual PR links, and retain Anton's
merge ownership. No push, PR, merge or issue closure occurred here. The
current device state was not queried after the user's check; no app stop or
emulator shutdown was performed by this update.
