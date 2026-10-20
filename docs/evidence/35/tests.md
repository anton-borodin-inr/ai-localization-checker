# Issue #35 test evidence

All 26 new parametrized cases failed against unchanged production code at the
test-only commit `0d53c9a` and passed after implementation. The test file is
unchanged between these runs. Baseline full suite: 352 passed, 1 skipped.
The one skipped test requires a prepared emulator (`--run-device`).

The JSON record contains each pytest node id, its original failure message,
both commands and exit codes, and the test file SHA-256. Failures for invalid
readability distinguish the specific error type or consistency rule from v0
extra-field rejection. Partial-result tests require `unreadable_text` and
verify that observations survive only in the raw record.

| New case | Before | After |
|---|---|---|
| `test_readable_is_checked[clean]` | FAIL | PASS |
| `test_readable_is_checked[finding]` | FAIL | PASS |
| `test_unreadable_text_is_not_checked[partial]` | FAIL | PASS |
| `test_unreadable_text_is_not_checked[unreadable-no-regions]` | FAIL | PASS |
| `test_unreadable_text_is_not_checked[unreadable-with-region]` | FAIL | PASS |
| `test_partial_observations_are_diagnostics_only[partial]` | FAIL | PASS |
| `test_partial_observations_are_diagnostics_only[unreadable]` | FAIL | PASS |
| `test_readability_consistency_is_validated[readable-with-regions]` | FAIL | PASS |
| `test_readability_consistency_is_validated[partial-without-regions]` | FAIL | PASS |
| `test_readability_fields_are_required[readability]` | FAIL | PASS |
| `test_readability_fields_are_required[unreadable_regions]` | FAIL | PASS |
| `test_readability_fields_are_required[readability_reason]` | FAIL | PASS |
| `test_readability_values_are_strict[unknown-readability]` | FAIL | PASS |
| `test_readability_values_are_strict[null-readability]` | FAIL | PASS |
| `test_readability_values_are_strict[null-regions]` | FAIL | PASS |
| `test_readability_values_are_strict[bad-cell]` | FAIL | PASS |
| `test_readability_values_are_strict[numeric-reason]` | FAIL | PASS |
| `test_prompt_carries_labeling_and_readability_rules[scroll]` | FAIL | PASS |
| `test_prompt_carries_labeling_and_readability_rules[ellipsis]` | FAIL | PASS |
| `test_prompt_carries_labeling_and_readability_rules[raw-key]` | FAIL | PASS |
| `test_prompt_carries_labeling_and_readability_rules[placeholder]` | FAIL | PASS |
| `test_prompt_carries_labeling_and_readability_rules[region-centre]` | FAIL | PASS |
| `test_prompt_carries_labeling_and_readability_rules[visible-readability]` | FAIL | PASS |
| `test_v1_versions_are_recordable[prompt]` | FAIL | PASS |
| `test_v1_versions_are_recordable[schema]` | FAIL | PASS |
| `test_v1_versions_are_recordable[wrapper]` | FAIL | PASS |

To reproduce the red run, check out test-only commit `0d53c9a`, run `uv sync`,
then `uv run pytest tests/test_readability.py -vv`. On the final branch the
same command passes. No live requests are made by these tests.
