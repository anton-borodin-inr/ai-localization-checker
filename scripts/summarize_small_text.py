"""Publish reproducible issue 10 diagnostics from local run records, offline."""

import hashlib
import json
from pathlib import Path

from l10n_checker.reading_metrics import coverage, image_tokens, span_score
from l10n_checker.tiling import region_candidates

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/evidence/10"


def load(path):
    return json.loads(path.read_text())


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main():
    plan = load(EVIDENCE / "request-plan.json")
    reference = load(EVIDENCE / "reference-candidate.json")
    approval = load(EVIDENCE / "reference-approval.json")
    plan_hash = hashlib.sha256(
        (EVIDENCE / "request-plan.json").read_bytes()
    ).hexdigest()
    reference_hash = hashlib.sha256(
        (EVIDENCE / "reference-candidate.json").read_bytes()
    ).hexdigest()
    if (
        approval["plan_sha256"] != plan_hash
        or approval["reference_sha256"] != reference_hash
    ):
        raise ValueError("Approved inputs changed")
    runs_dir = ROOT / "data/runs"
    ledger = load(runs_dir / "issue-10-ledger.json")
    if ledger["plan_sha256"] != plan_hash:
        raise ValueError("Ledger plan changed")
    summary = {
        "reference_sha256": reference_hash,
        "plan_sha256": plan_hash,
        "slots_reserved": len(ledger["slots"]),
        "task_request_cap": 15,
        "runs": [],
        "comparisons": [],
        "findings": [],
        "reading_audit": [],
        "pending_or_interrupted_runs": [],
    }
    outputs = {}
    review_path = EVIDENCE / "result-review.json"
    visual_reviews = (
        {r["run_id"]: r for r in load(review_path)["runs"]}
        if review_path.exists()
        else {}
    )
    for slot in ledger["slots"]:
        directory = runs_dir / slot["run_id"]
        if not (directory / "result.json").exists() or slot["requests_sent"] is None:
            summary["pending_or_interrupted_runs"].append(slot)
            continue
        run = load(directory / "run.json")
        result = load(directory / "result.json")
        request = next(r for r in plan["requests"] if r["slot"] == slot["slot"])
        if run["requests_sent"] != slot["requests_sent"] or run["max_requests"] != 1:
            raise ValueError("Ledger/run request count mismatch")
        if run["settings"]["media_resolution"] != request["media_resolution"]:
            raise ValueError("Run setting differs from plan")
        item = {
            "slot": slot["slot"],
            "run_id": slot["run_id"],
            "request": request,
            "requests_sent": run["requests_sent"],
            "status": result["status"],
            "reason": result["reason"],
            "requested_model": run["model"],
            "model_version": run["model_version"],
            "settings": run["settings"],
            "latency_s": round(sum(a["latency_s"] for a in run["attempts"]), 3),
            "image_tokens": image_tokens(run["usage"]),
            "usage": run["usage"],
            "attempts": run["attempts"],
            "image": run["image"],
        }
        item["image"]["path"] = str(Path(item["image"]["path"]).relative_to(ROOT))
        summary["runs"].append(item)
        public_directory = EVIDENCE / "runs" / slot["run_id"]
        for path in sorted(directory.iterdir()):
            if path.suffix not in (".json", ".txt"):
                continue
            # Run data is already redacted by run_check. Normalize host paths
            # only in these public copies; original local records are untouched.
            text = path.read_text().replace(str(ROOT) + "/", "")
            public_directory.mkdir(parents=True, exist_ok=True)
            (public_directory / path.name).write_text(text, encoding="utf-8")
        output_path = directory / "output.json"
        outputs[slot["run_id"]] = load(output_path) if output_path.exists() else None

    summary["confirmed_requests_sent"] = sum(
        r["requests_sent"] for r in summary["runs"]
    )
    summary["requests_sent"] = (
        None
        if summary["pending_or_interrupted_runs"]
        else summary["confirmed_requests_sent"]
    )
    if summary["confirmed_requests_sent"] > 15 or summary["slots_reserved"] > 15:
        raise ValueError("Task cap exceeded")
    for screen in reference["screens"]:
        for option in ("high", "ultra", "tiles"):
            runs = [
                r
                for r in summary["runs"]
                if r["request"]["image"] == screen["image"]
                and r["request"]["option"] == option
            ]
            expected = 3 if option == "tiles" else 1
            complete = len(runs) == expected and all(
                r["status"] == "checked" for r in runs
            )
            readings = []
            for run in runs:
                output = outputs[run["run_id"]]
                if output is None:
                    continue
                box = run["request"]["box"]
                for reading in output["readings"]:
                    readings.append({**reading, "box": box, "run_id": run["run_id"]})
                    matches = [
                        row["id"]
                        for row in screen["rows"]
                        if span_score(row["text_seen"], reading["text_seen"])[1] >= 0.90
                    ]
                    summary["reading_audit"].append(
                        {
                            "run_id": run["run_id"],
                            "index": len(
                                [
                                    a
                                    for a in summary["reading_audit"]
                                    if a["run_id"] == run["run_id"]
                                ]
                            ),
                            **reading,
                            "reference_units_present": matches,
                            "review": (
                                "reviewed_against_reference_and_screenshot"
                                if visual_reviews.get(run["run_id"], {}).get(
                                    "output_sha256"
                                )
                                == hashlib.sha256(
                                    (
                                        runs_dir / run["run_id"] / "output.json"
                                    ).read_bytes()
                                ).hexdigest()
                                else "pending_visual_review"
                            ),
                        }
                    )
                for index, finding in enumerate(output["findings"]):
                    matched_rows = [
                        row
                        for row in screen["rows"]
                        if span_score(row["text_seen"], finding["text_seen"])[1] >= 0.90
                    ]
                    candidates = region_candidates(
                        finding["region"], tuple(box), (2400, 1080)
                    )
                    expected_regions = sorted({r["region"] for r in matched_rows})
                    assessment = (
                        "unresolved_text"
                        if not matched_rows
                        else "incorrect"
                        if not set(candidates) & set(expected_regions)
                        else "correct"
                        if len(candidates) == 1
                        else "ambiguous_after_crop_mapping"
                    )
                    summary["findings"].append(
                        {
                            "run_id": run["run_id"],
                            "finding_index": index,
                            "image": screen["image"],
                            "option": option,
                            **finding,
                            "local_region": finding["region"],
                            "box": box,
                            "original_region_candidates": candidates,
                            "reference_ids": [r["id"] for r in matched_rows],
                            "reference_regions": expected_regions,
                            "region_assessment": assessment,
                        }
                    )
            diagnostic = coverage(screen["rows"], readings)
            token_values = [r["image_tokens"] for r in runs]
            summary["comparisons"].append(
                {
                    "image": screen["image"],
                    "option": option,
                    "status": "checked" if complete else "not_checked",
                    "run_ids": [r["run_id"] for r in runs],
                    "coverage": diagnostic if complete else None,
                    "partial_evidence": diagnostic
                    if not complete and readings
                    else None,
                    "requests_sent": sum(r["requests_sent"] for r in runs),
                    "latency_s": round(sum(r["latency_s"] for r in runs), 3),
                    "image_tokens": sum(token_values)
                    if len(runs) == expected
                    and all(t is not None for t in token_values)
                    else None,
                }
            )
    save(EVIDENCE / "run-summary.json", summary)
    save(EVIDENCE / "ledger.json", ledger)
    print("Runs:", len(summary["runs"]), "Requests sent:", summary["requests_sent"])
    for row in summary["comparisons"]:
        primary = row["coverage"]["primary"] if row["coverage"] else "unavailable"
        print(Path(row["image"]).stem, row["option"], row["status"], primary)


if __name__ == "__main__":
    main()
