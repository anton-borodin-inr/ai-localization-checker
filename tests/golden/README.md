Golden tests check the metric and matching code against small, fixed examples.
Their expected values are computed by hand by Anton and are never changed to make a test pass.

`matching_cases.json` holds the matching and metric cases for issue #13. Each case gives:

- `labels`: what is really on the screen (Anton's ground truth, format of `docs/labeling.md`);
- `findings`: what a detector reported (format of the D-018 finding schema);
- `status`: `checked` or `not_checked` (D-013);
- `screen_texts`: every text visible on the screen, so that a hallucinated finding (text not on the screen at all) can be told apart from a wrong judgement about real text;
- `expected`: TP, FP, FN, precision, recall on checked screens, recall on all screens, hallucinations, collapsed duplicates, not-checked screens and the confusion table (label type → finding type) for matched findings. `null` means undefined (zero denominator).

The rules behind the cases are D-026 (matching), D-025 (scroll clipping) and D-023 (ellipsis).
The fuzzy text threshold is a parameter: any value for which cases 08a and 08b match and 08c does not is acceptable.
