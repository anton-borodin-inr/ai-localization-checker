"""Read Anton's specification without duplicating any expected values."""

import json
from pathlib import Path

import pytest

from l10n_checker.matching import Label, LabelV1, match_screen
from l10n_checker.vision import Finding, FindingV1

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
    label_version = case.get("label_schema_version", 2)
    result_version = case.get("result_schema_version", 2)
    label_model = LabelV1 if label_version == 1 else Label
    finding_model = FindingV1 if result_version == 1 else Finding
    return match_screen(
        labels=[
            label_model(**{k: v for k, v in row.items() if k != "id"})
            for row in case["labels"]
        ],
        findings=[
            finding_model(**{k: v for k, v in row.items() if k != "id"})
            for row in case["findings"]
        ],
        screen_texts=case["screen_texts"],
        status=case["status"],
        label_schema_version=label_version,
        result_schema_version=result_version,
    )
