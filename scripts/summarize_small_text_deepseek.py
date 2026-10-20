"""Publish immutable DeepSeek runs and frozen issue 10 coverage diagnostics."""

import json
from decimal import Decimal
from pathlib import Path

from l10n_checker.reading_metrics import coverage
from l10n_checker.small_text import file_hash, write_json

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "docs/evidence/10/deepseek"


def load(path):
    return json.loads(path.read_text())


def main():
    approval = load(FOLDER / "approval.json")
    plan = load(FOLDER / "request-plan.json")
    ledger = load(ROOT / "data/runs/issue-10-deepseek-ledger.json")
    reference = FOLDER.parent / "reference-amendment-candidate.json"
    if (
        ledger["approval_sha256"] != file_hash(FOLDER / "approval.json")
        or approval["hashes"]["reference"] != file_hash(reference)
        or approval["hashes"]["request_plan"] != file_hash(FOLDER / "request-plan.json")
    ):
        raise ValueError("DeepSeek authorization or inputs changed")
    reviews_path = FOLDER / "result-review.json"
    reviews = (
        {r["run_id"]: r for r in load(reviews_path)["runs"]}
        if reviews_path.exists()
        else {}
    )
    summary = {
        "generation_cap": 12,
        "spending_cap_usd": "0.25",
        "runs": [],
        "pending_or_interrupted": [],
        "comparisons": [],
        "reading_audit": [],
        "halt_reason": ledger.get("halt_reason"),
    }
    outputs = {}
    for entry in ledger["slots"]:
        folder = ROOT / "data/runs" / entry["run_id"]
        if entry["requests_sent"] is None or not (folder / "result.json").exists():
            summary["pending_or_interrupted"].append(entry)
            continue
        run, result = load(folder / "run.json"), load(folder / "result.json")
        request = next(r for r in plan["requests"] if r["slot"] == entry["slot"])
        if (
            run["max_requests"] != 1
            or run["requests_sent"] != entry["requests_sent"]
            or run["requests_sent"] != 1
            or len(run["attempts"]) != 1
            or run["image"]["sha256"] != request["prepared_image_sha256"]
        ):
            raise ValueError("DeepSeek run/input/ledger mismatch")
        row = {
            "slot": entry["slot"],
            "run_id": entry["run_id"],
            "request": request,
            "status": result["status"],
            "reason": result["reason"],
            "requests_sent": run["requests_sent"],
            "settings": run["settings"],
            "model_version": run["model_version"],
            "usage": run["usage"],
            "latency_s": sum(a["latency_s"] for a in run["attempts"]),
            "cost": load(folder / "cost.json"),
            "image_tokens": None,
        }
        summary["runs"].append(row)
        destination = FOLDER.parent / "runs" / entry["run_id"]
        destination.mkdir(exist_ok=True)
        for path in folder.iterdir():
            if path.suffix in (".json", ".txt"):
                (destination / path.name).write_text(
                    path.read_text().replace(str(ROOT) + "/", "")
                )
        output_path = folder / "output.json"
        output = load(output_path) if output_path.exists() else None
        outputs[entry["run_id"]] = output
        if output is not None:
            reviewed = reviews.get(entry["run_id"], {}).get(
                "output_sha256"
            ) == file_hash(output_path)
            summary["reading_audit"].extend(
                {
                    "run_id": entry["run_id"],
                    "index": i,
                    **r,
                    "review": "reviewed" if reviewed else "pending_visual_review",
                }
                for i, r in enumerate(output["readings"])
            )
    summary["confirmed_deepseek_requests_sent"] = sum(
        r["requests_sent"] for r in summary["runs"]
    )
    summary["deepseek_requests_sent"] = (
        None
        if summary["pending_or_interrupted"]
        else summary["confirmed_deepseek_requests_sent"]
    )
    summary["combined_actual_requests_sent"] = (
        41 + summary["confirmed_deepseek_requests_sent"]
    )
    reserved = sum((Decimal(e["reserved_usd"]) for e in ledger["slots"]), Decimal(0))
    summary["reserved_usd"] = str(reserved)
    known = [
        Decimal(e["usage_peak_estimate_usd"])
        for e in ledger["slots"]
        if e.get("usage_peak_estimate_usd") is not None
    ]
    summary["usage_peak_estimate_usd"] = str(sum(known, Decimal(0)))
    summary["usage_off_peak_estimate_usd"] = str(sum(known, Decimal(0)) / 2)
    summary["unknown_usage_reservations_usd"] = str(
        sum(
            (
                Decimal(e["reserved_usd"])
                for e in ledger["slots"]
                if e.get("usage_peak_estimate_usd") is None
            ),
            Decimal(0),
        )
    )
    summary["balance_initial_usd"] = ledger.get("initial_balance_usd")
    summary["balance_last_usd"] = (
        ledger["slots"][-1].get("balance_after_usd") if ledger["slots"] else None
    )
    summary["observed_balance_delta_usd"] = (
        str(
            Decimal(summary["balance_initial_usd"])
            - Decimal(summary["balance_last_usd"])
        )
        if summary["balance_last_usd"] is not None
        else None
    )
    if len(ledger["slots"]) > 12 or reserved > Decimal("0.25"):
        raise ValueError("Approved request or spending cap exceeded")
    for screen in load(reference)["screens"]:
        for option in ("original", "tiles"):
            rows = [
                r
                for r in summary["runs"]
                if r["request"]["image"] == screen["image"]
                and (r["request"]["tile"] == "full") == (option == "original")
            ]
            complete = len(rows) == (1 if option == "original" else 3) and all(
                r["status"] == "checked" for r in rows
            )
            readings = [
                {**reading, "box": r["request"]["box"], "tile": r["request"]["tile"]}
                for r in rows
                if outputs[r["run_id"]]
                for reading in outputs[r["run_id"]]["readings"]
            ]
            measured = coverage(screen["rows"], readings)
            summary["comparisons"].append(
                {
                    "image": screen["image"],
                    "option": option,
                    "status": "checked"
                    if complete
                    else "not_checked"
                    if rows
                    else "not_run",
                    "coverage": measured if complete else None,
                    "partial_evidence": measured if readings and not complete else None,
                    "requests_sent": sum(r["requests_sent"] for r in rows),
                    "latency_s": round(sum(r["latency_s"] for r in rows), 3),
                    "run_ids": [r["run_id"] for r in rows],
                }
            )
    write_json(FOLDER / "ledger.json", ledger)
    write_json(FOLDER / "summary.json", summary)
    print(
        "DeepSeek generation sends:",
        summary["deepseek_requests_sent"],
        "; combined:",
        summary["combined_actual_requests_sent"],
        "; peak cost estimate:",
        summary["usage_peak_estimate_usd"],
    )


if __name__ == "__main__":
    main()
