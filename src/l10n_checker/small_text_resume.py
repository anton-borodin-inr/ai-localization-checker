"""Explicitly authorized issue 10 continuation; the initial ledger stays frozen."""

import argparse
import json
import os
import re
from pathlib import Path

from l10n_checker.capture import REPO_ROOT
from l10n_checker.small_text import (
    EXPERIMENT_SCHEMA,
    PROMPT,
    ReadingOutput,
    approved_request,
    exclusive_ledger,
    file_hash,
    prepare_image,
    write_json,
)
from l10n_checker.vision import RequestBudget, new_run_id, redact, run_check

ADDITIONAL_CAP = 18
TOTAL_CAP = 33
FAILED_SLOTS = (2, 3, 6, 8, 9, 11, 12, 14, 15)


def is_503(result) -> bool:
    return result["status"] == "not_checked" and bool(
        re.match(r"^api_error:\s+(?:\w+Error:\s+)?503\b", result.get("reason") or "")
    )


def load_context(root: Path, slot: int):
    folder = root / "docs/evidence/10"
    authorization_path = folder / "continuation-approval.json"
    authorization = json.loads(authorization_path.read_text())
    if (
        authorization.get("accepted_by") != "Anton"
        or authorization.get("status") != "approved"
        or authorization.get("task_request_cap") != TOTAL_CAP
        or authorization.get("additional_request_cap") != ADDITIONAL_CAP
        or authorization.get("max_new_attempts_per_slot") != 2
        or authorization.get("eligible_slots") != list(FAILED_SLOTS)
        or authorization.get("retry_only_after_503") is not True
    ):
        raise ValueError(
            "Continuation needs Anton's explicit 33-total / 18-new authorization"
        )
    for field, filename in (
        ("reference_sha256", "reference-candidate.json"),
        ("plan_sha256", "request-plan.json"),
        ("initial_ledger_sha256", "ledger.json"),
    ):
        if authorization.get(field) != file_hash(folder / filename):
            raise ValueError("Frozen continuation input changed")
    archived = json.loads((folder / "ledger.json").read_text())
    local_path = root / "data/runs/issue-10-ledger.json"
    if not local_path.exists() or json.loads(local_path.read_text()) != archived:
        raise ValueError("Original local ledger must match the frozen published ledger")
    if (
        len(archived["slots"]) != 15
        or sum(r["requests_sent"] for r in archived["slots"]) != 15
    ):
        raise ValueError("Expected all fifteen original requests in the baseline")
    if slot not in FAILED_SLOTS:
        raise ValueError("Only the nine original 503 slots may be continued")
    parent = next(r for r in archived["slots"] if r["slot"] == slot)
    original = root / "data/runs" / parent["run_id"]
    if not is_503(json.loads((original / "result.json").read_text())):
        raise ValueError("Original slot did not fail with HTTP 503")
    request, source = approved_request(
        root, folder / "request-plan.json", folder / "reference-approval.json", slot
    )
    return authorization_path, parent, request, source


def execute_attempt(
    provider,
    request,
    image,
    runs_dir,
    authorization_hash,
    parent_run_id,
    attempt,
    secrets=(),
):
    """Two new sends at most per eligible slot, with one task-wide lock."""
    if attempt not in (1, 2) or request["slot"] not in FAILED_SLOTS:
        raise ValueError("Invalid continuation slot or attempt")
    ledger_path = runs_dir / "issue-10-continuation-ledger.json"
    with exclusive_ledger(runs_dir / "issue-10-ledger.json"):
        ledger = (
            json.loads(ledger_path.read_text())
            if ledger_path.exists()
            else {
                "authorization_sha256": authorization_hash,
                "baseline_requests_sent": 15,
                "task_request_cap": TOTAL_CAP,
                "additional_request_cap": ADDITIONAL_CAP,
                "attempts": [],
            }
        )
        if ledger["authorization_sha256"] != authorization_hash:
            raise ValueError("Continuation authorization changed")
        if (
            ledger["task_request_cap"] != TOTAL_CAP
            or ledger["additional_request_cap"] != ADDITIONAL_CAP
        ):
            raise ValueError("Continuation ledger cap changed")
        if len(ledger["attempts"]) >= ADDITIONAL_CAP:
            raise ValueError("Continuation request cap reached")
        previous = [r for r in ledger["attempts"] if r["slot"] == request["slot"]]
        if len(previous) != attempt - 1:
            raise ValueError("Attempt was used already or is out of order")
        if previous and (
            previous[-1]["requests_sent"] is None or not is_503(previous[-1])
        ):
            raise ValueError("Second attempt requires a completed first HTTP 503")
        run_id = new_run_id()
        record = {
            "slot": request["slot"],
            "attempt": attempt,
            "run_id": run_id,
            "parent_run_id": parent_run_id,
            "previous_run_id": previous[-1]["run_id"] if previous else parent_run_id,
            "reservation": 1,
            "requests_sent": None,
            "status": "reserved_or_interrupted",
            "reason": None,
        }
        ledger["attempts"].append(record)
        write_json(ledger_path, ledger)
        result, run_dir = run_check(
            provider,
            image,
            runs_dir,
            RequestBudget(1),
            secrets=secrets,
            prompt=PROMPT,
            output_model=ReadingOutput,
            schema_version=EXPERIMENT_SCHEMA,
            run_id=run_id,
        )
        write_json(
            run_dir / "experiment.json",
            {
                **request,
                "continuation_attempt": attempt,
                "parent_run_id": parent_run_id,
                "authorization_sha256": authorization_hash,
            },
        )
        record.update(
            requests_sent=result.metadata["requests_sent"],
            status=result.status,
            reason=result.reason,
        )
        write_json(ledger_path, ledger)
        return result, run_dir


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slot", type=int, choices=FAILED_SLOTS, required=True)
    parser.add_argument("--attempt", type=int, choices=[1, 2], required=True)
    parser.add_argument("--max-requests", type=int, choices=[1], required=True)
    parser.add_argument("--free-tier-key", action="store_true", required=True)
    args = parser.parse_args()
    root = REPO_ROOT
    key = os.environ.get("GEMINI_API_KEY", "")
    try:
        auth_path, parent, request, source = load_context(root, args.slot)
        published_path = root / "docs/evidence/10/continuation-ledger.json"
        local_path = root / "data/runs/issue-10-continuation-ledger.json"
        if published_path.exists():
            published = json.loads(published_path.read_text())
            local = (
                json.loads(local_path.read_text())
                if local_path.exists()
                else {"attempts": []}
            )
            if any(r not in local["attempts"] for r in published["attempts"]):
                raise ValueError("Published continuation reservations cannot be reset")
        image = prepare_image(source, request, root / "data")
        baseline = json.loads(
            (root / "data/runs" / parent["run_id"] / "run.json").read_text()
        )
        if file_hash(image) != baseline["image"]["sha256"]:
            raise ValueError("Continuation image bytes differ from the original call")
        if not key:
            raise ValueError("GEMINI_API_KEY is not set; no request sent")
        from l10n_checker.gemini import make_reading_provider

        provider = make_reading_provider(
            key, request["media_resolution"], ReadingOutput
        )
        if (
            provider.settings != baseline["settings"]
            or provider.model != baseline["model"]
            or provider.sdk_version != baseline["sdk_version"]
        ):
            raise ValueError(
                "Model, SDK or request settings changed since the original call"
            )
        result, directory = execute_attempt(
            provider,
            request,
            image,
            root / "data/runs",
            file_hash(auth_path),
            parent["run_id"],
            args.attempt,
            (key,),
        )
    except Exception as exc:  # noqa: BLE001 - redact every command failure
        print(redact(f"Continuation refused or interrupted: {exc}", (key,)))
        return 1
    print(directory)
    print(result.status, "requests_sent:", result.metadata["requests_sent"])
    return 0 if result.status == "checked" else 2
