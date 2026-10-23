"""Engine-backed candidates and explicitly human-confirmed reference exports."""

import html
import io
import shutil
from pathlib import Path
from typing import Literal

from PIL import Image
from pydantic import field_validator

from l10n_checker.capture import CaptureError
from l10n_checker.screen_manifest import Hash, StrictModel, digest, json_bytes
from l10n_checker.text_dump import (
    Rect,
    canonical_bytes,
    grid_region,
    load_dump,
    rectangle,
    rgba_digest,
)

Region = Literal[
    "top-left",
    "top",
    "top-right",
    "left",
    "center",
    "right",
    "bottom-left",
    "bottom",
    "bottom-right",
]


class Row(StrictModel):
    id: str
    section: str
    region: Region
    text_seen: str
    visibility: str
    primary_denominator: bool
    bounds: Rect | None
    owner_bounds: Rect | None
    clip_bounds: Rect | None
    visible_bounds: Rect | None
    source: Literal["engine", "human"]
    human_edited: bool
    element_ids: list[str]
    source_keys: list[str]
    input_text: str | None
    ellipsis_applied: bool
    overflow_x: bool
    overflow_y: bool
    warnings: list[str]

    _rect = field_validator("bounds", "owner_bounds", "clip_bounds", "visible_bounds")(
        rectangle
    )


class Candidate(StrictModel):
    candidate_version: Literal[1]
    status: Literal["candidate_awaiting_Anton_confirmation"]
    parent_candidate_sha256: Hash | None
    capture_pair_sha256: Hash
    screen: str
    language: str
    build_version_code: int
    image: dict
    dump: dict
    rows: list[Row]
    limitations: list[str]


def read_json(path):
    return json_bytes(path.read_bytes())


def child(root: Path, name: str) -> Path:
    path = (root / name).resolve()
    if Path(name).is_absolute() or not path.is_relative_to(root.resolve()):
        raise CaptureError("Artifact path escapes its directory")
    return path


def load_pair(path: Path):
    pair = read_json(path)
    if pair.get("pair_version") != 1 or pair.get("protocol_version") != 2:
        raise CaptureError("A committed protocol v2 PNG/dump pair is required")
    png = child(path.parent, pair["png"]).read_bytes()
    raw_dump = child(path.parent, pair["dump"]).read_bytes()
    if (
        digest(png) != pair["png_sha256"]
        or digest(raw_dump) != pair["dump_sha256"]
        or rgba_digest(png) != pair["rgba_sha256"]
    ):
        raise CaptureError("Capture pair hash mismatch")
    with Image.open(io.BytesIO(png)) as image:
        size = list(image.size)
    dump = load_dump(
        raw_dump,
        expected={
            "screen": pair["screen"],
            "language": pair["language"],
            "state_sha256": pair["state_sha256"],
            "image_size": size,
            "build_version_code": int(pair["build"]["version_code"]),
        },
    )
    return pair, png, raw_dump, dump


def ordinary_text(text: str, warnings: list[str]) -> str:
    """Remove only engine-identified icons, preserving rendered line breaks."""
    icon_codes = set()
    for warning in warnings:
        if warning.startswith("icon_glyph:"):
            try:
                icon_codes.add(int(warning.removeprefix("icon_glyph:"), 16))
            except ValueError:
                continue
    visible = "".join(c for c in text if ord(c) not in icon_codes)
    return "\n".join(" ".join(line.split()) for line in visible.split("\n")).strip()


def candidate_for(pair_path: Path) -> dict:
    pair, png, raw, dump = load_pair(pair_path)
    rows = []
    for element in dump.elements:
        if element.decoration or element.visibility == "hidden":
            continue
        fragments = []
        if element.visibility == "full":
            fragments = [element.display_text]
        else:
            for line in element.lines:
                span = ""
                for glyph in line.glyphs:
                    if glyph.visibility == "full":
                        span += glyph.text
                    else:
                        if span.strip():
                            fragments.append(span)
                        span = ""
                if span.strip():
                    fragments.append(span)
            if not fragments:
                fragments = [
                    ""
                ]  # Explicit unresolved visible fragment for human review.
        draws = [e.id for e in dump.elements if e.logical_id == element.logical_id]
        for index, fragment in enumerate(fragments):
            text = ordinary_text(fragment, element.warnings)
            if not text and element.visibility == "full":
                continue
            warning = list(element.warnings)
            if element.visibility != "full":
                warning.append(
                    "Clipped unit: confirm visible spans; hidden input is provenance only"
                )
            primary = (
                element.visibility == "full"
                and element.bounds is not None
                and any(c.isalpha() for c in text)
                # Provenance/formatting warnings do not make visible text uncertain.
                and not [
                    w
                    for w in warning
                    if w not in ("source_unavailable", "markup_input")
                    and not w.startswith("icon_glyph:")
                ]
            )
            rows.append(
                {
                    "id": f"{element.id}:fragment-{index}"
                    if len(fragments) > 1
                    else element.id,
                    "section": element.actor_path or "unmapped",
                    "region": grid_region(element.glyph_bounds, dump.image_size),
                    "text_seen": text,
                    "visibility": element.visibility,
                    "primary_denominator": primary,
                    "bounds": element.glyph_bounds,
                    "visible_bounds": element.visible_bounds,
                    "owner_bounds": element.bounds,
                    "clip_bounds": element.clip_bounds,
                    "source": "engine",
                    "human_edited": False,
                    "element_ids": draws,
                    "source_keys": list(
                        dict.fromkeys(
                            ([element.source_key] if element.source_key else [])
                            + element.source_keys
                        )
                    ),
                    "input_text": element.input_text,
                    "ellipsis_applied": element.ellipsis_applied,
                    "overflow_x": element.overflow_x,
                    "overflow_y": element.overflow_y,
                    "warnings": warning,
                }
            )
    value = {
        "candidate_version": 1,
        "status": "candidate_awaiting_Anton_confirmation",
        "parent_candidate_sha256": None,
        "capture_pair_sha256": digest(pair_path.read_bytes()),
        "screen": dump.screen,
        "language": dump.language,
        "build_version_code": dump.build_version_code,
        "image": {
            "file": pair["png"],
            "sha256": digest(png),
            "rgba_sha256": pair["rgba_sha256"],
            "size": dump.image_size,
        },
        "dump": {"file": pair["dump"], "sha256": digest(raw)},
        "rows": rows,
        "limitations": [
            "Engine candidates require Anton's confirmation; no defect labels.",
            "Draw/scissor visibility cannot establish occlusion by later opaque actors.",
            "Clipped, numeric and uncertain units are diagnostics until human review.",
        ],
    }
    Candidate.model_validate(value)
    return value


def review_one(pair_path: Path, folder: Path) -> Path:
    candidate = candidate_for(pair_path)
    folder.mkdir(parents=True, exist_ok=False)
    for entry in (candidate["image"], candidate["dump"]):
        source = child(pair_path.parent, entry["file"])
        # Flatten filenames in the review bundle, preserving exact bytes.
        if source.name != entry["file"]:
            raise CaptureError("Capture pair artifacts must share its directory")
        shutil.copyfile(source, folder / source.name)
    shutil.copyfile(pair_path, folder / "capture.pair.json")
    data = canonical_bytes(candidate)
    (folder / "candidate.json").write_bytes(data)
    from l10n_checker.reference_page import render_page

    (folder / "review.html").write_text(render_page(candidate, data), encoding="utf-8")
    return folder / "review.html"


def review_run(capture: Path, folder: Path) -> dict:
    summary = read_json(capture / "summary.json")
    folder.mkdir(parents=True, exist_ok=False)
    results = []
    for record in summary["records"]:
        if record["pass"] != 1:
            continue
        name = f"{record['screen']}__{record['language']}"
        if not name or any(
            c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_."
            for c in name
        ):
            raise CaptureError("Invalid review directory name")
        entry = {"screen": record["screen"], "language": record["language"]}
        if record["status"] != "captured" or "pair" not in record:
            entry.update(
                status="unavailable", reason=record.get("reason", "No v2 pair")
            )
        else:
            page = review_one(child(capture, record["pair"]), folder / name)
            entry.update(status="candidate", page=str(page.relative_to(folder)))
        results.append(entry)
    links = "".join(
        f'<li><a href="{html.escape(r["page"])}">{html.escape(r["screen"] + " / " + r["language"])}</a> — candidate</li>'
        if r["status"] == "candidate"
        else f"<li>{html.escape(r['screen'] + ' / ' + r['language'])} — unavailable: {html.escape(r['reason'])}</li>"
        for r in results
    )
    (folder / "index.html").write_text(
        '<!doctype html><meta charset="utf-8"><title>Engine reference review</title>'
        "<h1>Engine reference candidates</h1><p>Every screen needs Anton’s confirmation.</p>"
        + f"<p>Capture run status: {html.escape(summary['status'])}</p><ul>"
        + links
        + "</ul>",
        encoding="utf-8",
    )
    report = {
        "status": "candidates_only",
        "input_capture_status": summary["status"],
        "screens": results,
        "live_provider_requests": 0,
        "api_spend_usd": 0,
    }
    (folder / "review-index.json").write_bytes(canonical_bytes(report))
    return report


def compare_capture_runs(current: Path, reference: Path) -> dict:
    """Compare all recorded new PNGs to their 1271045 counterparts, offline."""
    from l10n_checker.screen_capture import compare_pixels

    new = read_json(current / "summary.json")
    old = read_json(reference / "summary.json")
    if old.get("observed_build", {}).get("version_code") != "1271045":
        raise CaptureError("Expected the original 1271045 capture reference")
    index = {}
    for record in old["records"]:
        key = (record["screen"], record["language"], record["pass"])
        if key in index:
            raise CaptureError("Duplicate comparison reference record")
        index[key] = record
    results = []
    for record in new["records"]:
        key = (record["screen"], record["language"], record["pass"])
        previous = index.get(key, {})
        entry = {
            "screen": key[0],
            "language": key[1],
            "pass": key[2],
            "status": "unavailable",
        }
        if record.get("status") == previous.get("status") == "captured":
            paths = [
                child(root, row["png"])
                for root, row in ((current, record), (reference, previous))
            ]
            if any(
                digest(path.read_bytes()) != row["png_sha256"]
                for path, row in zip(paths, (record, previous))
            ):
                raise CaptureError("PNG changed since capture summary")
            entry.update(compare_pixels(*paths))
        results.append(entry)
    complete = (
        bool(results)
        and new.get("status") == old.get("status") == "complete"
        and len(results) == len(index)
        and len({(r["screen"], r["language"], r["pass"]) for r in results})
        == len(results)
        and all(r["status"] == "identical" for r in results)
    )
    return {
        "status": "identical" if complete else "failed",
        "comparisons": results,
        "current_summary_sha256": digest((current / "summary.json").read_bytes()),
        "reference_summary_sha256": digest((reference / "summary.json").read_bytes()),
    }


def confirm_bundle(review: Path, bundle: Path, output: Path) -> dict:
    """Validate an explicit browser export, never synthesize human approval."""
    original_bytes = (review / "candidate.json").read_bytes()
    original = Candidate.model_validate(json_bytes(original_bytes)).model_dump()
    package = read_json(bundle)
    data = package["candidate_json"].encode("utf-8")
    candidate = Candidate.model_validate(json_bytes(data)).model_dump()
    approval = package["approval"]
    if not (
        approval.get("status") == "confirmed"
        and approval.get("accepted_by") == "Anton"
        and approval.get("candidate_sha256") == digest(data)
        and approval.get("initial_candidate_sha256") == digest(original_bytes)
    ):
        raise CaptureError("Missing or mismatched Anton confirmation")
    for key in (
        "capture_pair_sha256",
        "screen",
        "language",
        "build_version_code",
        "image",
        "dump",
    ):
        if candidate[key] != original[key]:
            raise CaptureError(f"Reviewed provenance changed: {key}")
    if data != original_bytes and candidate["parent_candidate_sha256"] != digest(
        original_bytes
    ):
        raise CaptureError("Edited candidate must name its original hash")
    if (
        approval.get("image_sha256") != candidate["image"]["sha256"]
        or approval.get("dump_sha256") != candidate["dump"]["sha256"]
    ):
        raise CaptureError("Approval image/dump binding mismatch")
    pair_path = review / "capture.pair.json"
    if digest(pair_path.read_bytes()) != candidate["capture_pair_sha256"]:
        raise CaptureError("Reviewed capture pair changed")
    load_pair(pair_path)  # Independent readback of original PNG and raw dump.
    timing = approval["timing"]
    if (
        not timing.get("started_at")
        or not timing.get("finished_at")
        or not 0 <= timing["active_seconds"] <= timing["elapsed_seconds"]
        or timing["elapsed_seconds"] <= 0
    ):
        raise CaptureError("Invalid explicit review timing")
    rows = candidate["rows"]
    if len({r["id"] for r in rows}) != len(rows) or any(
        not r["text_seen"].strip() for r in rows
    ):
        raise CaptureError("Resolve empty text/duplicate row ids before confirmation")
    projection = [
        {
            "id": r["id"],
            "text": r["text_seen"],
            "region": r["region"],
            "visibility": r["visibility"],
            "primary_denominator": r["primary_denominator"],
        }
        for r in rows
    ]
    result = {
        "status": "confirmed",
        "reference_sha256": digest(data),
        "screen": candidate["screen"],
        "language": candidate["language"],
        "image": candidate["image"],
        "dump": candidate["dump"],
        "rows": rows,
        "screen_texts": [r["text"] for r in projection],
        "screen_texts_source": projection,
        "limitations": candidate["limitations"],
    }
    output.mkdir(parents=True, exist_ok=False)
    for entry in (candidate["image"], candidate["dump"]):
        source = child(review, entry["file"])
        shutil.copyfile(source, output / source.name)
    shutil.copyfile(pair_path, output / "capture.pair.json")
    (output / "initial-candidate.json").write_bytes(original_bytes)
    (output / "reviewed-candidate.json").write_bytes(data)
    (output / "approval.json").write_bytes(canonical_bytes(approval))
    (output / "reference.json").write_bytes(canonical_bytes(result))
    return result
