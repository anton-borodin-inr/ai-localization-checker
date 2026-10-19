"""Publish local issue 10 evidence without rewriting the Gemini snapshots."""

import json
from pathlib import Path

from l10n_checker.reading_metrics import coverage, span_score
from l10n_checker.small_text import file_hash, write_json
from l10n_checker.tiling import region_candidates

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "docs/evidence/10/local-model"


def load(path):
    return json.loads(path.read_text())


def main():
    plan = load(FOLDER / "request-plan.json")
    approval_path = FOLDER / "approval.json"
    approval = load(approval_path)
    reference_path = FOLDER.parent / "reference-amendment-candidate.json"
    if (
        approval["status"] != "approved"
        or approval["accepted_by"] != "Anton"
        or approval["request_plan_sha256"] != file_hash(FOLDER / "request-plan.json")
        or approval["reference_sha256"] != file_hash(reference_path)
    ):
        raise ValueError("Local approved inputs changed")
    reference = load(reference_path)
    ledger = load(ROOT / "data/runs/issue-10-local-ledger.json")
    if ledger["approval_sha256"] != file_hash(approval_path):
        raise ValueError("Local authorization changed")
    reviews_path = FOLDER / "result-review.json"
    reviews = (
        {r["run_id"]: r for r in load(reviews_path)["runs"]}
        if reviews_path.exists()
        else {}
    )
    cap = ledger.get("extended_local_cap", 12)
    if cap == 13 and ledger.get("extension_sha256") != file_hash(
        FOLDER / "timeout-extension.json"
    ):
        raise ValueError("Local timeout extension changed")
    summary = {
        "local_cap": cap,
        "gemini_requests_sent": 27,
        "reservations": len(ledger["slots"]),
        "pending_or_interrupted": [],
        "runs": [],
        "comparisons": [],
        "reading_audit": [],
        "findings": [],
    }
    outputs = {}
    for record in ledger["slots"]:
        directory = ROOT / "data/runs" / record["run_id"]
        if record["requests_sent"] is None or not (directory / "result.json").exists():
            summary["pending_or_interrupted"].append(record)
            continue
        run, result = load(directory / "run.json"), load(directory / "result.json")
        request = next(r for r in plan["requests"] if r["slot"] == record["slot"])
        if (
            run["requests_sent"] != record["requests_sent"]
            or run["requests_sent"] != 1
            or run["max_requests"] != 1
            or len(run["attempts"]) != 1
            or run["image"]["sha256"] != request["prepared_image_sha256"]
        ):
            raise ValueError("Local run/ledger/input mismatch")
        row = {
            "slot": record["slot"],
            "attempt": record.get("attempt", 1),
            "run_id": record["run_id"],
            "request": request,
            "status": result["status"],
            "reason": result["reason"],
            "requests_sent": run["requests_sent"],
            "requested_model": run["model"],
            "model_version": run["model_version"],
            "settings": run["settings"],
            "usage": run["usage"],
            "image_tokens": None,
            "latency_s": round(sum(a["latency_s"] for a in run["attempts"]), 3),
        }
        summary["runs"].append(row)
        destination = FOLDER.parent / "runs" / record["run_id"]
        destination.mkdir(parents=True, exist_ok=True)
        for path in directory.iterdir():
            if path.suffix in (".json", ".txt"):
                (destination / path.name).write_text(
                    path.read_text().replace(str(ROOT) + "/", ""), encoding="utf-8"
                )
        output_path = directory / "output.json"
        output = load(output_path) if output_path.exists() else None
        outputs[record["run_id"]] = output
        if output is None:
            continue
        screen = next(s for s in reference["screens"] if s["image"] == request["image"])
        reviewed = reviews.get(record["run_id"], {}).get("output_sha256") == file_hash(
            output_path
        )
        for index, reading in enumerate(output["readings"]):
            summary["reading_audit"].append(
                {
                    "run_id": record["run_id"],
                    "index": index,
                    **reading,
                    "review": "reviewed" if reviewed else "pending_visual_review",
                }
            )
        for index, finding in enumerate(output["findings"]):
            matched = [
                r
                for r in screen["rows"]
                if span_score(r["text_seen"], finding["text_seen"])[1] >= 0.90
            ]
            summary["findings"].append(
                {
                    "run_id": record["run_id"],
                    "finding_index": index,
                    **finding,
                    "image": screen["image"],
                    "box": request["box"],
                    "original_region_candidates": region_candidates(
                        finding["region"], tuple(request["box"]), (2400, 1080)
                    ),
                    "reference_ids": [r["id"] for r in matched],
                    "reference_regions": sorted({r["region"] for r in matched}),
                }
            )
    summary["confirmed_local_requests_sent"] = sum(
        r["requests_sent"] for r in summary["runs"]
    )
    summary["local_requests_sent"] = (
        None
        if summary["pending_or_interrupted"]
        else summary["confirmed_local_requests_sent"]
    )
    summary["combined_actual_requests_sent"] = (
        27 + summary["confirmed_local_requests_sent"]
    )
    if (
        summary["reservations"] > cap
        or summary["combined_actual_requests_sent"] > 27 + cap
    ):
        raise ValueError("Local/combined budget exceeded")
    selected = {}
    for run in summary["runs"]:
        if run["slot"] not in selected or selected[run["slot"]]["status"] != "checked":
            selected[run["slot"]] = run
    summary["selected_runs"] = {str(slot): r["run_id"] for slot, r in selected.items()}
    for screen in reference["screens"]:
        for option in ("original", "tiles"):
            runs = [
                r
                for r in summary["runs"]
                if r["request"]["image"] == screen["image"]
                and r["request"]["option"] == option
            ]
            chosen = [
                r
                for r in selected.values()
                if r["request"]["image"] == screen["image"]
                and r["request"]["option"] == option
            ]
            complete = len(chosen) == (1 if option == "original" else 3) and all(
                r["status"] == "checked" for r in chosen
            )
            readings = []
            for run in chosen:
                output = outputs[run["run_id"]]
                if output:
                    readings.extend(
                        {**r, "box": run["request"]["box"], "run_id": run["run_id"]}
                        for r in output["readings"]
                    )
            measured = coverage(screen["rows"], readings)
            summary["comparisons"].append(
                {
                    "image": screen["image"],
                    "option": option,
                    "status": "checked"
                    if complete
                    else "not_checked"
                    if runs
                    else "not_run",
                    "coverage": measured if complete else None,
                    "partial_evidence": measured if readings and not complete else None,
                    "image_tokens": None,
                    "latency_all_attempts_s": round(
                        sum(r["latency_s"] for r in runs), 3
                    ),
                    "requests_sent": sum(r["requests_sent"] for r in runs),
                    "run_ids": [r["run_id"] for r in runs],
                    "selected_run_ids": [r["run_id"] for r in chosen],
                    "latency_selected_s": round(sum(r["latency_s"] for r in chosen), 3)
                    if complete
                    else None,
                }
            )
    write_json(FOLDER / "ledger.json", ledger)
    write_json(FOLDER / "summary.json", summary)
    print(
        "Local:",
        summary["local_requests_sent"],
        f"/ {cap}; combined actual:",
        summary["combined_actual_requests_sent"],
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
