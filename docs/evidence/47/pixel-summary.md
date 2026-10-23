# Issue 47 pixel observation — recorded under D-0XX

Anton approved the revised non-interference criterion on 2026-10-23. Its
D-0XX entry remains **Proposed** until numbering/rebase before merge. Require
zero changed pixels for same-build v1/v2 and repeats. Record cross-build
count, bounding box, maximum channel delta and a visual text/layout check;
a cross-build difference is not an acceptance blocker by itself.

1271048 attempt 2 captured 40/40 PNG/dump pairs and passed all 20 pixel repeats
and all 20 dump-byte repeats. Against 1271045, 36/40 images match; Tech Picker
has the following difference in both passes:

| Language | Changed pixels | Exclusive bounding box | Maximum absolute channel delta |
|---|---:|---|---:|
| EN | 40 | `[751,469,768,484]` | 1 |
| DE | 72 | `[214,239,237,258]` | 2 |

Alpha is unchanged. The retained magnified EN/DE comparisons were inspected
again offline in this revision: no change to text or layout was found.
[Raw counts and comparison result](device-attempt-2/against-1271045.json) and
[per-pixel/channel evidence](device-attempt-2/tech-picker-pixel-deltas.json)
remain unchanged. The historical compare command returned 2/status `failed`;
this records a difference and has not been rewritten to `identical`.

[Attempt 3](device-attempt-3/analysis.json) sampled German Tech Picker cold v1,
warm v2 after v1, cold v2 and warm v1 after v2 on the same 1271048 build. All
eight PNGs match retained 1271048; both v2 dumps match. This is the bounded
same-build evidence, not a paired v1/v2 check of all 20 screen/language states.

History retained in output archives: the first 1271047 capture crashed before
any successful pair; the literal component-key parser fixed it in 1271048.
Later exact 1271045/1271048 binary controls reproduced each build's pixels.
Diagnostic 1271049 tested loading-gate and telemetry off/on arms: all eight
PNGs matched 1271048, and selected CPU projections matched. Host replays did
not establish the Android cause. Root-cause investigation is **closed** for
this scope, with no production correction or new experiment. Post-READY
freeze versus 1271045 continuous redraw was never isolated; it remains only
a historical hypothesis. This criterion does not change D-038 or D-039,
confirm a candidate, or settle the two D-025 human scroll checks.

Original reports and every removed evidence file are byte-preserved in
`issue-47-pre-review-fixes-evidence.zip` in task outputs; the full
[archive receipt](review-fixes/archive-check.json) lists each removed path,
hash and matching ZIP entry. Existing output archives, including device
rounds 2–5 and host diagnostics, remain intact. Production is pinned to
`b534a8a` / 1271048; diagnostic `c8eb6fb` is retained on its separate branch.
