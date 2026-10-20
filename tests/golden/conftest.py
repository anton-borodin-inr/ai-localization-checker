"""Read Anton's specification without duplicating any expected values."""

import json
from pathlib import Path

import pytest

from l10n_checker.matching import Label, match_screen
from l10n_checker.vision import Finding

CASES = json.loads(
    Path(__file__).with_name("matching_cases.json").read_text(encoding="utf-8")
)["cases"]


@pytest.fixture(params=CASES, ids=lambda case: case["id"])
def golden_case(request):
    return request.param


@pytest.fixture
def golden_matches(golden_case):
    return match_case(golden_case)


@pytest.fixture
def golden_dataset():
    return [(case, match_case(case)) for case in CASES]


def match_case(case):
    return match_screen(
        labels=[
            Label(**{k: v for k, v in row.items() if k != "id"})
            for row in case["labels"]
        ],
        findings=[
            Finding(**{k: v for k, v in row.items() if k != "id"})
            for row in case["findings"]
        ],
        screen_texts=case["screen_texts"],
        status=case["status"],
    )
