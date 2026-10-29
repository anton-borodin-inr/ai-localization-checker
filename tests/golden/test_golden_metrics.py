import json
import math
from collections import Counter

from l10n_checker.metrics import score_screen, score_screens


def test_every_expected_field_from_file(golden_case, golden_matches):
    actual = score_screen(golden_matches).to_dict()
    actual["matches"] = [
        [
            golden_case["findings"][pair.finding_index]["id"],
            golden_case["labels"][pair.label_index]["id"],
        ]
        for pair in golden_matches.matches
    ]
    for field, expected in golden_case["expected"].items():
        value = actual[field]
        if expected is None:
            assert value is None, field
        else:
            assert type(value) is type(expected), field
            if isinstance(expected, float):
                assert math.isfinite(value), field
            assert value == expected, field
    # strict JSON would reject NaN/Infinity; None round-trips as null.
    assert json.loads(json.dumps(actual, allow_nan=False)) == actual


def test_dataset_aggregates_file_counts_before_ratios(golden_dataset):
    actual = score_screens(result for _, result in golden_dataset).to_dict()
    expected_counts = {
        field: sum(case["expected"].get(field, 0) for case, _ in golden_dataset)
        for field in (
            "tp",
            "fp",
            "fn",
            "hallucinations",
            "duplicates_collapsed",
            "not_checked_screens",
            "fn_on_not_checked",
        )
    }
    for field, expected in expected_counts.items():
        assert actual[field] == expected, field
    tp, fp, fn = (expected_counts[field] for field in ("tp", "fp", "fn"))
    assert actual["precision"] == tp / (tp + fp)
    assert actual["recall_checked"] == tp / (tp + fn)
    assert actual["recall_all"] == tp / (tp + fn + expected_counts["fn_on_not_checked"])
    # A case with a v1 side makes the whole dataset's confusion undefined.
    assert any(case["expected"]["confusion"] is None for case, _ in golden_dataset)
    assert actual["confusion"] is None
    assert actual["confusion_unavailable_reason"] == (
        "classes are comparable only for schema v2 labels and results; got results v1"
    )


def test_v2_cases_aggregate_the_confusion_table(golden_dataset):
    v2 = [
        (case, result)
        for case, result in golden_dataset
        if case["expected"]["confusion"] is not None
    ]
    actual = score_screens(result for _, result in v2).to_dict()
    expected_confusion = Counter()
    for case, _ in v2:
        for row in case["expected"]["confusion"]:
            expected_confusion[row["label_type"], row["finding_type"]] += row["count"]
    assert actual["confusion"] == [
        {"label_type": label, "finding_type": finding, "count": count}
        for (label, finding), count in sorted(expected_confusion.items())
    ]
    assert actual["confusion_unavailable_reason"] is None


def test_aggregation_is_independent_of_order_and_scales_counts(golden_dataset):
    screens = [result for _, result in golden_dataset]
    metrics = score_screens(screens)
    assert score_screens(reversed(screens)) == metrics
    doubled = score_screens(screens + screens)
    for field in ("precision", "recall_checked", "recall_all"):
        assert getattr(doubled, field) == getattr(metrics, field)
    for field in (
        "tp",
        "fp",
        "fn",
        "hallucinations",
        "duplicates_collapsed",
        "not_checked_screens",
        "fn_on_not_checked",
    ):
        assert getattr(doubled, field) == 2 * getattr(metrics, field)


def test_empty_dataset_is_explicitly_undefined():
    metrics = score_screens([])
    assert metrics.precision is None
    assert metrics.recall_checked is None
    assert metrics.recall_all is None
    assert (
        json.loads(json.dumps(metrics.to_dict(), allow_nan=False)) == metrics.to_dict()
    )
