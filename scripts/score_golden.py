"""Print one golden case's actual score for an offline manual comparison."""

import argparse
import json
from pathlib import Path

from l10n_checker.matching import Label, LabelV1, match_screen
from l10n_checker.metrics import score_screen
from l10n_checker.vision import Finding, FindingV1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case_id", help="Exact case id in matching_cases.json")
    args = parser.parse_args()
    path = Path(__file__).resolve().parent.parent / "tests/golden/matching_cases.json"
    cases = json.loads(path.read_text(encoding="utf-8"))["cases"]
    case = next((case for case in cases if case["id"] == args.case_id), None)
    if case is None:
        parser.error("unknown case id; see tests/golden/matching_cases.json")
    label_version = case.get("label_schema_version", 2)
    result_version = case.get("result_schema_version", 2)
    label_model = LabelV1 if label_version == 1 else Label
    finding_model = FindingV1 if result_version == 1 else Finding
    result = match_screen(
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
    actual = score_screen(result).to_dict()
    actual["matches"] = [
        [case["findings"][p.finding_index]["id"], case["labels"][p.label_index]["id"]]
        for p in result.matches
    ]
    print(
        json.dumps({"case_id": case["id"], "actual": actual}, indent=2, allow_nan=False)
    )


if __name__ == "__main__":
    main()
