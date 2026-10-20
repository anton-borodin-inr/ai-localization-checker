"""Approved paid issue 10 comparison: twelve sends, no retries, USD 0.25 cap."""

import argparse
import json
import os
from datetime import UTC, datetime
from decimal import Decimal

from l10n_checker.capture import REPO_ROOT
from l10n_checker.deepseek import (
    CAP,
    MODEL,
    RESERVATION,
    SCHEMA_VERSION,
    DeepSeekProvider,
    format_prompt,
    input_bound,
    peak_cost,
)
from l10n_checker.small_text import (
    ReadingOutput,
    exclusive_ledger,
    file_hash,
    prepare_image,
    write_json,
)
from l10n_checker.small_text_local import published_reservations_present
from l10n_checker.vision import ProviderError, RequestBudget, new_run_id, run_check


def load_context(root, slot):
    folder = root / "docs/evidence/10/deepseek"
    approval = json.loads((folder / "approval.json").read_text())
    plan = json.loads((folder / "request-plan.json").read_text())
    if any(
        approval.get(k) != v
        for k, v in {
            "accepted_by": "Anton",
            "status": "approved",
            "max_requests": 12,
            "max_usd": "0.25",
            "retries": 0,
            "combined_actual_cap": 53,
        }.items()
    ):
        raise ValueError("Matching paid DeepSeek approval required")
    for name, path in {
        "plan": folder / "plan.md",
        "request_plan": folder / "request-plan.json",
        "prompt": folder / "prompt.txt",
        "schema": folder / "schema.json",
        "reference": folder.parent / "reference-amendment-candidate.json",
        "reference_approval": folder.parent / "reference-amendment-approval.json",
        "cloud_summary": folder.parent / "combined-summary.json",
        "local_summary": folder.parent / "local-model/summary.json",
    }.items():
        if approval["hashes"].get(name) != file_hash(path):
            raise ValueError("Approved DeepSeek inputs changed")
    schema = json.loads((folder / "schema.json").read_text())
    if schema != ReadingOutput.model_json_schema():
        raise ValueError("Frozen local validation schema changed")
    prompt = format_prompt(schema)
    if prompt != (folder / "prompt.txt").read_text():
        raise ValueError("Approved format wrapper changed")
    input_bound(prompt)
    original = json.loads((folder.parent / "local-model/request-plan.json").read_text())
    if (
        plan.get("requests") != original["requests"]
        or plan.get("max_requests") != 12
        or plan.get("max_usd") != "0.25"
        or plan.get("model") != MODEL
    ):
        raise ValueError("DeepSeek allocation differs from approved inputs")
    request = next(r for r in plan["requests"] if r["slot"] == slot)
    source = (root / request["image"]).resolve()
    if (
        not source.is_relative_to((root / "docs/evidence/8/final").resolve())
        or file_hash(source) != request["image_sha256"]
    ):
        raise ValueError("Source screenshot changed or is outside approved inputs")
    image = prepare_image(source, request, root / "data")
    if file_hash(image) != request["prepared_image_sha256"]:
        raise ValueError("Prepared PNG differs from the previous experiment")
    return folder, file_hash(folder / "approval.json"), request, image, prompt


def timestamp():
    return datetime.now(UTC).isoformat()


def execute_paid(
    provider, request, image, runs_dir, approval_hash, prompt, settings, published=None
):
    """Reserve before POST and retain the worst-case cost even after failure."""
    path = runs_dir / "issue-10-deepseek-ledger.json"
    with exclusive_ledger(runs_dir / "issue-10-ledger.json"):
        ledger = (
            json.loads(path.read_text())
            if path.exists()
            else {
                "approval_sha256": approval_hash,
                "max_requests": 12,
                "max_usd": "0.25",
                "slots": [],
                "discovery": [],
            }
        )
        if (
            ledger["approval_sha256"] != approval_hash
            or ledger["max_requests"] != 12
            or ledger["max_usd"] != "0.25"
        ):
            raise ValueError("DeepSeek ledger authorization changed")
        if any(Decimal(r["reserved_usd"]) != RESERVATION for r in ledger["slots"]):
            raise ValueError("Cost reservations cannot be changed")
        if published and not published_reservations_present(published, ledger):
            raise ValueError("Published reservations cannot be reset")
        if ledger.get("halt_reason") or any(
            r["requests_sent"] is None for r in ledger["slots"]
        ):
            raise ValueError("Interrupted or halted experiment cannot continue")
        if (
            any(r["slot"] == request["slot"] for r in ledger["slots"])
            or len(ledger["slots"]) >= 12
        ):
            raise ValueError("DeepSeek slot already reserved or cap reached")
        if provider.settings != settings:
            raise ValueError("Provider settings differ from approved plan")
        input_bound(prompt)
        reserved = sum(
            (Decimal(r["reserved_usd"]) for r in ledger["slots"]), Decimal(0)
        )
        if reserved + RESERVATION > CAP:
            raise ValueError("Next reservation exceeds USD 0.25")
        if not ledger["discovery"]:
            try:
                models = provider.models()
                ledger["discovery"].append(
                    {
                        "method": "GET",
                        "path": "/models",
                        "at_utc": timestamp(),
                        "result": models,
                    }
                )
                write_json(path, ledger)
            except (ProviderError, ValueError, ArithmeticError, KeyError, TypeError):
                ledger["halt_reason"] = (
                    "Initial model discovery failed; zero generation sends"
                )
                write_json(path, ledger)
                raise ValueError(ledger["halt_reason"]) from None
        try:
            before = provider.balance()
        except (ProviderError, ValueError, ArithmeticError, KeyError, TypeError):
            ledger["halt_reason"] = (
                "Pre-send balance unavailable; no new generation sent"
            )
            write_json(path, ledger)
            raise ValueError(ledger["halt_reason"]) from None
        ledger["discovery"].append(
            {
                "method": "GET",
                "path": "/user/balance",
                "at_utc": timestamp(),
                "usd": str(before),
            }
        )
        ledger.setdefault("initial_balance_usd", str(before))
        observed = Decimal(ledger["initial_balance_usd"]) - before
        if before < RESERVATION or observed < 0 or observed > reserved:
            ledger["halt_reason"] = (
                "Balance inconsistent with reserved task budget or insufficient"
            )
            write_json(path, ledger)
            raise ValueError(ledger["halt_reason"])
        run_id = new_run_id()
        entry = {
            "slot": request["slot"],
            "run_id": run_id,
            "reservation": 1,
            "reserved_usd": str(RESERVATION),
            "requests_sent": None,
            "status": "reserved_or_interrupted",
            "balance_before_usd": str(before),
        }
        ledger["slots"].append(entry)
        write_json(path, ledger)
        result, directory = run_check(
            provider,
            image,
            runs_dir,
            RequestBudget(1),
            secrets=(provider._key,),
            prompt=prompt,
            output_model=ReadingOutput,
            schema_version=SCHEMA_VERSION,
            run_id=run_id,
        )
        entry.update(
            requests_sent=result.metadata["requests_sent"], status=result.status
        )
        write_json(path, ledger)
        raw_path = directory / "response_raw.json"
        raw = json.loads(raw_path.read_text()) if raw_path.exists() else {}
        usage = raw.get("usage")
        try:
            estimate = peak_cost(usage)
        except ValueError:
            estimate = None
            ledger["halt_reason"] = "Returned usage exceeded reserved bound"
        entry["usage_peak_estimate_usd"] = (
            str(estimate) if estimate is not None else None
        )
        entry["usage_source"] = (
            "raw API response"
            if usage is not None
            else "unavailable; reservation retained"
        )
        try:
            after = provider.balance()
            entry["balance_after_usd"] = str(after)
            ledger["discovery"].append(
                {
                    "method": "GET",
                    "path": "/user/balance",
                    "at_utc": timestamp(),
                    "usd": str(after),
                }
            )
            delta = Decimal(ledger["initial_balance_usd"]) - after
            if after > before or delta > reserved + RESERVATION:
                ledger["halt_reason"] = (
                    "Post-send balance inconsistent with task reservation"
                )
        except (ProviderError, ValueError, ArithmeticError, KeyError, TypeError):
            ledger["halt_reason"] = (
                "Post-send balance unavailable; generation still counted"
            )
        if raw.get("http_status") in (400, 401, 403, 404) or (
            result.reason or ""
        ).startswith("api_error:"):
            ledger["halt_reason"] = (
                "Unusable API/configuration response; no fallback or tuning"
            )
        write_json(
            directory / "experiment.json", {**request, "approval_sha256": approval_hash}
        )
        write_json(directory / "cost.json", entry)
        write_json(path, ledger)
        return result, directory, ledger.get("halt_reason")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slot", type=int, choices=range(1, 13), required=True)
    parser.add_argument("--max-requests", type=int, choices=[1], required=True)
    args = parser.parse_args()
    folder = REPO_ROOT / "docs/evidence/10/deepseek"
    try:
        folder, approval_hash, request, image, prompt = load_context(
            REPO_ROOT, args.slot
        )
        provider = DeepSeekProvider(os.environ.get("DEEPSEEK_API_KEY", ""))
        settings = json.loads((folder / "request-plan.json").read_text())["settings"]
        published = folder / "ledger.json"
        result, directory, halt = execute_paid(
            provider,
            request,
            image,
            REPO_ROOT / "data/runs",
            approval_hash,
            prompt,
            settings,
            json.loads(published.read_text()) if published.exists() else None,
        )
        write_json(
            folder / "ledger.json",
            json.loads(
                (REPO_ROOT / "data/runs/issue-10-deepseek-ledger.json").read_text()
            ),
        )
    except Exception as exc:  # noqa: BLE001 - never print environment or arbitrary HTTP errors
        print("DeepSeek refused/interrupted:", type(exc).__name__)
        return 1
    print(directory)
    print(result.status, "requests_sent:", result.metadata["requests_sent"])
    if halt:
        print("Experiment halted:", halt)
        return 1
    return 0 if result.status == "checked" else 2


if __name__ == "__main__":
    raise SystemExit(main())
