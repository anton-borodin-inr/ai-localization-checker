"""Re-run the recommended, already registered E2 on the labelled trio only."""

import argparse
import json
from pathlib import Path

from l10n_checker.baseline import run_baseline
from l10n_checker.baseline_cli import output_directory
from l10n_checker.metrics import score_screens
from l10n_checker.ocr import ConfiguredOcr
from l10n_checker.ocr_experiment import (
    evaluate,
    read,
    validated_protocol,
    write,
)
from l10n_checker.slice import REFERENCE_SOURCE
from l10n_checker.vision import new_run_id


def recheck(root: Path, fork: Path, runs_dir: Path, model_dir: Path) -> dict:
    protocol = validated_protocol(root)
    config = next(c for c in protocol["grid"] if c["id"] == "E2")
    images = [image for image in protocol["images"] if image["scope"] == "labelled"]
    reference = read(root / REFERENCE_SOURCE)
    directory = runs_dir / new_run_id()
    directory.mkdir(parents=True, exist_ok=False)
    engine = ConfiguredOcr(config["engine"], config["preprocess"], model_dir)
    rows, matches = [], []
    try:
        for image in images:
            _, record = run_baseline(
                root / image["path"],
                root / "docs/evidence/8/pair-manifest.json",
                root / "docs/evidence/12/tech-picker.json",
                fork,
                directory / "runs",
                engine,
            )
            row, matched = evaluate(
                root,
                {
                    "configuration": "E2",
                    "pass": 1,
                    "scope": "labelled",
                    "image": image["path"],
                    "language": image["language"],
                    "record": str(record.relative_to(root)),
                },
                reference,
            )
            rows.append(row)
            matches.append(matched)
    finally:
        engine.close()
    complete = all(row["coverage"] is not None for row in rows)
    summary = {
        "configuration": "E2",
        "image_operations": len(rows),
        "metrics": score_screens(matches).to_dict(),
        "clean_fp": sum(
            row["metrics"]["fp"] for row in rows if "__clean__" in row["image"]
        ),
        "primary_exact": sum(row["coverage"]["primary"]["exact_count"] for row in rows)
        if complete
        else None,
        "primary_fuzzy": sum(row["coverage"]["primary"]["fuzzy_count"] for row in rows)
        if complete
        else None,
        "primary_reference_count": sum(
            row["coverage"]["primary"]["reference_count"] for row in rows
        )
        if complete
        else None,
        "provider_requests": 0,
        "rows": rows,
        "summary": str((directory / "summary.json").relative_to(root)),
    }
    write(directory / "summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--unciv-fork", type=Path, required=True)
    parser.add_argument("--runs-dir", type=Path, default=Path("data/issue-48-rechecks"))
    parser.add_argument("--model-dir", type=Path, default=Path("data/ocr-models"))
    args = parser.parse_args()
    summary = recheck(
        Path.cwd().resolve(),
        args.unciv_fork.resolve(),
        output_directory(args.runs_dir),
        args.model_dir.resolve(),
    )
    print(json.dumps({k: v for k, v in summary.items() if k != "rows"}, indent=2))


if __name__ == "__main__":
    main()
