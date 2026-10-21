import json
from pathlib import Path

import pytest

from l10n_checker.reading_metrics import coverage, span_score

GOLDEN = json.loads(
    (Path(__file__).parent / "golden/small_text_cases.json").read_text()
)


@pytest.mark.parametrize("reference,observed,exact,fuzzy", GOLDEN["cases"])
def test_Anton_confirmed_text_comparison(reference, observed, exact, fuzzy):
    actual_exact, score = span_score(reference, observed)
    assert actual_exact == exact
    assert (score >= 0.90) == fuzzy


def test_overlap_does_not_inflate_coverage_or_cover_another_location():
    rows = [
        {
            "id": "tree",
            "section": "tree",
            "text_seen": "Archery",
            "region": "center",
            "primary_denominator": True,
        }
    ]
    reading = {"text_seen": "Archery", "region": "center", "box": [0, 0, 2400, 1080]}
    result = coverage(rows, [reading, reading])
    assert result["primary"]["reference_count"] == 1
    assert result["primary"]["exact_count"] == 1
    wrong_location = {
        **reading,
        "region": "bottom-right",
        "text_seen": "Research Archery",
    }
    button = {
        **rows[0],
        "id": "button",
        "text_seen": "Research Archery",
        "region": "bottom-right",
    }
    result = coverage([*rows, button], [wrong_location])
    assert result["matches"][0]["exact"] is False
    assert result["matches"][1]["exact"] is True
    # A unique transcribed label is still read correctly when its region is wrong.
    assert (
        coverage(rows, [{**reading, "region": "top-right"}])["primary"]["exact_count"]
        == 1
    )
