"""Twelve local inputs and one explicitly authorized repeat; cloud stays frozen."""

import argparse
import hashlib
import json

from l10n_checker.capture import REPO_ROOT
from l10n_checker.local_model import ENDPOINT, MODEL, LocalVisionProvider
from l10n_checker.small_text import (
    EXPERIMENT_SCHEMA,
    PROMPT,
    ReadingOutput,
    exclusive_ledger,
    file_hash,
    prepare_image,
    write_json,
)
from l10n_checker.vision import RequestBudget, new_run_id, run_check

LOCAL_CAP = 12


def published_reservations_present(published, current):
    """Preserve reservations while allowing pending records to finish."""
    for old in published["slots"]:
        same = next(
            (
                new
                for new in current["slots"]
                if new["slot"] == old["slot"]
                and new.get("attempt", 1) == old.get("attempt", 1)
            ),
            None,
        )
        if same is None or any(
            same.get(k) != old.get(k) for k in ("run_id", "reservation")
        ):
            return False
        if old["requests_sent"] is not None and any(
            same.get(k) != old.get(k) for k in ("requests_sent", "status")
        ):
            return False
    return True


def load_context(root, slot):
    folder = root / "docs/evidence/10/local-model"
    plan_path = folder / "request-plan.json"
    approval_path = folder / "approval.json"
    plan, approval = (json.loads(p.read_text()) for p in (plan_path, approval_path))
    if (
        approval.get("accepted_by") != "Anton"
        or approval.get("status") != "approved"
        or approval.get("local_cap") != LOCAL_CAP
        or approval.get("combined_actual_cap") != 39
        or approval.get("retries") != 0
    ):
        raise ValueError("Local comparison needs Anton's 12-send authorization")
    for field, path in (
        ("request_plan_sha256", plan_path),
        ("plan_sha256", folder / "plan.md"),
        ("reference_sha256", folder.parent / "reference-amendment-candidate.json"),
        (
            "reference_approval_sha256",
            folder.parent / "reference-amendment-approval.json",
        ),
        ("metadata_sha256", folder / "models-before.json"),
    ):
        if approval.get(field) != file_hash(path):
            raise ValueError("Approved local input changed")
    if (
        plan["local_cap"] != LOCAL_CAP
        or plan["baseline_gemini_requests"] != 27
        or plan["combined_actual_cap"] != 39
        or plan["endpoint"] != ENDPOINT
        or plan["model"] != MODEL
        or plan["retries"] != 0
        or len(plan["requests"]) != LOCAL_CAP
        or {r["slot"] for r in plan["requests"]} != set(range(1, LOCAL_CAP + 1))
        or any(r["max_requests"] != 1 for r in plan["requests"])
    ):
        raise ValueError("Local plan differs from the fixed allocation")
    cloud = json.loads((folder.parent / "combined-summary.json").read_text())
    if cloud["requests_sent"] != 27:
        raise ValueError("Expected 27 frozen Gemini sends")
    request = next(r for r in plan["requests"] if r["slot"] == slot)
    source = (root / request["image"]).resolve()
    if not source.is_relative_to((root / "docs/evidence/8/final").resolve()):
        raise ValueError("Only approved issue 8 final images are allowed")
    if file_hash(source) != request["image_sha256"]:
        raise ValueError("Original image changed")
    if plan["prompt_sha256"] != hashlib.sha256(PROMPT.encode()).hexdigest():
        raise ValueError("Frozen prompt changed")
    return plan, file_hash(approval_path), request, source


def load_extension(root):
    folder = root / "docs/evidence/10/local-model"
    path = folder / "timeout-extension.json"
    if not path.exists():
        return None
    extension = json.loads(path.read_text())
    plan = extension["plan"]
    original = root / "data/runs" / plan["initial_timeout_run_id"] / "result.json"
    if (
        extension["accepted_by"] != "Anton"
        or extension["status"] != "approved"
        or plan["local_cap"] != 13
        or plan["combined_actual_cap"] != 40
        or plan["gemini_requests_sent"] != 27
        or plan["timeout_s"] != 400
        or plan["extra_attempt"] != {"slot": 1, "attempt": 2}
        or plan["remaining_slots"] != list(range(2, 13))
        or plan["retries_after_this"] != 0
        or plan["base_approval_sha256"] != file_hash(folder / "approval.json")
        or plan["base_request_plan_sha256"] != file_hash(folder / "request-plan.json")
        or plan["initial_result_sha256"] != file_hash(original)
    ):
        raise ValueError("Local timeout/cap extension needs matching Anton approval")
    result = json.loads(original.read_text())
    if result["status"] != "not_checked" or not result["reason"].startswith("timeout:"):
        raise ValueError(
            "Only the initial timed-out input may receive a second attempt"
        )
    return file_hash(path)


def load_nightly_extension(root):
    folder = root / "docs/evidence/10/local-model"
    path = folder / "nightly-extension.json"
    if not path.exists():
        return None
    extension = json.loads(path.read_text())
    plan = extension["plan"]
    if (
        extension["accepted_by"] != "Anton"
        or extension["status"] != "approved"
        or plan["local_cap"] != 14
        or plan["combined_actual_cap"] != 41
        or plan["gemini_requests_sent"] != 27
        or plan["timeout_s"] != 1800
        or plan["extra_attempt"] != {"slot": 1, "attempt": 3}
        or plan["further_retries"] != 0
        or plan["base_approval_sha256"] != file_hash(folder / "approval.json")
        or plan["previous_extension_sha256"]
        != file_hash(folder / "timeout-extension.json")
        or len(plan["prior_timeout_results"]) != 2
    ):
        raise ValueError("Nightly timeout/cap needs matching Anton approval")
    for run_id, digest in plan["prior_timeout_results"].items():
        path_to_result = root / "data/runs" / run_id / "result.json"
        if file_hash(path_to_result) != digest:
            raise ValueError("Prior timeout changed")
        result = json.loads(path_to_result.read_text())
        if result["status"] != "not_checked" or not result["reason"].startswith(
            "timeout:"
        ):
            raise ValueError("Third attempt requires both prior timeouts")
    return file_hash(path)


def execute_local(
    provider,
    request,
    image,
    runs_dir,
    approval_hash,
    published=None,
    *,
    attempt=1,
    extension_hash=None,
    nightly_hash=None,
):
    path = runs_dir / "issue-10-local-ledger.json"
    with exclusive_ledger(runs_dir / "issue-10-ledger.json"):
        ledger = (
            json.loads(path.read_text())
            if path.exists()
            else {"approval_sha256": approval_hash, "local_cap": LOCAL_CAP, "slots": []}
        )
        if (
            ledger["approval_sha256"] != approval_hash
            or ledger["local_cap"] != LOCAL_CAP
        ):
            raise ValueError("Local ledger approval changed")
        if published and not published_reservations_present(published, ledger):
            raise ValueError("Published local reservations cannot be reset")
        if ledger.get("nightly_extension_sha256") not in (None, nightly_hash):
            raise ValueError("Nightly extension changed or was removed")
        if nightly_hash and not extension_hash:
            raise ValueError("Nightly extension requires the prior authorization")
        if ledger.get("extension_sha256") not in (None, extension_hash):
            raise ValueError("Local extension changed or was removed")
        previous = [s for s in ledger["slots"] if s["slot"] == request["slot"]]
        if attempt == 1 and previous:
            raise ValueError("Slot already reserved; no retry")
        if attempt == 2:
            if not extension_hash or request["slot"] != 1 or len(previous) != 1:
                raise ValueError(
                    "Only one explicitly approved second attempt of slot 1"
                )
            result_path = runs_dir / previous[0]["run_id"] / "result.json"
            if previous[0]["requests_sent"] != 1 or not result_path.exists():
                raise ValueError("An interrupted slot cannot be retried")
            first = json.loads(result_path.read_text())
            if first["status"] != "not_checked" or not first["reason"].startswith(
                "timeout:"
            ):
                raise ValueError("Second local attempt requires the initial timeout")
        elif attempt == 3:
            if not nightly_hash or request["slot"] != 1 or len(previous) != 2:
                raise ValueError("Only one explicitly approved third attempt of slot 1")
            for entry in previous:
                result_path = runs_dir / entry["run_id"] / "result.json"
                if entry["requests_sent"] != 1 or not result_path.exists():
                    raise ValueError("An interrupted slot cannot be retried")
                first = json.loads(result_path.read_text())
                if first["status"] != "not_checked" or not first["reason"].startswith(
                    "timeout:"
                ):
                    raise ValueError("Third attempt requires both prior timeouts")
        elif attempt != 1:
            raise ValueError("Invalid local attempt")
        cap = 14 if nightly_hash else 13 if extension_hash else LOCAL_CAP
        if not 1 <= request["slot"] <= LOCAL_CAP or len(ledger["slots"]) >= cap:
            raise ValueError("Local request cap reached")
        if extension_hash:
            ledger["extension_sha256"] = extension_hash
            ledger["extended_local_cap"] = cap
        if nightly_hash:
            ledger["nightly_extension_sha256"] = nightly_hash
        run_id = new_run_id()
        record = {
            "slot": request["slot"],
            "run_id": run_id,
            "reservation": 1,
            "requests_sent": None,
            "status": "reserved_or_interrupted",
            "attempt": attempt,
        }
        ledger["slots"].append(record)
        write_json(path, ledger)
        result, directory = run_check(
            provider,
            image,
            runs_dir,
            RequestBudget(1),
            prompt=PROMPT,
            output_model=ReadingOutput,
            schema_version=EXPERIMENT_SCHEMA,
            run_id=run_id,
        )
        write_json(
            directory / "experiment.json",
            {
                **request,
                "approval_sha256": approval_hash,
                "attempt": attempt,
                "extension_sha256": extension_hash,
                "nightly_extension_sha256": nightly_hash,
            },
        )
        record.update(
            requests_sent=result.metadata["requests_sent"], status=result.status
        )
        write_json(path, ledger)
        return result, directory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--slot", type=int, choices=range(1, LOCAL_CAP + 1), required=True
    )
    parser.add_argument("--max-requests", type=int, choices=[1], required=True)
    parser.add_argument("--attempt", type=int, choices=[1, 2, 3], default=1)
    args = parser.parse_args()
    root = REPO_ROOT
    try:
        plan, approval_hash, request, source = load_context(root, args.slot)
        extension_hash = load_extension(root)
        nightly_hash = load_nightly_extension(root)
        if args.attempt == 3 and not nightly_hash:
            raise ValueError("Third attempt requires explicit nightly authorization")
        if args.attempt == 2 and not extension_hash:
            raise ValueError("Second attempt requires the explicit timeout extension")
        image = prepare_image(source, request, root / "data")
        if file_hash(image) != request["prepared_image_sha256"]:
            raise ValueError("Prepared image differs from Gemini input")
        folder = root / "docs/evidence/10/local-model"
        metadata = json.loads((folder / "models-before.json").read_text())
        model = next(m for m in metadata["data"] if m["id"] == MODEL)
        provider = LocalVisionProvider(
            plan["settings"]["response_schema"],
            model,
            timeout_s=1800
            if nightly_hash
            else 400
            if extension_hash
            else plan["settings"]["timeout_s"],
        )
        for name in ("temperature", "max_tokens", "stream"):
            if provider.settings[name] != plan["settings"][name]:
                raise ValueError("Local provider settings differ from approved plan")
        published_path = folder / "ledger.json"
        result, directory = execute_local(
            provider,
            request,
            image,
            root / "data/runs",
            approval_hash,
            json.loads(published_path.read_text()) if published_path.exists() else None,
            attempt=args.attempt,
            extension_hash=extension_hash,
            nightly_hash=nightly_hash,
        )
    except Exception as exc:  # noqa: BLE001 - report refusals without loading secrets
        print(f"Local experiment refused or interrupted: {exc}")
        return 1
    print(directory)
    print(result.status, "requests_sent:", result.metadata["requests_sent"])
    return 0 if result.status == "checked" else 2
