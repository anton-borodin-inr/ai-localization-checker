"""Fixed issue-48 experiment and offline replay, isolated from capture code."""

import argparse
import hashlib
import json
import platform
import re
import shutil
import subprocess
import sys
import time
from dataclasses import asdict
from importlib.metadata import distributions
from pathlib import Path

from PIL import Image

from l10n_checker.baseline import BaselineError, parse_tsv, run_baseline
from l10n_checker.matching import Label, MatchingConfig, match_screen
from l10n_checker.metrics import score_screen, score_screens
from l10n_checker.ocr import (
    EASY_PARAMS,
    LANGUAGES,
    MODEL_FILES,
    ConfiguredOcr,
    readings,
    sha256,
)
from l10n_checker.reading_metrics import coverage
from l10n_checker.slice import REFERENCE_SOURCE, reference_texts

PROTOCOL = "docs/evidence/48/protocol.json"
PROTOCOL_SHA256 = "c9ffa6e0dcb05a91436500ecc5bb03f027875f0590145dda49c2fe98ae432074"
EVIDENCE = "docs/evidence/48"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def object_hash(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()
    ).hexdigest()


def validated_protocol(root):
    path = root / PROTOCOL
    if sha256(path) != PROTOCOL_SHA256:
        raise ValueError("The pre-registered protocol has changed")
    protocol = read(path)
    if protocol["easyocr"]["readtext"] != EASY_PARAMS:
        raise ValueError("EasyOCR settings differ from the fixed grid")
    for name, expected in protocol["protected_sha256"].items():
        if sha256(root / name) != expected:
            raise ValueError(f"Protected input/code changed: {name}")
    for image in protocol["images"]:
        path = root / image["path"]
        if not path.resolve().is_relative_to(root.resolve()):
            raise ValueError("Input escapes the checkout")
        if sha256(path) != image["sha256"]:
            raise ValueError(f"Image SHA-256 mismatch: {path.name}")
        with Image.open(path) as png:
            if png.format != "PNG" or png.size != (2400, 1080):
                raise ValueError("Unexpected image format or resolution")
    reference = root / REFERENCE_SOURCE
    approval = read(reference.with_name("reference-amendment-approval.json"))
    if (
        sha256(reference) != protocol["reference_sha256"]
        or approval["reference_sha256"] != sha256(reference)
        or approval["accepted_by"] != "Anton"
        or approval["status"] != "confirmed"
    ):
        raise ValueError("The reference lacks its hash-bound human confirmation")
    return protocol


def tesseract_provenance():
    def command(*args):
        return subprocess.run(
            ["tesseract", *args], check=True, text=True, capture_output=True, timeout=30
        ).stdout

    available = command("--list-langs")
    match = re.search(r'in "([^\"]+)"', available)
    if not match:
        raise ValueError("Cannot locate Tesseract traineddata")
    directory = Path(match[1])
    return {
        "version": command("--version").splitlines()[0],
        "traineddata_sha256": {
            lang: sha256(directory / f"{lang}.traineddata") for lang in ("eng", "deu")
        },
    }


def prepare_models(root, model_dir):
    """Network setup only: initialize readers without supplying any image."""
    validated_protocol(root)
    model_dir.mkdir(parents=True, exist_ok=True)
    import easyocr
    import torch
    from easyocr.config import detection_models, recognition_models

    torch.set_num_threads(1)
    for languages in LANGUAGES.values():
        easyocr.Reader(
            languages,
            gpu=False,
            detect_network="craft",
            recog_network="standard",
            quantize=True,
            cudnn_benchmark=False,
            model_storage_directory=str(model_dir),
            user_network_directory=str(model_dir / "user-network"),
            download_enabled=True,
            verbose=False,
        )
    sources = [
        detection_models["craft"],
        recognition_models["gen2"]["english_g2"],
        recognition_models["gen2"]["latin_g2"],
    ]
    manifest = {
        "sha256": {name: sha256(model_dir / name) for name in MODEL_FILES},
        "models": [
            {
                "file": item["filename"],
                "url": item["url"],
                "upstream_md5": item["md5sum"],
            }
            for item in sources
        ],
        "easyocr_version": easyocr.__version__,
    }
    write(model_dir / "models.json", manifest)
    environment = {
        "protocol_sha256": PROTOCOL_SHA256,
        "python": sys.version,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "packages": dict(
            sorted((d.metadata["Name"].lower(), d.version) for d in distributions())
        ),
        "uv_lock_sha256": sha256(root / "uv.lock"),
        "models": manifest,
        "tesseract": tesseract_provenance(),
        "source_sha256": {
            name: sha256(root / name)
            for name in (
                "src/l10n_checker/ocr.py",
                "src/l10n_checker/ocr_experiment.py",
                "src/l10n_checker/baseline.py",
                "src/l10n_checker/baseline_cli.py",
            )
        },
        "provider_requests": 0,
        "api_spend_usd": 0,
    }
    destination = root / EVIDENCE / "environment.json"
    if destination.exists():
        if read(destination)["models"] != manifest:
            raise ValueError("Downloaded models differ from the recorded experiment")
        print(
            "Models prepared; the original experiment environment is preserved.",
            flush=True,
        )
        return
    write(destination, environment)
    print("Models and environment frozen; no OCR images processed.", flush=True)


class TimedEngine:
    def __init__(self, engine):
        self.engine = engine
        self.output = None
        self.seconds = 0.0

    def recognize(self, image, language):
        self.output = None
        started = time.monotonic()
        try:
            self.output = self.engine.recognize(image, language)
            return self.output
        finally:
            self.seconds = time.monotonic() - started


def qualitative_run(image, language, engine, directory):
    directory.mkdir(parents=True)
    metadata = {
        "image": {"name": image.name, "sha256": sha256(image)},
        "requests_sent": 0,
    }
    result = {"status": "checked", "reason": None, "findings": [], "metadata": metadata}
    try:
        output = engine.recognize(image, language)
        metadata["ocr"] = output.metadata
        (directory / "ocr.tsv").write_text(output.tsv, encoding="utf-8")
        parse_tsv(output.tsv, (2400, 1080))
    except (BaselineError, OSError, ValueError, KeyError, TypeError) as exc:
        result.update(status="not_checked", reason=f"{type(exc).__name__}: {exc}")
    write(directory / "result.json", result)
    write(directory / "run.json", metadata)


def run_experiment(root, fork, model_dir):
    protocol = validated_protocol(root)
    environment = read(root / EVIDENCE / "environment.json")
    for name, expected in environment["source_sha256"].items():
        if sha256(root / name) != expected:
            raise ValueError(f"Code changed after environment freeze: {name}")
    if sha256(root / "uv.lock") != environment["uv_lock_sha256"]:
        raise ValueError("Dependencies changed after environment freeze")
    if read(model_dir / "models.json") != environment["models"]:
        raise ValueError("Model manifest changed after environment freeze")
    if tesseract_provenance() != environment["tesseract"]:
        raise ValueError("Tesseract changed after environment freeze")
    records = root / EVIDENCE / "records"
    records.mkdir(exist_ok=False)
    rows = []
    for config in protocol["grid"]:
        for repeat in (1, 2):
            engine = ConfiguredOcr(config["engine"], config["preprocess"], model_dir)
            timed = TimedEngine(engine)
            try:
                for image in protocol["images"]:
                    path = root / image["path"]
                    destination = records / config["id"] / f"pass-{repeat}" / path.stem
                    # Persist intent before starting the image operation.
                    row = {
                        "configuration": config["id"],
                        "pass": repeat,
                        "image": image["path"],
                        "language": image["language"],
                        "scope": image["scope"],
                        "record": str(destination.relative_to(root)),
                        "state": "started",
                    }
                    rows.append(row)
                    write(root / EVIDENCE / "operations.json", rows)
                    if image["scope"] == "labelled":
                        _, run_dir = run_baseline(
                            path,
                            root / "docs/evidence/8/pair-manifest.json",
                            root / "docs/evidence/12/tech-picker.json",
                            fork,
                            root / "data/issue-48/runs",
                            timed,
                        )
                        shutil.copytree(run_dir, destination)
                    else:
                        qualitative_run(path, image["language"], timed, destination)
                    result = read(destination / "result.json")
                    initialization = (
                        timed.output.metadata.get("initialization_s", 0)
                        if timed.output
                        else 0
                    )
                    row.update(
                        state="complete",
                        status=result["status"],
                        reason=result["reason"],
                        initialization_s=initialization,
                        operation_s=timed.seconds - initialization,
                    )
                    write(root / EVIDENCE / "operations.json", rows)
                    print(
                        f"{len(rows):02}/84 {config['id']} pass {repeat} {path.name}: {result['status']} ({row['operation_s']:.3f}s)",
                        flush=True,
                    )
            finally:
                engine.close()
    validated_protocol(root)
    index = {
        str((root / EVIDENCE / "operations.json").relative_to(root)): sha256(
            root / EVIDENCE / "operations.json"
        )
    }
    for row in rows:
        for name in (
            "result.json",
            "run.json",
            "ocr.tsv",
            "diagnostics.json",
            "source-entries.json",
        ):
            path = root / row["record"] / name
            if path.exists():
                index[str(path.relative_to(root))] = sha256(path)
    write(root / EVIDENCE / "record-index.json", index)
    summarize(root)


def evaluate(root, row, reference):
    record = root / row["record"]
    result = read(record / "result.json")
    readings_path = record / "readings.json"
    observed = (
        readings((record / "ocr.tsv").read_text(), (2400, 1080))
        if result["status"] == "checked"
        else None
    )
    write(readings_path, observed)
    row = {**row, "findings": result["findings"], "coverage": None, "metrics": None}
    matches = None
    if row["scope"] == "labelled":
        screen = next(s for s in reference["screens"] if s["image"] == row["image"])
        labels = [
            Label.model_validate(label)
            for label in read((root / row["image"]).with_suffix(".labels.json"))[
                "labels"
            ]
        ]
        from l10n_checker.vision import Finding

        texts, _ = reference_texts(screen)
        matches = match_screen(
            labels,
            [Finding.model_validate(f) for f in result["findings"]],
            texts,
            result["status"],
            MatchingConfig(),
        )
        row["metrics"] = score_screen(matches).to_dict()
        row["matches"] = [asdict(match) for match in matches.matches]
        row["false_positive_indices"] = list(matches.unmatched_finding_indices)
        row["hallucination_indices"] = list(matches.hallucination_indices)
        row["coverage"] = (
            coverage(screen["rows"], observed) if observed is not None else None
        )
        row["diagnostics"] = read(record / "diagnostics.json")
    native = result["metadata"].get("ocr", {})
    raw = native.get("native_segments", native.get("native_tsv"))
    if raw is None and (record / "ocr.tsv").exists():
        raw = (record / "ocr.tsv").read_text()
    row["fingerprints"] = {
        "native": object_hash(raw),
        "tsv": sha256(record / "ocr.tsv") if (record / "ocr.tsv").exists() else None,
        "readings": object_hash(observed),
        "result": object_hash(
            {key: result[key] for key in ("status", "reason", "findings")}
        ),
        "diagnostics": object_hash(row.get("diagnostics")),
    }
    return row, matches


def summarize(root):
    protocol = validated_protocol(root)
    for name, expected_hash in read(root / EVIDENCE / "record-index.json").items():
        path = (root / name).resolve()
        if not path.is_relative_to(root.resolve()) or sha256(path) != expected_hash:
            raise ValueError(f"Recorded evidence changed: {name}")
    operations = read(root / EVIDENCE / "operations.json")
    expected = {
        (config["id"], repeat, image["path"])
        for config in protocol["grid"]
        for repeat in (1, 2)
        for image in protocol["images"]
    }
    if (
        len(operations) != 84
        or {(r["configuration"], r["pass"], r["image"]) for r in operations} != expected
        or any(r["state"] != "complete" for r in operations)
    ):
        raise ValueError(
            "The experiment ledger is incomplete or contains unexpected operations"
        )
    reference = read(root / REFERENCE_SOURCE)
    rows, matched = [], {}
    for operation in operations:
        expected_record = (
            Path(EVIDENCE)
            / "records"
            / operation["configuration"]
            / f"pass-{operation['pass']}"
            / Path(operation["image"]).stem
        )
        if operation["record"] != str(expected_record):
            raise ValueError("Unexpected record path in the experiment ledger")
        row, matches = evaluate(root, operation, reference)
        rows.append(row)
        if matches is not None:
            matched.setdefault((row["configuration"], row["pass"]), []).append(matches)
    comparisons = []
    for config in protocol["grid"]:
        for image in protocol["images"]:
            pair = [
                r
                for r in rows
                if r["configuration"] == config["id"] and r["image"] == image["path"]
            ]
            different = [
                key
                for key in pair[0]["fingerprints"]
                if pair[0]["fingerprints"][key] != pair[1]["fingerprints"][key]
            ]
            comparisons.append(
                {
                    "configuration": config["id"],
                    "image": image["path"],
                    "differences": different,
                }
            )
    totals = []
    for config in protocol["grid"]:
        for repeat in (1, 2):
            selected = [
                r
                for r in rows
                if r["configuration"] == config["id"] and r["pass"] == repeat
            ]
            labelled = [r for r in selected if r["scope"] == "labelled"]
            complete_coverage = all(r["coverage"] is not None for r in labelled)
            totals.append(
                {
                    "configuration": config["id"],
                    "pass": repeat,
                    "metrics": score_screens(matched[config["id"], repeat]).to_dict(),
                    "clean_fp": sum(
                        r["metrics"]["fp"]
                        for r in labelled
                        if "__clean__" in r["image"]
                    ),
                    "primary_exact": sum(
                        r["coverage"]["primary"]["exact_count"]
                        for r in labelled
                        if r["coverage"] is not None
                    )
                    if complete_coverage
                    else None,
                    "primary_fuzzy": sum(
                        r["coverage"]["primary"]["fuzzy_count"]
                        for r in labelled
                        if r["coverage"] is not None
                    )
                    if complete_coverage
                    else None,
                    "coverage_available_images": sum(
                        r["coverage"] is not None for r in labelled
                    ),
                    "primary_reference_count": 56,
                    "operation_s": sum(r["operation_s"] for r in selected),
                    "initialization_s": sum(r["initialization_s"] for r in selected),
                }
            )
    summary = {
        "status": "preliminary",
        "scope": "Three labelled images from one source screen; four qualitative-only images.",
        "protocol_sha256": PROTOCOL_SHA256,
        "environment_sha256": sha256(root / EVIDENCE / "environment.json"),
        "reference_sha256": protocol["reference_sha256"],
        "reference_limitations": "D-037: #10 is not an exhaustive occurrence map; supplied clipped/numeric diagnostics only, no OCR-derived additions. Hallucination counts inherit its gaps.",
        "provider_requests": 0,
        "api_spend_usd": 0,
        "rows": rows,
        "totals": totals,
        "repeatability": comparisons,
    }
    write(root / EVIDENCE / "summary.json", summary)
    output = [
        "# Preliminary OCR comparison",
        "",
        summary["scope"],
        "",
        "| Config | Pass | TP / FP / FN | Clean FP | Exact /56 | Fuzzy /56 | Coverage images | 7-image seconds | Init seconds |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for total in totals:
        m = total["metrics"]
        output.append(
            f"| {total['configuration']} | {total['pass']} | {m['tp']} / {m['fp']} / {m['fn']} | {total['clean_fp']} | {total['primary_exact']} | {total['primary_fuzzy']} | {total['coverage_available_images']}/3 | {total['operation_s']:.3f} | {total['initialization_s']:.3f} |"
        )
    output += [
        "",
        "Failed transcription is unavailable; counts above cover only available images.",
        "Primary denominators are 16/20/20. Clipped diagnostics remain separate in summary.json.",
        "",
        f"Repeat differences: {sum(bool(r['differences']) for r in comparisons)}/42 image/configuration pairs.",
        "",
        summary["reference_limitations"],
        "",
        "Per-image metrics, all findings, Mining rules, coverage matches and runtime: summary.json.",
        "No Stage 2 detection metrics or coverage were computed. API requests/spend: 0.",
    ]
    (root / EVIDENCE / "comparison.md").write_text("\n".join(output) + "\n")
    print("Offline summary written; no OCR executed by summarize.", flush=True)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare-models", "run", "summarize"))
    parser.add_argument("--unciv-fork", type=Path)
    parser.add_argument("--model-dir", type=Path, default=Path("data/ocr-models"))
    args = parser.parse_args()
    root = Path.cwd().resolve()
    if args.action == "prepare-models":
        prepare_models(root, args.model_dir.resolve())
    elif args.action == "run":
        if args.unciv_fork is None:
            parser.error("run requires --unciv-fork")
        run_experiment(root, args.unciv_fork.resolve(), args.model_dir.resolve())
    else:
        summarize(root)


if __name__ == "__main__":
    main()
