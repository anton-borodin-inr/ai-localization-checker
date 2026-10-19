"""Aggregate the authorized continuation without rewriting initial evidence."""

import hashlib
import json
from pathlib import Path

from l10n_checker.reading_metrics import coverage, image_tokens, span_score
from l10n_checker.small_text_resume import ADDITIONAL_CAP, TOTAL_CAP
from l10n_checker.tiling import region_candidates

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "docs/evidence/10"


def load(path):
    return json.loads(path.read_text())


def save(path, value):
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def choose_runs(runs):
    """First validated response per original slot; never choose by quality score."""
    chosen = {}
    for run in runs:
        current = chosen.get(run["slot"])
        if current is None or current["status"] != "checked":
            chosen[run["slot"]] = run
    return chosen


def compare(reference, runs, chosen, outputs):
    comparisons = []
    for screen in reference["screens"]:
        for option in ("high", "ultra", "tiles"):
            attempts = [
                r
                for r in runs
                if r["request"]["image"] == screen["image"]
                and r["request"]["option"] == option
            ]
            selected = [
                r
                for r in chosen.values()
                if r["request"]["image"] == screen["image"]
                and r["request"]["option"] == option
            ]
            complete = len(selected) == (3 if option == "tiles" else 1) and all(
                r["status"] == "checked" for r in selected
            )
            readings = []
            for run in selected:
                output = outputs[run["run_id"]]
                if output:
                    readings.extend(
                        {**r, "box": run["request"]["box"], "run_id": run["run_id"]}
                        for r in output["readings"]
                    )
            diagnostic = coverage(screen["rows"], readings)
            tokens = [r["image_tokens"] for r in selected]
            comparisons.append(
                {
                    "image": screen["image"],
                    "option": option,
                    "status": "checked" if complete else "not_checked",
                    "selected_run_ids": [r["run_id"] for r in selected],
                    "coverage": diagnostic if complete else None,
                    "partial_evidence": diagnostic
                    if readings and not complete
                    else None,
                    "image_tokens_selected": sum(tokens)
                    if complete and all(t is not None for t in tokens)
                    else None,
                    "latency_selected_s": round(
                        sum(r["latency_s"] for r in selected), 3
                    ),
                    "latency_all_attempts_s": round(
                        sum(r["latency_s"] for r in attempts), 3
                    ),
                    "requests_sent_all_attempts": sum(
                        r["requests_sent"] for r in attempts
                    ),
                }
            )
    return comparisons


def amended_reference(original):
    path = FOLDER / "reference-amendment-candidate.json"
    approval = load(FOLDER / "reference-amendment-approval.json")
    if (
        approval.get("accepted_by") != "Anton"
        or approval.get("status") != "confirmed"
        or approval.get("reference_sha256")
        != hashlib.sha256(path.read_bytes()).hexdigest()
        or approval.get("amends_reference_sha256")
        != hashlib.sha256(
            (FOLDER / "reference-candidate.json").read_bytes()
        ).hexdigest()
    ):
        raise ValueError("Reference amendment needs a hash-bound Anton confirmation")
    amended = load(path)
    if amended["amends_reference_sha256"] != approval["amends_reference_sha256"]:
        raise ValueError("Reference amendment does not identify its original")
    if amended["builds"] != original["builds"]:
        raise ValueError("Reference amendment changed build provenance")
    return amended


def main():
    approval_path = FOLDER / "continuation-approval.json"
    approval = load(approval_path)
    for field, name in (
        ("reference_sha256", "reference-candidate.json"),
        ("plan_sha256", "request-plan.json"),
        ("initial_ledger_sha256", "ledger.json"),
    ):
        if hashlib.sha256((FOLDER / name).read_bytes()).hexdigest() != approval[field]:
            raise ValueError("Frozen inputs changed")
    initial = load(FOLDER / "run-summary.json")
    original_reference = load(FOLDER / "reference-candidate.json")
    reference = amended_reference(original_reference)
    plan = load(FOLDER / "request-plan.json")
    ledger = load(ROOT / "data/runs/issue-10-continuation-ledger.json")
    if (
        ledger["authorization_sha256"]
        != hashlib.sha256(approval_path.read_bytes()).hexdigest()
    ):
        raise ValueError("Continuation approval changed")
    if len(ledger["attempts"]) > ADDITIONAL_CAP:
        raise ValueError("Continuation cap exceeded")
    reviews = {}
    for name in ("result-review.json", "continuation-result-review.json"):
        path = FOLDER / name
        if path.exists():
            reviews.update({r["run_id"]: r for r in load(path)["runs"]})
    summary = {
        "reference_version": "Anton-confirmed post-call amendment: injected 18 to 20 units",
        "reference_sha256": hashlib.sha256(
            (FOLDER / "reference-amendment-candidate.json").read_bytes()
        ).hexdigest(),
        "original_reference_sha256": approval["reference_sha256"],
        "total_cap": TOTAL_CAP,
        "additional_cap": ADDITIONAL_CAP,
        "baseline_requests_sent": 15,
        "new_reservations": len(ledger["attempts"]),
        "pending_or_interrupted": [],
        "runs": initial["runs"].copy(),
        "comparisons": [],
        "reading_audit": [],
        "findings": [],
    }
    for record in ledger["attempts"]:
        directory = ROOT / "data/runs" / record["run_id"]
        if record["requests_sent"] is None or not (directory / "result.json").exists():
            summary["pending_or_interrupted"].append(record)
            continue
        run, result = load(directory / "run.json"), load(directory / "result.json")
        request = next(r for r in plan["requests"] if r["slot"] == record["slot"])
        if run["requests_sent"] != record["requests_sent"] or run["max_requests"] != 1:
            raise ValueError("Continuation run/ledger count mismatch")
        summary["runs"].append(
            {
                "slot": record["slot"],
                "continuation_attempt": record["attempt"],
                "run_id": record["run_id"],
                "parent_run_id": record["parent_run_id"],
                "request": request,
                "status": result["status"],
                "reason": result["reason"],
                "requests_sent": run["requests_sent"],
                "requested_model": run["model"],
                "model_version": run["model_version"],
                "settings": run["settings"],
                "usage": run["usage"],
                "image_tokens": image_tokens(run["usage"]),
                "latency_s": round(sum(a["latency_s"] for a in run["attempts"]), 3),
            }
        )
        destination = FOLDER / "runs" / record["run_id"]
        destination.mkdir(parents=True, exist_ok=True)
        for path in directory.iterdir():
            if path.suffix in (".json", ".txt"):
                (destination / path.name).write_text(
                    path.read_text().replace(str(ROOT) + "/", ""), encoding="utf-8"
                )
    summary["confirmed_requests_sent"] = sum(
        r["requests_sent"] for r in summary["runs"]
    )
    summary["requests_sent"] = (
        None
        if summary["pending_or_interrupted"]
        else summary["confirmed_requests_sent"]
    )
    if summary["confirmed_requests_sent"] > TOTAL_CAP:
        raise ValueError("Combined cap exceeded")
    chosen = choose_runs(summary["runs"])
    summary["selected_runs"] = {
        str(slot): run["run_id"] for slot, run in chosen.items()
    }
    outputs = {}
    for run in summary["runs"]:
        path = ROOT / "data/runs" / run["run_id"] / "output.json"
        output = load(path) if path.exists() else None
        outputs[run["run_id"]] = output
        if output is None:
            continue
        screen = next(
            s for s in reference["screens"] if s["image"] == run["request"]["image"]
        )
        box = run["request"]["box"]
        reviewed = (
            reviews.get(run["run_id"], {}).get("output_sha256")
            == hashlib.sha256(path.read_bytes()).hexdigest()
        )
        for index, reading in enumerate(output["readings"]):
            summary["reading_audit"].append(
                {
                    "run_id": run["run_id"],
                    "index": index,
                    **reading,
                    "review": "reviewed" if reviewed else "pending_visual_review",
                    "reference_units_present": [
                        r["id"]
                        for r in screen["rows"]
                        if span_score(r["text_seen"], reading["text_seen"])[1] >= 0.90
                    ],
                }
            )
        for index, finding in enumerate(output["findings"]):
            candidates = region_candidates(finding["region"], tuple(box), (2400, 1080))
            matched = [
                r
                for r in screen["rows"]
                if span_score(r["text_seen"], finding["text_seen"])[1] >= 0.90
            ]
            summary["findings"].append(
                {
                    "run_id": run["run_id"],
                    "finding_index": index,
                    **finding,
                    "image": screen["image"],
                    "option": run["request"]["option"],
                    "box": box,
                    "original_region_candidates": candidates,
                    "reference_ids": [r["id"] for r in matched],
                    "reference_regions": sorted({r["region"] for r in matched}),
                    "selected": chosen[run["slot"]]["run_id"] == run["run_id"],
                }
            )
    summary["comparisons"] = compare(reference, summary["runs"], chosen, outputs)
    summary["original_reference_comparisons"] = compare(
        original_reference, summary["runs"], chosen, outputs
    )
    save(FOLDER / "continuation-ledger.json", ledger)
    save(FOLDER / "combined-summary.json", summary)
    print(
        "Combined confirmed requests:",
        summary["confirmed_requests_sent"],
        "/",
        TOTAL_CAP,
    )
    for row in summary["comparisons"]:
        print(
            Path(row["image"]).stem,
            row["option"],
            row["status"],
            row["coverage"]["primary"] if row["coverage"] else "unavailable",
        )


if __name__ == "__main__":
    main()
