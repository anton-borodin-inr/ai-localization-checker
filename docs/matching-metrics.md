# Matching and metrics v0

Issue #13 implements D-026; it supersedes the type-strict matching of D-009
and D-018's old restriction on `other`. Golden expectations belong to Anton
and live in `tests/golden/matching_cases.json`. They are read directly by tests.
No provider, image access, OCR or translation lookup is performed here.

## Matching API

`l10n_checker.matching.match_screen(labels, findings, screen_texts, status="checked",
config=MatchingConfig())` accepts `Label` objects and existing `vision.Finding`
objects. Labels include optional `note`, and allow `other` for broken placeholders
(D-027). Keep raw keys as `untranslated`; the matcher does not infer ground truth.
`screen_texts` must include every visible occurrence, including repeated clean
text. A false positive about scroll clipping remains a false positive (D-025).
Inputs are not rewritten. Result indices refer to their original input order,
so callers can recover IDs without adding IDs to the provider schema.

Provisional conventions (D-029, Proposed):

- Normalize to Unicode NFC, collapse whitespace and map `…` to `...`.
  Preserve case, accents and other punctuation.
- Similarity is `1 - LevenshteinDistance(finding, label) / max(lengths)`.
  A nonempty pair matches at or above `MatchingConfig.text_threshold` (default
  **0.90**). Empty strings never identify labels.
- Alternatively, a finding ending in an ellipsis may identify a label by prefix.
  Remove the terminal ellipsis from both texts and trim the bodies. The finding
  body must be an exact prefix of the label body, contain at least
  `prefix_min_words` (default **2**), and cover at least `prefix_min_coverage`
  (default **0.50**) of the visible label body. The word minimum cannot be below 2.
- The score is the maximum of accepted similarity and accepted prefix coverage.
  Each finding chooses the highest-scoring eligible label, breaking ties by
  label input order. Type and confidence do not affect detection.
- Region restricts candidates only when a label's normalized visible text occurs
  more than once in `screen_texts` or the labels. It must then equal the label's
  grid cell. Unique text ignores region, including distant cells. Region values
  retain D-025's bounding-box-centre interpretation.
- Findings selecting the same label collapse to one detection: keep the strongest
  text score, then the first finding in input order. Its original type is used
  for classification; a correct type is never preferred over `other`.
- Presence is weaker than identification. An unmatched finding is real text if
  its nonempty body (terminal ellipsis removed) is a literal substring of a
  visible text, or near-exact similarity meets the configured text threshold.
  Otherwise it is a hallucination and a FP. Only findings assigned to a label
  collapse; unmatched findings remain separate FP records.

With the defaults, golden 08a matches by similarity `1 - 1/21`; 08b matches
by prefix coverage `11/18`; 08c fails identification but is present as a literal
fragment. These defaults are provisional, not a final evaluation threshold.

`ScreenMatches` exposes matched pairs, unmatched finding/label indices, duplicate
indices and hallucination indices. A `not_checked` result carries no findings
and does not classify labels as checked misses. Unknown status or findings on a
`not_checked` screen raise `ValueError` rather than silently becoming clean.

## Metrics API

`l10n_checker.metrics.score_screen(screen_matches)` scores one result;
`score_screens(iterable_of_screen_matches)` scores a dataset. Counts are summed
before dividing, rather than averaging screen ratios:

- `tp`: matched labels; `fp`: unmatched findings after collapse.
- `fn`: unmatched labels on **checked** screens only.
- `fn_on_not_checked`: all labels on failed/unchecked screens, kept separately.
- `precision = tp / (tp + fp)`.
- `recall_checked = tp / (tp + fn)`.
- `recall_all = tp / (tp + fn + fn_on_not_checked)`.

Any zero denominator returns Python `None`. `Metrics.to_dict()` preserves it
as JSON `null`; it never substitutes zero, one or NaN. `confusion` counts
`label_type` → `finding_type` for retained matches, including wrong categories
and `other`. Duplicates contribute only the representative. Hallucinations are
a subset of FP, not an additional FP penalty.

`not_checked_screens` counts failed/unchecked screens, including those without
labels. They never become true negatives. Callers retain the screenshot ID
alongside each `ScreenMatches` to list failed screens; scoring does not invent
IDs or reinterpret an API failure as a checked empty finding list. Existing
`vision.CheckResult` supplies the detector's checked/not_checked status.

## Verification and manual comparison

Run `uv run pytest tests/golden` for Anton's hand-computed examples. Every case
runs; expected values are never copied into the test source or rounded.

For example, inspect `03_identical_labels_region_decides` in the golden JSON,
recompute its result by hand, then print the actual result offline:

```sh
PYTHONPATH=src uv run python scripts/score_golden.py 03_identical_labels_region_decides
```

`PYTHONPATH=src` also works around the standalone hidden editable-hook issue
described in D-019. The script reads the specification but never uses `expected`
to compute results. For the failure-status example, pass
`11_not_checked_screen`; undefined metrics print as `null`. Neither command
contacts a provider. Anton performs the independent hand comparison (D-012).
