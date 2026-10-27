"""Run the unchanged l10n-check CLI twice per approved issue-45 PNG, with a task ledger."""

import argparse
import fcntl
import json
import os
import shutil
import subprocess
from decimal import Decimal
from pathlib import Path

from issue45_capture import ALLOWED, digest, write_json

from l10n_checker.deepseek import MAX_TOKENS, TARIFF, WRAPPER, schema_text
from l10n_checker.vision import PROMPT

REPO = Path(__file__).resolve().parents[1]
EVIDENCE = REPO / "docs/evidence/45"
DATA = REPO / "data/issue-45"
# Published Flash context limit is 1M. Reserve 1 Mi tokens at cache-miss peak
# price, plus the unchanged maximum output, even for a failure without usage.
# Official pricing checked 2026-10-21; this is an accounting bound, not a charge.
MAX_REQUEST_USD = (
    Decimal(1048576) * Decimal("0.30") + Decimal(MAX_TOKENS) * Decimal("1.20")
) / 1000000


def freeze_check():
    frozen = json.loads((EVIDENCE / "frozen-contract.json").read_text())
    actual = {
        "prompt.txt": PROMPT.encode(),
        "schema.json": schema_text().encode(),
        "prompt_sent.txt": (PROMPT + WRAPPER + schema_text()).encode(),
    }
    for name, data in actual.items():
        if (
            digest(data) != frozen["hashes"][name]
            or (EVIDENCE / name).read_bytes() != data
        ):
            raise ValueError("Frozen prompt/schema/wrapper changed")
    for relative, checksum in frozen["unchanged_source_files"].items():
        if digest((REPO / relative).read_bytes()) != checksum:
            raise ValueError("Frozen detector/provider source changed")
    rates = TARIFF["peak_per_million_tokens"]
    if rates != {
        "input_cache_hit": "0.006",
        "input_cache_miss": "0.30",
        "output": "1.20",
    }:
        raise ValueError("Provider tariff differs from the verified accounting bound")


def captured_images(folder):
    folder = folder.resolve()
    if not folder.is_relative_to((DATA / "captures").resolve()):
        raise ValueError("Only issue-45 capture folders are accepted")
    audit = json.loads((folder / "capture-audit.json").read_text())
    if (
        audit["status"] != "captured"
        or not audit.get("settings_restored_byte_identical")
        or not audit.get("all_saves_unchanged")
    ):
        raise ValueError("Capture/restore audit did not succeed")
    images = []
    for capture in audit["captures"]:
        if capture["screen"] not in ALLOWED or capture["status"] != "captured":
            raise ValueError("Screen outside the dev allowlist or incomplete capture")
        ready = (
            f"L10N_SCREEN_READY {capture['screen']} request={capture['request_id']} "
        )
        if not any(ready in line for line in capture["hook"]["events"]):
            raise ValueError("Capture has no matching D-038 READY event")
        image = (folder / capture["png"]).resolve()
        if (
            not image.is_relative_to(folder)
            or image.name.split("__")[0] != capture["screen"]
        ):
            raise ValueError("PNG escapes the audited capture folder or screen")
        if digest(image.read_bytes()) != capture["sha256"]:
            raise ValueError("Audited PNG hash differs")
        images.append((image, capture["sha256"]))
    if not images:
        raise ValueError("No captured PNGs")
    return images


def spent(ledger):
    requests = sum(
        r.get("request_upper_bound", r.get("requests_sent", 0)) for r in ledger["runs"]
    )
    cost = sum(
        (
            Decimal(r.get("peak_usd", "0"))
            + Decimal(r.get("unknown_cost_reserve_usd", "0"))
            for r in ledger["runs"]
        ),
        Decimal(0),
    )
    return requests, cost


def check_budget(ledger):
    requests, cost = spent(ledger)
    if requests + 1 > 100 or cost + MAX_REQUEST_USD > Decimal("1.00"):
        raise ValueError(
            "No next request fits both task caps including worst-case reservation"
        )
    if any(r["status"] in {"pending", "unreconciled"} for r in ledger["runs"]):
        raise ValueError(
            "An interrupted request remains unreconciled; do not send another"
        )


def summarize(ledger):
    ledger["requests_upper_bound"], cost = spent(ledger)
    ledger["requests_sent"] = sum(r.get("requests_sent", 0) for r in ledger["runs"])
    ledger["known_peak_estimate_usd"] = str(
        sum((Decimal(r.get("peak_usd", "0")) for r in ledger["runs"]), Decimal(0))
    )
    ledger["unknown_cost_reserve_usd"] = str(
        sum(
            (Decimal(r.get("unknown_cost_reserve_usd", "0")) for r in ledger["runs"]),
            Decimal(0),
        )
    )
    ledger["accounted_peak_upper_bound_usd"] = str(cost)


def execute(image, checksum, repetition, ledger, ledger_path):
    check_budget(ledger)
    entry = {
        "image": str(image.relative_to(REPO)),
        "image_sha256": checksum,
        "repetition": repetition,
        "status": "pending",
        "request_upper_bound": 1,
        "unknown_cost_reserve_usd": str(MAX_REQUEST_USD),
    }
    ledger["runs"].append(entry)
    summarize(ledger)
    write_json(ledger_path, ledger)
    runs = REPO / "data/runs"
    runs.mkdir(parents=True, exist_ok=True)
    before = set(runs.iterdir())
    command = [
        "uv",
        "run",
        "--env-file",
        ".env",
        "--no-sync",
        "l10n-check",
        "--image",
        str(image.relative_to(REPO)),
        "--runs-dir",
        "data/runs",
        "--max-requests",
        "1",
    ]
    env = dict(os.environ, PYTHONPATH=str(REPO / "src"))
    result = subprocess.run(
        command, cwd=REPO, env=env, capture_output=True, text=True, check=False
    )
    new = set(runs.iterdir()) - before
    matches = []
    for folder in new:
        metadata = folder / "run.json"
        if metadata.is_file():
            record = json.loads(metadata.read_text())
            if record["image"]["sha256"] == checksum:
                matches.append((folder, record))
    entry["cli_exit_code"] = result.returncode
    if len(matches) != 1:
        entry["status"] = "unreconciled"
        summarize(ledger)
        write_json(ledger_path, ledger)
        raise ValueError(
            "CLI did not produce exactly one matching run record; reservation retained"
        )
    folder, record = matches[0]
    if record["requests_sent"] not in (0, 1) or record["max_requests"] != 1:
        raise ValueError("Run violates the per-run cap; pending reservation retained")
    entry.update(
        {
            "status": "recorded",
            "run_id": folder.name,
            "requests_sent": record["requests_sent"],
            "request_upper_bound": record["requests_sent"],
            "usage": record["usage"],
            "model_version": record["model_version"],
            "estimated_cost": record["estimated_cost"],
            "result_status": json.loads((folder / "result.json").read_text())["status"],
        }
    )
    if record["estimated_cost"] is not None:
        entry["peak_usd"] = record["estimated_cost"]["peak_usd"]
        entry["unknown_cost_reserve_usd"] = "0"
    elif record["requests_sent"] == 0:
        entry["unknown_cost_reserve_usd"] = "0"
    destination = EVIDENCE / "run-records" / folder.name
    destination.mkdir(parents=True, exist_ok=False)
    for name in (
        "run.json",
        "result.json",
        "response_raw.json",
        "prompt.txt",
        "prompt_sent.txt",
    ):
        if (folder / name).is_file():
            shutil.copyfile(folder / name, destination / name)
    (destination / "cli.txt").write_text(result.stdout + result.stderr)
    summarize(ledger)
    write_json(ledger_path, ledger)
    print(
        f"{folder.name}: {entry['result_status']}; task requests={ledger['requests_sent']}; accounted upper bound USD {ledger['accounted_peak_upper_bound_usd']}",
        flush=True,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-folder", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    freeze_check()
    images = captured_images(args.capture_folder)
    if not args.execute:
        print(
            f"Eligible: {len(images)} audited PNGs, two independent calls each; no live request."
        )
        return
    if not (REPO / ".env").is_file():
        raise ValueError("No .env file reference is configured; no live request sent")
    DATA.mkdir(exist_ok=True)
    with (DATA / "check.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        ledger_path = EVIDENCE / "api-ledger.json"
        ledger = json.loads(ledger_path.read_text())
        for image, checksum in images:
            for repetition in (1, 2):
                if any(
                    r.get("image") == str(image.relative_to(REPO))
                    and r["repetition"] == repetition
                    for r in ledger["runs"]
                ):
                    continue
                freeze_check()
                execute(image, checksum, repetition, ledger, ledger_path)


if __name__ == "__main__":
    main()
