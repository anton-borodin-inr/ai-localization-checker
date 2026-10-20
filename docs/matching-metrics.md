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
- A finding is scored against both texts of a label, `text_seen` and
  `text_expected`, with the same similarity and prefix rules; the label's score
  is the better of the two. Models often report the full intended string of a
  truncated label (golden case 12). The score is the maximum of accepted
  similarity and accepted prefix coverage.
- Findings are assigned to labels one-to-one. The assignment maximizes the
  number of matched labels, then the total score (exact fractions, so equal
  scores tie exactly). Among equal assignments it keeps input order: findings
  are decided in order, each prefers its lowest-index label, and a finding stays
  unassigned only if that still reaches the optimum. A finding equally close to
  a taken label and a free label therefore takes the free one (golden case 13).
  The polynomial assignment described below is exact and adds no dependency.
  Type and confidence do not affect detection.
- Region restricts candidates only when a label's normalized visible text occurs
  more than once in `screen_texts` or the labels. It must then equal the label's
  grid cell. Unique text ignores region, including distant cells. Region values
  retain D-025's bounding-box-centre interpretation.
- An unassigned finding that identifies at least one label is a collapsed
  duplicate: by optimality, every label it identifies is already matched
  (golden case 07). The assigned finding is the representative; its original
  type is used for classification, and a correct type is never preferred over
  `other`.
- Presence is weaker than identification. An unassigned finding that identifies
  no label is real text if its nonempty body (terminal ellipsis removed) occurs
  as whole words in a visible text, that is, at word boundaries (Unicode `\w`),
  or if near-exact similarity to a visible text meets the configured threshold.
  A finding that identifies some label's `text_expected` is also real text.
  Otherwise it is a hallucination and a FP. A single letter inside a word is
  not present; a word cut by a truncation ellipsis (`Erzgew` in `Erzgew...`) is.
  Unmatched findings remain separate FP records.

With the defaults, golden 08a matches by similarity `1 - 1/21`; 08b matches
by prefix coverage `11/18`; 08c fails identification but is present as a whole
word. Golden 12 matches by `text_expected`; in golden 13, `Neue Spiel` scores
`1 - 1/11` against both labels and takes the free one. These defaults are
provisional, not a final evaluation threshold.

`ScreenMatches` exposes matched pairs, unmatched finding/label indices, duplicate
indices and hallucination indices. A `not_checked` result carries no findings
and does not classify labels as checked misses. Unknown status or findings on a
`not_checked` screen raise `ValueError` rather than silently becoming clean.

## Exact polynomial assignment (issue #31)

`_assign` uses a rectangular Hungarian algorithm with one row per finding,
`L` real columns for the distinct candidate labels, and `F` dummy columns for
unassigned findings. Missing label indices are compressed in ascending order;
the returned indices still refer to the original labels. Its objective and
result are identical to the former exact search:

1. Maximize the number of matched labels.
2. Maximize the total exact `Fraction` score.
3. Choose the lexicographically smallest assignment in finding input order,
   preferring ascending label indices before `None` at each position.

The priorities are encoded as exact integer weights. Let `D` be the LCM of
all candidate score denominators and scale each score to integer `s`.
Let `M = max(abs(s))`, `B = L + 1`, `T = B**F`, and
`C = (2 * F * M + 1) * T`. A candidate at finding index `f` and compressed
label index `j` has weight:

```text
C + s * T + (L - j) * B**(F - 1 - f)
```

The final term encodes the tie-breaking as base-`B` digits: a lower label index
has a larger digit, an unassigned finding has digit zero, and earlier findings
occupy more significant positions. The total tie term lies in `[0, T - 1]`, so
one scaled score unit outweighs every possible tie difference. Total scaled
scores lie in `[-F*M, F*M]`, so one additional match's `C` outweighs every
possible score and tie difference combined. This also handles zero or negative
candidate scores without weakening cardinality priority, although the current
text matcher supplies positive scores.

Hungarian minimizes the negated candidate weights. Dummy edges cost zero and
nonedges cost one; valid candidate edges always have negative cost. There are
`F` dummy columns, so an assignment using a nonedge could always improve by
switching that row to an unused dummy. Thus a nonedge is never selected.

The algorithm takes `O(F**2 * (L + F))` integer operations and
`O(F * (L + F))` space. Although the encoded weights have large numeric values,
their **bit lengths** are polynomial: the LCM's bit length is at most the sum
of the input denominator bit lengths, and `B**F` needs `O(F * log(L + 1))`
bits. There is no rounding, floating-point objective or epsilon tie-breaker.
Candidate construction, normalization, thresholds, region rules, duplicate
collapse, hallucination rules and metrics are unchanged.

`tests/test_assignment.py` preserves the former production search from
`335f6a4` as an independent test oracle. It compares complete assignments on
1000 seeded small inputs (up to eight labels and ten findings), with deliberate
score ties, sparse indices, empty/dense graphs and exact fractions. Boundary
cases also cover tied sums with different denominators, differences below float
precision, and cardinality priority. The same tests were committed and passed
before replacing the production algorithm. The integration performance test
uses 25 mutually similar `Technologie Nummer NN` labels and 25 findings and
requires the entire `match_screen` call to take less than one second. Existing
human-owned golden expectations remain unchanged.

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
