"""Offline, zero-tolerance pixel attribution, never a qualification rule.

Coordinates are top-left physical PNG pixels. A rectangle contains a pixel iff
left <= x+0.5 < right and top <= y+0.5 < bottom. The additional outward enclosure
uses floor(left/top), ceil(right/bottom), with exclusive right/bottom edges.
"""

import csv
import io
import json
import math
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

from l10n_checker.mutation_catalog import require
from l10n_checker.mutation_verify import compare_rgba
from l10n_checker.screen_manifest import digest
from l10n_checker.text_dump import canonical_bytes


def _groups(dump, excluded):
    groups = defaultdict(list)
    for element in dump.elements:
        if element.id in excluded:
            continue
        groups[(element.actor_path or element.logical_id, element.decoration)].append(
            element
        )
    return groups


def _signature(elements):
    return [e.model_dump(exclude={"id", "logical_id"}) for e in elements]


def _contains(rect, x, y):
    return rect is not None and rect[0] <= x < rect[2] and rect[1] <= y < rect[3]


RULES = ("pixel_center", "outward_enclosure")


def _intersection(*rectangles):
    if any(r is None for r in rectangles):
        return None
    rect = [
        max(r[0] for r in rectangles),
        max(r[1] for r in rectangles),
        min(r[2] for r in rectangles),
        min(r[3] for r in rectangles),
    ]
    return rect if rect[0] < rect[2] and rect[1] < rect[3] else None


def _geometry(element, dump):
    screen = [0, 0, *dump.image_size]
    clip = _intersection(screen, dump.viewport, element.clip_bounds or screen)
    active = (
        element.drawn and element.effective_alpha > 0 and element.visibility != "hidden"
    )
    owner = _intersection(element.bounds, clip) if active else None
    glyphs = []
    for i, line in enumerate(element.lines):
        for j, glyph in enumerate(line.glyphs):
            rect = (
                _intersection(glyph.bounds, glyph.visible_bounds, clip)
                if active
                else None
            )
            if rect is not None:
                glyphs.append(
                    {
                        "line_index": i,
                        "glyph_index": j,
                        **glyph.model_dump(),
                        "attribution_rectangle": rect,
                    }
                )
    return owner, glyphs


def _records(before, after, occurrences):
    excluded = [
        {identity for o in occurrences for identity in o.get(name, [])}
        for name in ("before_draw_ids", "after_draw_ids")
    ]
    for dump, ids in zip((before, after), excluded, strict=True):
        require(ids <= {e.id for e in dump.elements}, "Unknown target draw ID")
    a, b = _groups(before, excluded[0]), _groups(after, excluded[1])
    records, changed = [], []

    def add(first, second, status):
        element = first if first is not None else second
        signature = _signature([element])[0]
        owner, glyphs = _geometry(element, before if first is not None else after)
        records.append(
            {
                "record_id": f"element-{len(records):04d}",
                "before_draw_id": first.id if first is not None else None,
                "after_draw_id": second.id if second is not None else None,
                "before_logical_id": first.logical_id if first is not None else None,
                "after_logical_id": second.logical_id if second is not None else None,
                "status": status,
                "actor_path": element.actor_path,
                "display_text": element.display_text,
                "source_key": element.source_key,
                "source_keys": element.source_keys,
                "signature_sha256": digest(canonical_bytes(signature)),
                "signature": signature,
                "owner_rectangle": owner,
                "glyph_rectangles": glyphs,
                "counts": {rule: _empty_counts() for rule in RULES},
            }
        )

    for key in sorted(set(a) | set(b)):
        old, new = a.get(key, []), b.get(key, [])
        if _signature(old) == _signature(new):
            group_sha = digest(canonical_bytes(_signature(old)))
            for first, second in zip(old, new, strict=True):
                add(first, second, "stable_unmutated")
                records[-1]["unchanged_group_sha256"] = group_sha
        else:
            changed.append(
                {
                    "actor_path_or_logical_id": key[0],
                    "decoration": key[1],
                    "before": [e.model_dump() for e in old],
                    "after": [e.model_dump() for e in new],
                }
            )
            for e in old:
                add(e, None, "changed_or_unmatched_before")
            for e in new:
                add(None, e, "changed_or_unmatched_after")
    for dump, ids, side in (
        (before, excluded[0], "before"),
        (after, excluded[1], "after"),
    ):
        for e in dump.elements:
            if e.id in ids:
                add(
                    e if side == "before" else None,
                    e if side == "after" else None,
                    "target_excluded",
                )
    return records, changed, excluded


def _empty_counts():
    return dict.fromkeys(
        ("glyph", "owner", "owner_only", "union", "elsewhere", "glyph_owner_overlap"), 0
    )


def _rule_contains(rect, x, y, rule):
    if rect is None:
        return False
    if rule == "outward_enclosure":
        rect = [
            math.floor(rect[0]),
            math.floor(rect[1]),
            math.ceil(rect[2]),
            math.ceil(rect[3]),
        ]
    return _contains(rect, x + 0.5, y + 0.5)


def _hits(records, x, y, rule):
    stable, other = [], []
    for e in records:
        owner = _rule_contains(e["owner_rectangle"], x, y, rule)
        glyphs = [
            g
            for g in e["glyph_rectangles"]
            if _rule_contains(g["attribution_rectangle"], x, y, rule)
        ]
        if not (owner or glyphs):
            continue
        hit = {
            name: e[name]
            for name in (
                "record_id",
                "before_draw_id",
                "after_draw_id",
                "actor_path",
                "display_text",
                "source_key",
                "source_keys",
                "status",
            )
        }
        hit.update(owner=owner, glyphs=glyphs)
        (stable if e["status"] == "stable_unmutated" else other).append(hit)
    glyph, owner = any(h["glyphs"] for h in stable), any(h["owner"] for h in stable)
    return {
        "category": "glyph" if glyph else "owner_only" if owner else "elsewhere",
        "memberships": stable,
        "other_memberships": other,
    }


def _tally(counts, glyph, owner):
    for name, hit in {
        "glyph": glyph,
        "owner": owner,
        "owner_only": owner and not glyph,
        "union": glyph or owner,
        "elsewhere": not (glyph or owner),
        "glyph_owner_overlap": glyph and owner,
    }.items():
        counts[name] += int(hit)


def attribute_outside_pixels(
    first_png, second_png, before, after, verification, *, provenance=None
):
    """Assign outside changed pixels without changing any qualification rule.

    Ordered full-group equality matches verify_screen, excluding only id and
    logical_id. Bounds are engine rectangles, not ink or proof of causality.
    """
    identity = ("screen", "language", "state_sha256", "image_size", "viewport")
    require(
        all(getattr(before, k) == getattr(after, k) for k in identity),
        "Diagnostic dump identity mismatch",
    )
    pixels = compare_rgba(
        first_png, second_png, verification["pixels"]["mask"]["rectangles"]
    )
    require(pixels == verification["pixels"], "Diagnostic pixel replay mismatch")
    with Image.open(io.BytesIO(first_png)) as image:
        a = image.convert("RGBA")
    with Image.open(io.BytesIO(second_png)) as image:
        b = image.convert("RGBA")
    require(list(a.size) == before.image_size, "Diagnostic image/dump size mismatch")
    elements, changed, excluded = _records(before, after, verification["occurrences"])
    by_id = {e["record_id"]: e for e in elements}
    rows, counts = [], {rule: _empty_counts() for rule in RULES}
    raw_a, raw_b = a.tobytes(), b.tobytes()
    left, top, right, bottom = pixels["outside"]["bounding_box"] or [0, 0, 0, 0]
    for y in range(top, bottom):
        for x in range(left, right):
            offset = (y * a.width + x) * 4
            av, bv = raw_a[offset : offset + 4], raw_b[offset : offset + 4]
            if av == bv or any(
                _contains(rect, x + 0.5, y + 0.5)
                for rect in pixels["mask"]["rectangles"]
            ):
                continue
            rules = {}
            for rule in RULES:
                hits = rules[rule] = _hits(elements, x, y, rule)
                _tally(
                    counts[rule],
                    any(h["glyphs"] for h in hits["memberships"]),
                    any(h["owner"] for h in hits["memberships"]),
                )
                for hit in hits["memberships"] + hits["other_memberships"]:
                    _tally(
                        by_id[hit["record_id"]]["counts"][rule],
                        bool(hit["glyphs"]),
                        hit["owner"],
                    )
            rows.append(
                {
                    "x": x,
                    "y": y,
                    "before_rgba": list(av),
                    "after_rgba": list(bv),
                    "absolute_rgba_delta": [
                        abs(v - w) for v, w in zip(av, bv, strict=True)
                    ],
                    **rules,
                }
            )
    require(
        len(rows) == pixels["outside"]["different_pixels"],
        "Outside pixel accounting mismatch",
    )
    return {
        "diagnostics_version": "outside-attribution-v1",
        "diagnostic_only": True,
        "verification_passed_unchanged": verification.get("passed"),
        "screen": before.screen,
        "language": before.language,
        "image_size": before.image_size,
        "pixel_measurements": pixels,
        "coordinate_rules": {
            "pixel_center": "left <= x+0.5 < right and top <= y+0.5 < bottom; top-left physical PNG coordinates",
            "outward_enclosure": "floor(left/top), ceil(right/bottom); half-open integer enclosure, not a tolerance or target-mask change",
            "geometry": "Recorded per-glyph bounds intersect visible_bounds, element clip_bounds, viewport and screen; owner uses element.bounds intersect clip_bounds, viewport and screen. Hidden/undrawn/zero-alpha draws excluded. No parent/cell or aggregate glyph geometry invented.",
            "counts": "Global glyph, owner_only and elsewhere partition unique outside changed pixels. Owner is any owner membership; glyph_owner_overlap includes cross-element overlap. Per-element owner_only is local to that element, so per-element sums are not global totals.",
        },
        "provenance": {
            "first_png_sha256": digest(first_png),
            "second_png_sha256": digest(second_png),
            "first_rgba_sha256": digest(a.tobytes()),
            "second_rgba_sha256": digest(b.tobytes()),
            "before_dump_canonical_sha256": digest(
                canonical_bytes(before.model_dump())
            ),
            "after_dump_canonical_sha256": digest(canonical_bytes(after.model_dump())),
            "authenticated_source": provenance,
        },
        "counts": counts,
        "pixels": rows,
        "elements": elements,
        "changed_groups": changed,
        "excluded_target_draw_ids": {
            "before": sorted(excluded[0]),
            "after": sorted(excluded[1]),
        },
        "geometry_diagnostics": [
            {
                "record_id": e["record_id"],
                "actor_path_missing": e["actor_path"] is None,
                "owner_bounds_missing": e["signature"]["bounds"] is None,
                "visible_glyph_rectangles": len(e["glyph_rectangles"]),
                "warnings": e["signature"]["warnings"],
            }
            for e in elements
            if e["actor_path"] is None
            or e["signature"]["bounds"] is None
            or not e["glyph_rectangles"]
            or e["signature"]["warnings"]
        ],
    }


def write_diagnostics(folder, result, first_png, second_png, *, context=32):
    """Write a fresh offline bundle; x50 is display-only, never counting."""
    require(type(context) is int and context >= 0, "Invalid crop context")
    require(
        digest(first_png) == result["provenance"]["first_png_sha256"]
        and digest(second_png) == result["provenance"]["second_png_sha256"],
        "Diagnostic export image mismatch",
    )
    folder = Path(folder).resolve()
    folder.mkdir(parents=True, exist_ok=False)
    with Image.open(io.BytesIO(first_png)) as image:
        first = image.convert("RGBA")
    with Image.open(io.BytesIO(second_png)) as image:
        second = image.convert("RGBA")
    bbox = result["pixel_measurements"]["outside"]["bounding_box"]
    crop = (
        [
            max(0, bbox[0] - context),
            max(0, bbox[1] - context),
            min(first.width, bbox[2] + context),
            min(first.height, bbox[3] + context),
        ]
        if bbox
        else [0, 0, *first.size]
    )
    crop_box = (crop[0], crop[1], crop[2], crop[3])
    control, calibration = first.crop(crop_box), second.crop(crop_box)
    channels = ImageChops.difference(control, calibration).split()
    display_lookup = [min(255, value * 50) for value in range(256)]
    amplified = [channel.point(display_lookup) for channel in channels]
    maximum = amplified[0]
    for channel in amplified[1:]:
        maximum = ImageChops.lighter(maximum, channel)
    images = {
        "control_crop": control,
        "calibration_crop": calibration,
        "difference_rgb_x50": Image.merge("RGB", tuple(amplified[:3])),
        "difference_alpha_x50": amplified[3],
        "difference_rgba_max_x50": maximum,
    }
    names = {
        "control_crop": "control-crop.png",
        "calibration_crop": "calibration-crop.png",
        "difference_rgb_x50": "difference-rgb-x50.png",
        "difference_alpha_x50": "difference-alpha-x50.png",
        "difference_rgba_max_x50": "difference-rgba-max-x50.png",
    }
    paths = {key: str(folder / name) for key, name in names.items()}
    for key, image in images.items():
        image.save(paths[key])
    font = ImageFont.load_default(size=18)
    cell_width, cell_height = max(control.width, 480) + 16, control.height + 48
    sheet = Image.new("RGB", (cell_width * 2, cell_height * 3 + 96), "white")
    draw = ImageDraw.Draw(sheet)
    draw.text(
        (12, 8),
        f"Outside changed pixels: {len(result['pixels'])}; crop {crop} (exclusive right/bottom)",
        fill="black",
        font=font,
    )
    draw.text(
        (12, 34),
        "Absolute RGBA delta x50, clamped at 255: DISPLAY ONLY. Counts have zero tolerance.",
        fill="black",
        font=font,
    )
    draw.text(
        (12, 60),
        "Difference panels include all deltas in the context crop; RGB shown opaque, alpha separately.",
        fill="black",
        font=font,
    )
    for index, (key, image) in enumerate(images.items()):
        x, y = (index % 2) * cell_width + 8, (index // 2) * cell_height + 96
        draw.text((x, y), key, fill="black", font=font)
        sheet.paste(image.convert("RGB"), (x, y + 30))
    paths.update(
        contact_sheet=str(folder / "contact-sheet.png"),
        csv=str(folder / "outside-pixels.csv"),
        json=str(folder / "outside-pixels.json"),
        summary=str(folder / "summary.json"),
    )
    sheet.save(paths["contact_sheet"])
    with open(paths["csv"], "w", encoding="utf-8", newline="") as stream:
        fields = [
            "x",
            "y",
            "before_rgba",
            "after_rgba",
            "absolute_rgba_delta",
            *RULES,
            "provenance",
        ]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for pixel in result["pixels"]:
            writer.writerow(
                {
                    key: json.dumps(value, ensure_ascii=False, separators=(",", ":"))
                    if isinstance(value, (dict, list))
                    else value
                    for key, value in {
                        **pixel,
                        "provenance": result["provenance"],
                    }.items()
                }
            )
    summary = {key: value for key, value in result.items() if key != "pixels"}
    summary.update(
        artifact_paths=paths,
        outside_pixel_rows=len(result["pixels"]),
        visualization={
            "crop_exclusive": crop,
            "outside_bbox_exclusive": bbox,
            "context_pixels": context,
            "amplification": 50,
            "counts_use_amplification": False,
            "empty_bbox_uses_full_image": bbox is None,
        },
    )
    Path(paths["json"]).write_bytes(
        canonical_bytes({**summary, "pixels": result["pixels"]})
    )
    Path(paths["summary"]).write_bytes(canonical_bytes(summary))
    return paths
