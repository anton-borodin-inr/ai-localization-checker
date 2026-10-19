"""Issue 10 experiment: isolated transcription output and persistent request slots.

No reference text is placed in the model prompt. Production finding semantics
and the production response schema remain unchanged.
"""

import argparse
import hashlib
import json
import os
from contextlib import contextmanager
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from l10n_checker.capture import REPO_ROOT
from l10n_checker.tiling import TECH_PICKER_TILES, crop_tiles
from l10n_checker.vision import (
    ModelOutput,
    Region,
    RequestBudget,
    new_run_id,
    redact,
    run_check,
)

TASK_CAP = 15
EXPERIMENT_SCHEMA = "issue-10-reading-v1"
PROMPT = """\
Inspect this mobile game UI image. Transcribe all visible text in readings,
including ordinary labels, buttons, description text and numeric counters.
For each reading return text_seen exactly as visible and region on the LOCAL
3x3 grid of the supplied image. Keep separate UI elements as separate readings.
Do not complete text hidden beyond an image or scroll boundary. Do not guess
unreadable characters. Icons need not be transcribed.
Also return findings for visible localization defects, using defect_type,
text_seen, local region and confidence. Types: truncated_text, overlap,
untranslated, other. An ellipsis is a defect only if the full text is not
available elsewhere on the original screenshot. Scroll viewport clipping is
not a defect. The input may be a crop: image edges and missing context alone
are not evidence of a localization defect. Return an empty findings list when
no defect is supported. Reading ordinary text does not make it a defect.
"""


class Reading(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text_seen: str
    region: Region


class ReadingOutput(ModelOutput):
    readings: list[Reading]


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value) -> None:
    """Durably replace one record; never truncate the prior ledger in place."""
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


@contextmanager
def exclusive_ledger(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_suffix(".lock")
    # A stale lock is deliberately not removed automatically after a crash.
    descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        yield
    finally:
        os.close(descriptor)
        lock.unlink()


def validate_inputs(root: Path, plan_path: Path, approval_path: Path, slot: int):
    plan = json.loads(plan_path.read_text())
    approval = json.loads(approval_path.read_text())
    reference = root / "docs/evidence/10/reference-candidate.json"
    if (
        approval.get("accepted_by") != "Anton"
        or approval.get("status") != "confirmed"
        or approval.get("reference_sha256") != file_hash(reference)
        or approval.get("plan_sha256") != file_hash(plan_path)
        or plan.get("reference_sha256") != file_hash(reference)
    ):
        raise ValueError("Reference and request plan need matching Anton confirmation")
    requests = plan["requests"]
    if (
        plan.get("task_request_cap") != TASK_CAP
        or len(requests) != TASK_CAP
        or {r["slot"] for r in requests} != set(range(1, TASK_CAP + 1))
        or any(r["max_requests"] != 1 for r in requests)
        or plan.get("retries") != 0
        or plan.get("free_tier_only") is not True
    ):
        raise ValueError("Expected the approved fifteen single-request slots")
    request = next(r for r in requests if r["slot"] == slot)
    source = (root / request["image"]).resolve()
    if not source.is_relative_to((root / "docs/evidence/8/final").resolve()):
        raise ValueError("Only the approved issue 8 final screenshots are allowed")
    if file_hash(source) != request["image_sha256"]:
        raise ValueError("Original screenshot hash changed")
    # A fresh checkout must not reset this issue's already spent task budget.
    archived_ledger = root / "docs/evidence/10/ledger.json"
    if archived_ledger.exists():
        archived = json.loads(archived_ledger.read_text())
        if len(archived["slots"]) >= TASK_CAP:
            raise ValueError(
                "Task budget exhausted in the published ledger; no more calls"
            )
        local_ledger = root / "data/runs/issue-10-ledger.json"
        if not local_ledger.exists() and archived["slots"]:
            raise ValueError(
                "Published reservations exist; refusing a fresh task ledger"
            )
    return request, source


def prepare_image(source: Path, request: dict, data_dir: Path) -> Path:
    if request["tile"] == "full":
        return source
    if TECH_PICKER_TILES.get(request["tile"]) != tuple(request["box"]):
        raise ValueError("Crop differs from the fixed experiment tiles")
    destination = data_dir / "issue-10/tiles" / source.stem
    manifest = destination / "tiles.json"
    if not destination.exists():
        records = crop_tiles(source, destination, TECH_PICKER_TILES)
        write_json(manifest, records)
    records = json.loads(manifest.read_text())
    for record in records:
        if record["source_sha256"] != file_hash(source):
            raise ValueError("Tile source hash changed")
        if record["sha256"] != file_hash(Path(record["path"])):
            raise ValueError("Prepared tile hash changed")
    return Path(next(r for r in records if r["name"] == request["tile"])["path"])


def execute_slot(provider, request, image, runs_dir, plan_hash, secrets=()):
    """Reserve before sending. Failed/interrupted slots are never reusable."""
    ledger_path = runs_dir / "issue-10-ledger.json"
    with exclusive_ledger(ledger_path):
        ledger = (
            json.loads(ledger_path.read_text())
            if ledger_path.exists()
            else {"task_request_cap": TASK_CAP, "plan_sha256": plan_hash, "slots": []}
        )
        if ledger["plan_sha256"] != plan_hash or ledger["task_request_cap"] != TASK_CAP:
            raise ValueError("Ledger belongs to a different request plan")
        if any(s["slot"] == request["slot"] for s in ledger["slots"]):
            raise ValueError("This slot was already reserved; no retry is allowed")
        if len(ledger["slots"]) >= TASK_CAP:
            raise ValueError("Task request cap reached")
        run_id = new_run_id()
        record = {
            "slot": request["slot"],
            "run_id": run_id,
            "reservation": 1,
            "requests_sent": None,
            "status": "reserved_or_interrupted",
        }
        ledger["slots"].append(record)
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
        write_json(run_dir / "experiment.json", request)
        record.update(
            requests_sent=result.metadata["requests_sent"], status=result.status
        )
        write_json(ledger_path, ledger)
        return result, run_dir


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--slot", type=int, choices=range(1, TASK_CAP + 1), required=True
    )
    parser.add_argument("--max-requests", type=int, choices=[1], required=True)
    parser.add_argument("--free-tier-key", action="store_true", required=True)
    args = parser.parse_args()
    root = REPO_ROOT
    plan_path = root / "docs/evidence/10/request-plan.json"
    approval_path = root / "docs/evidence/10/reference-approval.json"
    # The application loads the key; the agent never inspects it or the env file.
    key = os.environ.get("GEMINI_API_KEY", "")
    try:
        request, source = validate_inputs(root, plan_path, approval_path, args.slot)
        image = prepare_image(source, request, root / "data")
        if not key:
            raise ValueError("GEMINI_API_KEY is not set; no request sent")
        # Import provider-specific configuration only at the adapter boundary.
        from l10n_checker.gemini import make_reading_provider

        provider = make_reading_provider(
            key, request["media_resolution"], ReadingOutput
        )
        result, run_dir = execute_slot(
            provider, request, image, root / "data/runs", file_hash(plan_path), (key,)
        )
    except Exception as exc:  # noqa: BLE001 - redact all command failures
        print(redact(f"Experiment refused or interrupted: {exc}", (key,)))
        return 1
    print(run_dir)
    print(result.status, "requests_sent:", result.metadata["requests_sent"])
    return 0 if result.status == "checked" else 2
