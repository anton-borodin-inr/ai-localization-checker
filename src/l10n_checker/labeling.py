"""Stage 3 dev-set label drafting and confirmed-export writer (D-062).

Drafts come only from the accepted run's mutation manifest and acceptance.json,
never from a detector or LLM. Final `.labels.json` files are written only from
an export in which every screenshot is marked reviewed and every label passes
schema v2 validation via `matching.load_labels`.
"""

import json
import math
import re
import shutil
from collections.abc import Sequence
from pathlib import Path

from l10n_checker.capture import REPO_ROOT, png_size
from l10n_checker.matching import load_labels
from l10n_checker.text_dump import grid_region
from l10n_checker.text_reference import ordinary_text
from l10n_checker.vision import screenshot_language

DEFAULT_IMAGE_SIZE = (2400, 1080)
DEFAULT_SPLIT_PATH = REPO_ROOT / "fixtures" / "stage2" / "split.json"
DEFECT_TYPES = ("overflow", "wrong_language", "truncated_text", "other")
REGIONS = (
    "top-left",
    "top",
    "top-right",
    "left",
    "center",
    "right",
    "bottom-left",
    "bottom",
    "bottom-right",
)

# LibGDX color markup only; literal placeholders such as [amount] stay intact.
_COLOR_MARKUP = re.compile(
    r"\[(?:RED|GREEN|BLUE|WHITE|BLACK|YELLOW|ORANGE|GRAY|GREY|#[0-9a-fA-F]{6,8})\]|\[\]"
)


def region_from_bounds(
    bounds: Sequence[float],
    image_size: Sequence[int] = DEFAULT_IMAGE_SIZE,
) -> str:
    """Return the 3x3 grid cell containing the centre of `bounds` (D-025)."""
    if len(bounds) != 4 or not all(
        isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
        for v in bounds
    ):
        raise ValueError(f"Invalid bounds rectangle: {bounds!r}")
    if bounds[2] < bounds[0] or bounds[3] < bounds[1]:
        raise ValueError(f"Reversed bounds rectangle: {bounds!r}")
    if len(image_size) != 2 or any(type(v) is not int or v <= 0 for v in image_size):
        raise ValueError(f"Invalid image size: {image_size!r}")
    return grid_region([float(v) for v in bounds], [int(v) for v in image_size])


def _load_holdout_screens(split_path: Path | None) -> set[str]:
    if split_path is None:
        return set()
    data = json.loads(split_path.read_text(encoding="utf-8"))
    holdout = data.get("holdout")
    if not isinstance(holdout, list) or not all(isinstance(s, str) for s in holdout):
        raise ValueError(f"Invalid split file: {split_path}")
    return set(holdout)


def _clean_expected_input(text: str, warnings: Sequence[str]) -> str:
    return ordinary_text(_COLOR_MARKUP.sub("", text), list(warnings))


def draft_label_from_occurrence(
    occurrence: dict,
    *,
    image_size: Sequence[int] = DEFAULT_IMAGE_SIZE,
) -> dict:
    """Map one qualified manifest occurrence to a draft label (D-062)."""
    if occurrence.get("qualified") is not True:
        raise ValueError("Cannot draft a label from an unqualified occurrence")
    defect_type = occurrence.get("intended_class")
    if defect_type not in DEFECT_TYPES:
        raise ValueError(f"Unsupported intended class: {defect_type!r}")
    before = occurrence["before"]
    after = occurrence["after"]
    before_warnings = before.get("warnings") or []
    after_warnings = after.get("warnings") or []

    text_seen = ordinary_text(after["display_text"], list(after_warnings))
    if defect_type == "truncated_text":
        raw_expected = occurrence.get("expected_input_text")
        if raw_expected is None:
            raw_expected = after.get("input_text")
        if not isinstance(raw_expected, str):
            raise ValueError("Truncated occurrence is missing expected_input_text")
        text_expected = _clean_expected_input(raw_expected, after_warnings)
        note: str | None = None
    elif defect_type == "overflow":
        text_expected = text_seen
        note = None
    elif defect_type == "wrong_language":
        text_expected = ordinary_text(before["display_text"], list(before_warnings))
        note = None
    else:  # "other"
        text_expected = ordinary_text(before["display_text"], list(before_warnings))
        note = "broken placeholder"

    if not text_seen or not text_expected:
        raise ValueError(
            f"Empty draft text for occurrence {occurrence.get('recipe_id')!r}"
        )

    glyph_bounds = after["glyph_bounds"]
    owner_bounds = after.get("bounds")
    region = region_from_bounds(glyph_bounds, image_size)

    return {
        "source": "manifest",
        "recipe_id": occurrence.get("recipe_id"),
        "actor_path": occurrence.get("actor_path"),
        "defect_type": defect_type,
        "text_expected": text_expected,
        "text_seen": text_seen,
        "region": region,
        "note": note or "",
        "glyph_bounds": glyph_bounds,
        "owner_bounds": owner_bounds,
        "confirmed": False,
    }


def _accepted_entries(acceptance_path: Path) -> tuple[dict, list[dict]]:
    acceptance = json.loads(acceptance_path.read_text(encoding="utf-8"))
    decisions = acceptance.get("decisions")
    if not isinstance(decisions, list):
        raise TypeError("acceptance.json must contain a 'decisions' list")
    accepted = [d for d in decisions if d.get("status") == "accepted"]
    if not accepted:
        raise ValueError("No accepted screenshots in acceptance.json")
    seen: set[str] = set()
    for entry in accepted:
        png = entry.get("png")
        if not isinstance(png, str) or Path(png).name != png:
            raise ValueError(f"Invalid PNG name in acceptance.json: {png!r}")
        if png in seen:
            raise ValueError(f"Duplicate accepted PNG in acceptance.json: {png}")
        seen.add(png)
    return acceptance, accepted


def build_drafts(
    run_dir: Path,
    *,
    split_path: Path | None = DEFAULT_SPLIT_PATH,
) -> dict:
    """Build per-screenshot label drafts for all accepted screenshots in `run_dir`."""
    acceptance_path = run_dir / "acceptance.json"
    manifest_path = run_dir / "mutation-manifest.json"
    run_json_path = run_dir / "run.json"

    acceptance, accepted = _accepted_entries(acceptance_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    run_meta = (
        json.loads(run_json_path.read_text(encoding="utf-8"))
        if run_json_path.is_file()
        else {}
    )
    holdout = _load_holdout_screens(split_path)

    manifest_screenshots = manifest.get("screenshots")
    if not isinstance(manifest_screenshots, list):
        raise TypeError("mutation-manifest.json must contain a 'screenshots' list")
    by_png = {
        entry["png"]: entry
        for entry in manifest_screenshots
        if isinstance(entry, dict) and isinstance(entry.get("png"), str)
    }

    screenshots = []
    for decision in accepted:
        png = decision["png"]
        if png not in by_png:
            raise ValueError(f"Accepted PNG missing from mutation-manifest.json: {png}")
        entry = by_png[png]
        png_path = run_dir / png
        if not png_path.is_file():
            raise ValueError(f"Accepted PNG missing on disk: {png_path}")

        file_lang = screenshot_language(png_path)
        screen = png_path.stem.split("__")[0]
        if screen in holdout or entry.get("screen") in holdout:
            raise ValueError(f"Hold-out screen refused: {screen}")
        if entry.get("language") != file_lang:
            raise ValueError(
                f"Language mismatch for {png}: manifest={entry.get('language')!r}, "
                f"filename={file_lang!r}"
            )
        if entry.get("screen") != screen:
            raise ValueError(
                f"Screen mismatch for {png}: manifest={entry.get('screen')!r}, "
                f"filename={screen!r}"
            )

        width, height = png_size(png_path.read_bytes())
        role = entry.get("role")
        if role == "clean":
            draft_labels: list[dict] = []
            review_flags: list[dict] = []
        elif role == "mutation":
            verification = entry.get("verification") or {}
            occurrences = verification.get("occurrences") or []
            draft_labels = []
            for index, occ in enumerate(occurrences, start=1):
                if occ.get("qualified") is not True:
                    continue
                draft = draft_label_from_occurrence(occ, image_size=(width, height))
                draft["id"] = f"draft-{index}"
                draft_labels.append(draft)
            review_flags = list(entry.get("review_flags") or [])
        else:
            raise ValueError(f"Unsupported screenshot role for {png}: {role!r}")

        screenshots.append(
            {
                "png": png,
                "screen": screen,
                "language": file_lang,
                "role": role,
                "batch": entry.get("batch_id", decision.get("batch", "")),
                "image_size": [width, height],
                "review_flags": review_flags,
                "labels": draft_labels,
            }
        )

    return {
        "draft_version": 1,
        "run_id": run_meta.get("run_id") or acceptance.get("run_id", ""),
        "commit": run_meta.get("commit") or acceptance.get("commit", ""),
        "builder_commit": run_meta.get("builder_commit", ""),
        "screenshots": screenshots,
    }


def draft_run(
    run_dir: Path,
    output_html: Path | None = None,
    *,
    split_path: Path | None = DEFAULT_SPLIT_PATH,
) -> Path:
    """Generate the self-contained `label-review.html` next to the PNGs."""
    from l10n_checker.label_page import render_page

    payload = build_drafts(run_dir, split_path=split_path)
    target = output_html if output_html is not None else run_dir / "label-review.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_page(payload), encoding="utf-8")
    return target


def _validate_label_item(item: dict, png: str, index: int) -> dict:
    if not isinstance(item, dict):
        raise TypeError(f"{png}: label #{index} must be an object")
    if item.get("confirmed") is not True:
        raise ValueError(f"{png}: label #{index} is not confirmed")
    defect_type = item.get("defect_type")
    if defect_type not in DEFECT_TYPES:
        raise ValueError(
            f"{png}: label #{index} has invalid defect_type {defect_type!r}"
        )
    region = item.get("region")
    if region not in REGIONS:
        raise ValueError(f"{png}: label #{index} has invalid region {region!r}")

    text_seen = item.get("text_seen")
    text_expected = item.get("text_expected")
    if not isinstance(text_seen, str) or not text_seen.strip():
        raise ValueError(f"{png}: label #{index} has empty text_seen")
    if not isinstance(text_expected, str) or not text_expected.strip():
        raise ValueError(f"{png}: label #{index} has empty text_expected")

    raw_note = item.get("note")
    if raw_note is not None and not isinstance(raw_note, str):
        raise ValueError(f"{png}: label #{index} note must be a string or null")
    note = raw_note.strip() if isinstance(raw_note, str) else ""
    if defect_type == "other" and not note:
        raise ValueError(
            f"{png}: label #{index} with defect_type 'other' requires a note"
        )

    row: dict[str, str] = {
        "defect_type": defect_type,
        "text_expected": text_expected.strip(),
        "text_seen": text_seen.strip(),
        "region": region,
    }
    if note:
        row["note"] = note
    return row


def write_labels(
    export_path: Path,
    output_dir: Path,
    *,
    acceptance_path: Path | None = None,
    copy_pngs_from: Path | None = None,
    split_path: Path | None = DEFAULT_SPLIT_PATH,
) -> list[Path]:
    """Validate Anton's review export and write one `<stem>.labels.json` per PNG."""
    export = json.loads(export_path.read_text(encoding="utf-8"))
    screenshots = export.get("screenshots")
    if not isinstance(screenshots, list) or not screenshots:
        raise ValueError("Export must contain a non-empty 'screenshots' list")

    holdout = _load_holdout_screens(split_path)
    expected_pngs: set[str] | None = None
    if acceptance_path is not None:
        _, accepted = _accepted_entries(acceptance_path)
        expected_pngs = {entry["png"] for entry in accepted}

    seen_pngs: set[str] = set()
    unreviewed: list[str] = []
    validated_docs: list[tuple[str, dict]] = []

    for entry in screenshots:
        if not isinstance(entry, dict):
            raise TypeError("Each screenshot entry in the export must be an object")
        png = entry.get("png")
        if (
            not isinstance(png, str)
            or Path(png).name != png
            or not png.endswith(".png")
        ):
            raise ValueError(f"Invalid screenshot filename in export: {png!r}")
        if png in seen_pngs:
            raise ValueError(f"Duplicate screenshot in export: {png}")
        seen_pngs.add(png)

        if entry.get("reviewed") is not True:
            unreviewed.append(png)
            continue

        file_lang = screenshot_language(Path(png))
        screen = Path(png).stem.split("__")[0]
        if screen in holdout:
            raise ValueError(f"Hold-out screen refused: {screen}")
        language = entry.get("language")
        if language != file_lang:
            raise ValueError(
                f"Language mismatch for {png}: export={language!r}, filename={file_lang!r}"
            )

        raw_labels = entry.get("labels")
        if not isinstance(raw_labels, list):
            raise TypeError(f"{png}: 'labels' must be a list")
        rows = [
            _validate_label_item(item, png, index)
            for index, item in enumerate(raw_labels, start=1)
        ]

        doc = {
            "schema_version": 2,
            "screenshot": png,
            "language": file_lang,
            "labels": rows,
        }
        version, _ = load_labels(doc)
        if version != 2:
            raise ValueError(f"{png}: expected schema_version 2, got {version!r}")
        validated_docs.append((png, doc))

    if unreviewed:
        raise ValueError(
            f"Refusing export with {len(unreviewed)} unreviewed screenshot(s): "
            + ", ".join(unreviewed)
        )

    if expected_pngs is not None and seen_pngs != expected_pngs:
        missing = sorted(expected_pngs - seen_pngs)
        extra = sorted(seen_pngs - expected_pngs)
        parts = []
        if missing:
            parts.append(f"missing: {', '.join(missing)}")
        if extra:
            parts.append(f"unexpected: {', '.join(extra)}")
        raise ValueError(
            "Export does not match acceptance.json (" + "; ".join(parts) + ")"
        )

    if copy_pngs_from is not None:
        for png, _ in validated_docs:
            if not (copy_pngs_from / png).is_file():
                raise ValueError(f"Source PNG missing: {copy_pngs_from / png}")

    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for png, doc in sorted(validated_docs, key=lambda pair: pair[0]):
        label_path = output_dir / f"{Path(png).stem}.labels.json"
        label_path.write_text(
            json.dumps(doc, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        if copy_pngs_from is not None:
            source_png = copy_pngs_from / png
            dest_png = output_dir / png
            if source_png.resolve() != dest_png.resolve():
                shutil.copy2(source_png, dest_png)
        written.append(label_path)

    return written
