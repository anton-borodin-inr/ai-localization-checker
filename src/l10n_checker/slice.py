"""Issue 14 orchestration and replay. Detector and evaluator rules are reused."""

import hashlib
import json
import shutil
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path

from pydantic import ValidationError

from l10n_checker.baseline import resolve_inputs, run_baseline
from l10n_checker.matching import Label, MatchingConfig, match_screen
from l10n_checker.metrics import score_screen, score_screens
from l10n_checker.vision import (
    CheckResult,
    ModelOutput,
    ProviderError,
    RequestBudget,
    new_run_id,
    run_check,
)

REFERENCE_SOURCE = "docs/experiments/issue-10/reference-amendment-candidate.json"
REFERENCE_SHA256 = "bba4e51d48d81bfa836eb80632697069b4e70fd67944a09f93d71aada609dd19"
MAX_REQUESTS = 10
MAX_USD = Decimal("0.10")
# Operational reservation, not a provider-enforced token/billing ceiling.
# 8192 assumed input tokens + 4096 capped output tokens cost < $0.008
# at the frozen peak tariff. Stop on missing usage or an exceeded reservation.
RESERVE_USD = Decimal("0.01")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def snapshot(source: Path, target: Path) -> dict:
    shutil.copyfile(source, target)
    return {"file": target.name, "sha256": digest(target)}


def checked_file(root: Path, entry: dict) -> Path:
    path = (root / entry["file"]).resolve()
    if not path.is_relative_to(root.resolve()) or digest(path) != entry["sha256"]:
        raise ValueError("Bundle file path or SHA-256 mismatch")
    return path


def reference_texts(screen: dict) -> tuple[list[str], list[dict]]:
    """Preserve reference occurrences, including explicitly visible diagnostics.

    Do not use assembled_full_text or infer missing/repeated occurrences.
    Numeric diagnostics have no occurrence metadata; retain each supplied entry
    once and expose that limitation. Never deduplicate the reference.
    """
    entries = [
        {
            "source": f"rows/{i}/text_seen",
            "text": row["text_seen"],
            "id": row["id"],
            "visibility": row["visibility"],
            "region": row["region"],
        }
        for i, row in enumerate(screen["rows"])
    ]
    entries += [
        {"source": f"numeric_diagnostics/{i}", "text": value}
        for i, value in enumerate(screen.get("numeric_diagnostics", []))
    ]
    return [entry["text"] for entry in entries], entries


def prepare(
    images: Path,
    labels: Path,
    reference: Path,
    approval: Path,
    manifest: Path,
    inventory: Path,
    fork: Path,
) -> list[dict]:
    """Check all inputs before creating a provider or sending any request."""
    approved = read(approval)
    if not (
        approved.get("status") == "confirmed"
        and approved.get("accepted_by") == "Anton"
        and approved.get("reference_sha256") == digest(reference)
        and digest(reference) == REFERENCE_SHA256
    ):
        raise ValueError("Reference must have Anton's hash-bound confirmation")
    refs = read(reference)["screens"]
    captures = read(manifest)["captures"]
    images_found = sorted(images.glob("*.png"))
    if not images_found:
        raise ValueError("No PNG screenshots in the input folder")
    prepared = []
    for image in images_found:
        matches = [s for s in refs if Path(s["image"]).name == image.name]
        caps = [c for c in captures if c["file"] == image.name]
        if len(matches) != 1 or len(caps) != 1:
            raise ValueError(f"Missing or ambiguous provenance: {image.name}")
        screen, capture = matches[0], caps[0]
        if digest(image) != screen["sha256"]:
            raise ValueError(f"Reference image hash mismatch: {image.name}")
        label_path = labels / image.with_suffix(".labels.json").name
        if digest(label_path) != capture["human_label_sha256"]:
            raise ValueError(f"Human label hash mismatch: {image.name}")
        human = read(label_path)
        if (
            human["screenshot"] != image.name
            or human["language"] != image.stem.split("__")[1]
        ):
            raise ValueError(f"Human label identity mismatch: {image.name}")
        for label in human["labels"]:
            Label.model_validate(label)
        # Baseline validates build commits, PNG, translations and inventory.
        _, _, _, _, source = resolve_inputs(image, manifest, inventory, fork)
        build = read(reference)["builds"][screen["build"]]
        if source["fork_commit"] != build["commit"] or any(
            source["translations"][code]["sha256"]
            != build["translations"][name]["sha256"]
            for code, name in (("en", "English"), ("de", "German"))
        ):
            raise ValueError(f"Reference build provenance mismatch: {image.name}")
        prepared.append({"image": image, "label": label_path})
    return prepared


class Ledger:
    """Persistent task-wide accounting. Caller holds the exclusive workspace lock."""

    def __init__(self, path: Path):
        self.path = path
        self.data = read(path) if path.exists() else {"attempts": []}

    def reserve(self, image: str) -> int:
        attempts = self.data["attempts"]
        if any(a["state"] != "accounted" for a in attempts):
            raise ValueError("Unresolved API attempt; stop for accounting review")
        spent = sum((Decimal(a["charged_usd"]) for a in attempts), Decimal(0))
        if len(attempts) >= MAX_REQUESTS or spent + RESERVE_USD > MAX_USD:
            raise ValueError("Issue 14 request or USD budget exhausted")
        attempts.append(
            {
                "image": image,
                "state": "reserved",
                "charged_usd": str(RESERVE_USD),
                "reservation_usd": str(RESERVE_USD),
            }
        )
        write(self.path, self.data)
        return len(attempts) - 1

    def account(self, index: int, metadata: dict) -> None:
        attempt = self.data["attempts"][index]
        cost = metadata["estimated_cost"]
        known = cost is not None
        amount = Decimal(cost["peak_usd"]) if known else RESERVE_USD
        attempt.update(
            {
                "state": "accounted"
                if known and amount <= RESERVE_USD
                else "unresolved",
                "charged_usd": str(amount),
                "run_id": metadata["run_id"],
                "requests_sent": metadata["requests_sent"],
                "usage": metadata["usage"],
                "estimated_cost": cost,
            }
        )
        write(self.path, self.data)


def run_slice(
    prepared: list[dict],
    reference: Path,
    approval: Path,
    manifest: Path,
    inventory: Path,
    fork: Path,
    workspace: Path,
    provider_factory,
    secrets: tuple[str, ...] = (),
) -> Path:
    """One invocation, one request per vision run, no automatic re-runs."""
    workspace.mkdir(parents=True, exist_ok=True)
    lock = workspace / ".lock"
    # Retain a crash lock: don't silently resume a possibly sent request.
    with lock.open("x"):
        pass
    try:
        ledger = Ledger(workspace / "budget.json")
        if any(a["state"] != "accounted" for a in ledger.data["attempts"]):
            raise ValueError("Unresolved API attempt; no new calls allowed")
        session = workspace / new_run_id()
        session.mkdir()
        inputs = session / "inputs"
        inputs.mkdir()
        refs = {
            name: snapshot(path, inputs / name)
            for name, path in (
                ("reference.json", reference),
                ("approval.json", approval),
                ("pair-manifest.json", manifest),
                ("inventory.json", inventory),
            )
        }
        bundle = {
            "version": 1,
            "reference_source": REFERENCE_SOURCE,
            "matching_config": asdict(MatchingConfig()),
            "inputs": refs,
            "screens": [],
            "expected_images": [item["image"].name for item in prepared],
            "budget_stops": [],
        }
        write(session / "bundle.json", bundle)
        # Initialize the provider only after complete input preflight.
        provider = provider_factory()
        for item in prepared:
            image = item["image"]
            label_entry = snapshot(item["label"], inputs / item["label"].name)
            _, baseline_dir = run_baseline(
                image, manifest, inventory, fork, session / "baseline"
            )
            index = None
            try:
                index = ledger.reserve(image.name)
            except ValueError as exc:
                bundle["budget_stops"].append({"image": image.name, "reason": str(exc)})
            _, vision_dir = run_check(
                provider,
                image,
                session / "vision",
                RequestBudget(1 if index is not None else 0),
                secrets=secrets,
            )
            if index is not None:
                ledger.account(index, read(vision_dir / "run.json"))
            records = {}
            for detector, directory in (
                ("baseline", baseline_dir),
                ("vision", vision_dir),
            ):
                records[detector] = {
                    p.name: {"file": str(p.relative_to(session)), "sha256": digest(p)}
                    for p in sorted(directory.iterdir())
                    if p.is_file()
                }
            bundle["screens"].append(
                {
                    "image": image.name,
                    "sha256": digest(image),
                    "labels": label_entry,
                    "records": records,
                }
            )
            # Preserve partial progress before any subsequent request.
            write(session / "bundle.json", bundle)
            write(session / "budget.json", ledger.data)
        replay(session / "bundle.json", session / "comparison")
        return session
    finally:
        lock.unlink()


def load_result(root: Path, records: dict, image: dict, detector: str) -> CheckResult:
    for entry in records.values():
        checked_file(root, entry)
    result = CheckResult.model_validate_json(
        checked_file(root, records["result.json"]).read_text()
    )
    metadata = read(checked_file(root, records["run.json"]))
    if result.metadata != metadata or metadata["image"]["sha256"] != image["sha256"]:
        raise ValueError("Run/result/image provenance mismatch")
    recorded_name = Path(
        metadata["image"].get("path", metadata["image"].get("name", ""))
    ).name
    if recorded_name != image["image"]:
        raise ValueError("Run screenshot identity mismatch")
    if detector == "vision":
        if metadata["schema_version"] != "v1" or metadata["prompt_version"] != "v1":
            raise ValueError("Issue 14 requires prompt/schema v1")
        if result.status == "checked" and metadata["readability"] != "readable":
            raise ValueError("Only readable vision responses may be checked")
        for filename, field in (
            ("prompt.txt", "prompt_sha256"),
            ("prompt_sent.txt", "sent_prompt_sha256"),
        ):
            if digest(checked_file(root, records[filename])) != metadata[field]:
                raise ValueError("Recorded prompt hash mismatch")
        # Revalidate saved provider content without initializing a client.
        from l10n_checker.deepseek import DeepSeekProvider

        output = None
        try:
            if "response_raw.json" in records:
                response = DeepSeekProvider._parse(
                    read(checked_file(root, records["response_raw.json"]))
                )
                output = ModelOutput.model_validate_json(response.text)
        except (ProviderError, ValidationError):
            pass
        checked = output is not None and output.readability == "readable"
        if checked != (result.status == "checked"):
            raise ValueError("Recorded result contradicts saved provider response")
        if checked and result.findings != output.findings:
            raise ValueError("Recorded findings contradict saved provider response")
        if metadata["readability"] != (output.readability if output else None):
            raise ValueError("Recorded readability contradicts saved provider response")
    return result


def replay(bundle_path: Path, output: Path) -> dict:
    """Offline: only hashed snapshots and recorded results enter the evaluator."""
    root = bundle_path.parent
    bundle = read(bundle_path)
    if bundle["version"] != 1 or not bundle["screens"]:
        raise ValueError("Unsupported or empty bundle")
    protected = {bundle_path.resolve(), (root / "budget.json").resolve()}
    protected.update(
        (root / "inputs" / e["file"]).resolve() for e in bundle["inputs"].values()
    )
    for screen in bundle["screens"]:
        protected.add((root / "inputs" / screen["labels"]["file"]).resolve())
        protected.update(
            (root / e["file"]).resolve()
            for files in screen["records"].values()
            for e in files.values()
        )
    if any(
        output.with_suffix(suffix).resolve() in protected for suffix in (".json", ".md")
    ):
        raise ValueError("Replay output would overwrite an input or run record")
    inputs = {
        name: checked_file(root / "inputs", entry)
        for name, entry in bundle["inputs"].items()
    }
    reference = read(inputs["reference.json"])
    approval = read(inputs["approval.json"])
    if approval["reference_sha256"] != digest(inputs["reference.json"]):
        raise ValueError("Reference approval mismatch")
    if digest(inputs["reference.json"]) != REFERENCE_SHA256:
        raise ValueError("Reference is not the confirmed issue 10 amendment")
    if approval["status"] != "confirmed" or approval["accepted_by"] != "Anton":
        raise ValueError("Reference not confirmed by Anton")
    captures = read(inputs["pair-manifest.json"])["captures"]
    config = MatchingConfig(**bundle["matching_config"])
    all_matches = {"baseline": [], "vision": []}
    rows = []
    seen = set()
    for screen in bundle["screens"]:
        if screen["image"] in seen:
            raise ValueError("Duplicate screenshot in bundle")
        seen.add(screen["image"])
        reference_screens = [
            s for s in reference["screens"] if Path(s["image"]).name == screen["image"]
        ]
        if (
            len(reference_screens) != 1
            or reference_screens[0]["sha256"] != screen["sha256"]
        ):
            raise ValueError("Bundle/reference screenshot mismatch")
        label_path = checked_file(root / "inputs", screen["labels"])
        capture = next(c for c in captures if c["file"] == screen["image"])
        if capture["human_label_sha256"] != digest(label_path):
            raise ValueError("Bundle/human label provenance mismatch")
        human = read(label_path)
        if human["screenshot"] != screen["image"]:
            raise ValueError("Bundle/human label identity mismatch")
        labels = [Label.model_validate(label) for label in human["labels"]]
        texts, sources = reference_texts(reference_screens[0])
        for detector, detector_matches in all_matches.items():
            result = load_result(root, screen["records"][detector], screen, detector)
            matches = match_screen(
                labels, result.findings, texts, result.status, config
            )
            detector_matches.append(matches)
            meta = result.metadata
            cost = meta.get("estimated_cost")
            rows.append(
                {
                    "image": screen["image"],
                    "detector": detector,
                    "run_id": meta["run_id"],
                    "status": result.status,
                    "reason": result.reason,
                    "readability": meta.get("readability"),
                    "findings": len(result.findings),
                    "finding_details": [f.model_dump() for f in result.findings],
                    "missing_rule_findings": meta.get("missing_rule_findings", []),
                    "matches": [asdict(m) for m in matches.matches],
                    "false_positive_indices": list(matches.unmatched_finding_indices),
                    "hallucination_indices": list(matches.hallucination_indices),
                    **score_screen(matches).to_dict(),
                    "requests_sent": meta["requests_sent"],
                    "usage": meta.get("usage"),
                    "estimated_peak_usd": cost["peak_usd"]
                    if cost
                    else ("0" if detector == "baseline" else None),
                    "latency_s": meta["latency_s"]
                    if detector == "baseline"
                    else round(sum(a["latency_s"] for a in meta["attempts"]), 3),
                    "screen_texts_source": sources,
                }
            )
    totals = {}
    for detector, matches in all_matches.items():
        selected = [r for r in rows if r["detector"] == detector]
        costs = [r["estimated_peak_usd"] for r in selected]
        totals[detector] = {
            **score_screens(matches).to_dict(),
            "findings": sum(r["findings"] for r in selected),
            "requests_sent": sum(r["requests_sent"] for r in selected),
            "estimated_peak_usd": str(sum(map(Decimal, costs), Decimal(0)))
            if None not in costs
            else None,
            "latency_s": round(sum(r["latency_s"] for r in selected), 3),
        }
    report = {
        "scope": "Variants of one source screen, not quality estimates.",
        "expected_images": bundle["expected_images"],
        "missing_images": sorted(set(bundle["expected_images"]) - seen),
        "budget_stops": bundle["budget_stops"],
        "reference_source": bundle["reference_source"],
        "reference_sha256": digest(inputs["reference.json"]),
        "reference_limitations": (
            "Reference #10 is a transcription inventory, not an exhaustive occurrence map. "
            "All rows/text_seen and supplied numeric diagnostics are used unchanged; "
            "clipped diagnostics are included, hidden assembled_full_text is excluded. "
            "Numbers lack occurrence counts/regions; split spans and punctuation may affect "
            "hallucination counts. See the human-review gap audit in the issue 14 report."
        ),
        "time_definition": "Baseline complete run elapsed; vision sum of provider attempt latency.",
        "matching_config": bundle["matching_config"],
        "rows": rows,
        "totals": totals,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    write(output.with_suffix(".json"), report)
    output.with_suffix(".md").write_text(markdown(report), encoding="utf-8")
    return report


def markdown(report: dict) -> str:
    columns = [
        "image",
        "detector",
        "status",
        "readability",
        "findings",
        "tp",
        "fp",
        "fn",
        "fn_on_not_checked",
        "precision",
        "recall_checked",
        "recall_all",
        "hallucinations",
        "not_checked_screens",
        "estimated_peak_usd",
        "latency_s",
    ]
    lines = [
        "# Vertical slice comparison",
        "",
        report["scope"],
        "",
        f"Hallucination source: `{report['reference_source']}`.",
        "",
        report["reference_limitations"],
        "",
        report["time_definition"],
        "",
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in [
        *report["rows"],
        *(
            {"image": "TOTAL", "detector": name, **values}
            for name, values in report["totals"].items()
        ),
    ]:
        values = [
            str(row.get(k)) if row.get(k) is not None else "null" for k in columns
        ]
        lines.append(
            "| "
            + " | ".join(v.replace("|", "\\|").replace("\n", " ") for v in values)
            + " |"
        )
    lines += [
        "",
        "FN excludes labels on not_checked screens; fn_on_not_checked lists them separately.",
        "Undefined ratios are null. Baseline API cost is zero; local compute cost is not measured.",
        "Readability is the model's report, not independently verified reading coverage.",
        f"Missing requested screenshots: {report['missing_images']}.",
        f"Budget stops: {report['budget_stops']}.",
        "",
    ]
    return "\n".join(lines)
