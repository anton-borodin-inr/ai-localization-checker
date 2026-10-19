"""Offline OCR + source-translation baseline, independent of human labels."""

import csv
import hashlib
import io
import json
import math
import re
import shutil
import subprocess
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from l10n_checker.capture import CaptureError, png_size
from l10n_checker.unciv_text import RenderingError, TranslationTable
from l10n_checker.vision import CheckResult, Finding, new_run_id

SETTINGS = {
    "version": "baseline-v0",
    "oem": 1,
    "psm": 11,
    "languages": {"en": "eng", "de": "deu+eng"},
    "timeout_s": 30,
    "exact_match": "NFKC + casefold + whitespace collapse",
    "prefix_min_letters": 4,
    "prefix_min_fraction": 0.5,
    "missing_confidence": 0.5,
    "ocr_confidence_filter": None,
}
GRID = (
    ("top-left", "top", "top-right"),
    ("left", "center", "right"),
    ("bottom-left", "bottom", "bottom-right"),
)
TRANSLATIONS = "android/assets/jsons/translations/"


class BaselineError(ValueError):
    pass


class Slot(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)
    request: str = Field(min_length=1)
    box: tuple[float, float, float, float]
    source: str = Field(min_length=1)

    @model_validator(mode="after")
    def valid_box(self):
        x1, y1, x2, y2 = self.box
        if not (0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1):
            raise ValueError("box must be ordered normalized screen coordinates")
        return self


class Inventory(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: int = Field(ge=1, le=1)
    screen: str
    base_commit: str
    context: str
    slots: list[Slot] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_ids(self):
        if len({slot.id for slot in self.slots}) != len(self.slots):
            raise ValueError("slot ids must be unique")
        return self


@dataclass(frozen=True)
class Word:
    text: str
    left: int
    top: int
    width: int
    height: int
    confidence: float
    line: tuple[int, int, int, int]

    @property
    def box(self):
        return self.left, self.top, self.left + self.width, self.top + self.height


@dataclass
class OcrOutput:
    tsv: str
    metadata: dict


class OcrEngine(Protocol):
    def recognize(self, image: Path, language: str) -> OcrOutput: ...


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def normalize(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def parse_tsv(tsv: str, size: tuple[int, int]) -> list[Word]:
    reader = csv.DictReader(io.StringIO(tsv), delimiter="\t", quoting=csv.QUOTE_NONE)
    required = {
        "level",
        "page_num",
        "block_num",
        "par_num",
        "line_num",
        "word_num",
        "left",
        "top",
        "width",
        "height",
        "conf",
        "text",
    }
    if set(reader.fieldnames or []) != required:
        raise BaselineError("Invalid OCR TSV header")
    words = []
    for row in reader:
        if None in row or any(value is None for value in row.values()):
            raise BaselineError("Malformed OCR TSV row")
        if int(row["level"]) != 5 or not row["text"].strip():
            continue
        left, top, width, height = (
            int(row[k]) for k in ("left", "top", "width", "height")
        )
        conf = float(row["conf"])
        if not (
            left >= 0
            and top >= 0
            and width > 0
            and height > 0
            and left + width <= size[0]
            and top + height <= size[1]
            and math.isfinite(conf)
            and 0 <= conf <= 100
        ):
            raise BaselineError("Invalid OCR word geometry or confidence")
        line = tuple(
            int(row[k]) for k in ("page_num", "block_num", "par_num", "line_num")
        )
        words.append(Word(row["text"], left, top, width, height, conf / 100, line))
    if not words:
        raise BaselineError("OCR returned no usable text for a text-bearing screen")
    return words


class Tesseract:
    def __init__(self, executable: str = "tesseract"):
        self.executable = executable

    def recognize(self, image: Path, language: str) -> OcrOutput:
        executable = shutil.which(self.executable)
        if executable is None:
            raise BaselineError("Tesseract executable is missing")

        def run(*args):
            return subprocess.run(
                [executable, *args],
                capture_output=True,
                text=True,
                check=True,
                timeout=SETTINGS["timeout_s"],
            ).stdout

        version_lines = run("--version").splitlines()
        if not version_lines:
            raise BaselineError("Tesseract returned no version")
        version = version_lines[0]
        available = run("--list-langs")
        match = re.search(r'in "([^"]+)"', available)
        if not match:
            raise BaselineError("Cannot locate Tesseract language data for provenance")
        data_dir = Path(match[1])
        languages = SETTINGS["languages"][language]
        hashes = {}
        for lang in languages.split("+"):
            if lang not in available.splitlines()[1:]:
                raise BaselineError(f"Tesseract language data is missing: {lang}")
            hashes[lang] = digest((data_dir / f"{lang}.traineddata").read_bytes())
        tsv = run(
            str(image),
            "stdout",
            "--tessdata-dir",
            str(data_dir),
            "--oem",
            str(SETTINGS["oem"]),
            "--psm",
            str(SETTINGS["psm"]),
            "-l",
            languages,
            "tsv",
        )
        return OcrOutput(
            tsv,
            {"engine": version, "languages": languages, "traineddata_sha256": hashes},
        )


def git_file(fork: Path, commit: str, path: str) -> bytes:
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise BaselineError("Source commit must be a full immutable SHA")
    return subprocess.run(
        ["git", "-C", str(fork), "show", f"{commit}:{path}"],
        capture_output=True,
        check=True,
        timeout=10,
    ).stdout


def resolve_inputs(image: Path, manifest_path: Path, inventory_path: Path, fork: Path):
    for path in (image, manifest_path, inventory_path):
        if path.name.endswith(".labels.json") or path.name == ".env":
            raise BaselineError("Human labels and secret files are not baseline inputs")
    image_bytes = image.read_bytes()
    size = png_size(image_bytes)
    fields = image.stem.split("__")
    if len(fields) != 5:
        raise BaselineError("Screenshot must have the D-003 five-field filename")
    screen, lang, resolution, variant, code = fields
    if lang not in SETTINGS["languages"] or resolution != f"{size[0]}x{size[1]}":
        raise BaselineError("Screenshot language or resolution is inconsistent")
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    # Do not access human_label*, visual_observation or accepted_defect_boundary.
    captures = [c for c in manifest["captures"] if c["file"] == image.name]
    builds = [b for b in manifest["builds"].values() if str(b["version_code"]) == code]
    if len(captures) != 1 or len(builds) != 1:
        raise BaselineError("Screenshot/build provenance is missing or ambiguous")
    capture, build = captures[0], builds[0]
    if not (
        capture["sha256"] == digest(image_bytes)
        and capture["png_size"] == list(size)
        and str(capture["version_code"]) == code
        and capture["variant"] == variant
        and capture["language"] == {"en": "English", "de": "German"}[lang]
        and build["base_commit"] == manifest["base_commit"]
        and build["kind"] == {"clean": "clean", "injected": "defective"}.get(variant)
    ):
        raise BaselineError("Screenshot contradicts its recorded provenance")
    inventory_bytes = inventory_path.read_bytes()
    inventory = Inventory.model_validate_json(inventory_bytes)
    if inventory.screen != screen or inventory.base_commit != build["base_commit"]:
        raise BaselineError("Screen inventory does not match source base/screen")
    commit = build["fork_commit"]
    config = git_file(fork, commit, "buildSrc/src/main/kotlin/BuildConfig.kt").decode()
    if not re.search(rf"appCodeNumber\s*=\s*{re.escape(code)}\b", config):
        raise BaselineError("Source versionCode does not match screenshot")
    tables, sources = {}, {}
    for language, filename in (
        ("en", "English.properties"),
        ("de", "German.properties"),
    ):
        path = TRANSLATIONS + filename
        content = git_file(fork, commit, path)
        tables[language] = TranslationTable.parse(content.decode("utf-8"))
        sources[language] = {"path": path, "sha256": digest(content)}
    metadata = {
        "image": {"name": image.name, "sha256": digest(image_bytes), "size": size},
        "version_code": int(code),
        "fork_commit": commit,
        "base_commit": build["base_commit"],
        "translations": sources,
        "manifest_sha256": digest(manifest_bytes),
        "inventory_sha256": digest(inventory_bytes),
        "language": lang,
    }
    return size, lang, inventory, tables, metadata


def region(box: tuple[float, float, float, float], size: tuple[int, int]) -> str:
    x = (box[0] + box[2]) / (2 * size[0])
    y = (box[1] + box[3]) / (2 * size[1])
    return GRID[min(2, max(0, int(y * 3)))][min(2, max(0, int(x * 3)))]


def union(words: list[Word]):
    return (
        min(w.box[0] for w in words),
        min(w.box[1] for w in words),
        max(w.box[2] for w in words),
        max(w.box[3] for w in words),
    )


def spans(words: list[Word]):
    # A slot contains one UI text widget or one source fragment of it. Keep TSV
    # reading order, including wrapped lines, without joining distant widgets.
    for start in range(len(words)):
        for end in range(start + 1, len(words) + 1):
            part = words[start:end]
            yield " ".join(w.text for w in part), part


def detect(inventory: Inventory, tables: dict, language: str, words: list[Word], size):
    findings, diagnostics = [], []
    foreign_language = "en" if language == "de" else "de"
    for slot in inventory.slots:
        lookup_start = len(tables[language].lookups)
        expected = tables[language].render(slot.request)
        lookups = tables[language].lookups[lookup_start:]
        foreign = tables[foreign_language].render(slot.request)
        missing_translation = language == "de" and any(
            key in tables["en"].entries
            and (not (entry := tables["de"].entries.get(key)) or entry[1] is None)
            for key in lookups
        )
        expected_norm, foreign_norm = normalize(expected), normalize(foreign)
        if not expected_norm:
            raise BaselineError(f"Empty expectation: {slot.id}")
        pixel_box = tuple(v * size[i % 2] for i, v in enumerate(slot.box))
        local = [
            w
            for w in words
            if pixel_box[0] <= (w.box[0] + w.box[2]) / 2 <= pixel_box[2]
            and pixel_box[1] <= (w.box[1] + w.box[3]) / 2 <= pixel_box[3]
        ]
        candidates = list(spans(local))
        exact = next(
            ((t, ws) for t, ws in candidates if normalize(t) == expected_norm), None
        )
        broken = next(
            ((t, ws) for t, ws in candidates if re.search(r"\[[^\]]+\]", t)), None
        )
        foreign_match = (
            next(
                ((t, ws) for t, ws in candidates if normalize(t) == foreign_norm), None
            )
            if foreign_norm != expected_norm
            else None
        )
        prefix = []
        for text, part in candidates:
            norm = normalize(text).removesuffix("...").removesuffix("…").rstrip()
            if (
                norm
                and expected_norm.startswith(norm)
                and norm != expected_norm
                and sum(c.isalpha() for c in norm) >= SETTINGS["prefix_min_letters"]
                and len(norm) / len(expected_norm) >= SETTINGS["prefix_min_fraction"]
            ):
                prefix.append((text, part))
        diag = {
            "slot": slot.id,
            "request": slot.request,
            "expected": expected,
            "foreign": foreign,
            "box": slot.box,
            "source": slot.source,
        }
        if broken:
            kind, evidence, rule = "other", broken, "literal_placeholder"
        elif exact and missing_translation:
            kind, evidence, rule = "untranslated", exact, "source_fallback"
        elif exact:
            diagnostics.append({**diag, "rule": "exact", "text_seen": exact[0]})
            continue
        elif foreign_match:
            kind, evidence, rule = "untranslated", foreign_match, "known_foreign_text"
        elif prefix:
            kind, evidence, rule = (
                "truncated_text",
                max(prefix, key=lambda p: len(p[0])),
                "prefix",
            )
        else:
            kind, evidence, rule = "truncated_text", None, "missing"
        text, evidence_words = evidence if evidence else ("", [])
        finding = Finding(
            defect_type=kind,
            text_seen=text,
            region=region(union(evidence_words) if evidence_words else pixel_box, size),
            confidence=sum(w.confidence for w in evidence_words) / len(evidence_words)
            if evidence_words
            else SETTINGS["missing_confidence"],
        )
        findings.append(finding)
        diagnostics.append({**diag, "rule": rule, "finding_index": len(findings) - 1})
    return findings, diagnostics


def run_baseline(
    image: Path,
    manifest: Path,
    inventory: Path,
    fork: Path,
    runs_dir: Path,
    engine: OcrEngine | None = None,
) -> tuple[CheckResult, Path]:
    run_dir = runs_dir / new_run_id()
    run_dir.mkdir(parents=True)
    started = time.monotonic()
    metadata = {
        "detector": "ocr-translation-baseline",
        "settings": SETTINGS,
        "requests_sent": 0,
        "run_id": run_dir.name,
    }
    diagnostics, findings = [], []
    reason = None
    try:
        size, lang, slots, tables, provenance = resolve_inputs(
            image, manifest, inventory, fork
        )
        metadata.update(provenance)
        output = (engine or Tesseract()).recognize(image, lang)
        # Validate fake/custom engine output through the same parser as real OCR.
        metadata["ocr"] = output.metadata
        (run_dir / "ocr.tsv").write_text(output.tsv, encoding="utf-8")
        words = parse_tsv(output.tsv, size)
        findings, diagnostics = detect(slots, tables, lang, words, size)
        write_json(
            run_dir / "source-entries.json",
            {lang: table.source_entries() for lang, table in tables.items()},
        )
    except (
        BaselineError,
        RenderingError,
        CaptureError,
        OSError,
        ValueError,
        KeyError,
        TypeError,
        subprocess.SubprocessError,
    ) as exc:
        reason = f"{type(exc).__name__}: {exc}"
        findings = []
    metadata["latency_s"] = round(time.monotonic() - started, 3)
    result = CheckResult(
        status="not_checked" if reason else "checked",
        findings=findings,
        reason=reason,
        metadata=metadata,
    )
    write_json(run_dir / "diagnostics.json", diagnostics)
    write_json(run_dir / "run.json", metadata)
    (run_dir / "result.json").write_text(
        result.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    return result, run_dir


def write_json(path: Path, data) -> None:
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
