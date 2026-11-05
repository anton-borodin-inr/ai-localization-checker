"""Zero-tolerance RGBA/dump isolation and intended-occurrence qualification."""

import io
import math
import re
from collections import defaultdict

from PIL import Image, ImageChops, ImageDraw

from l10n_checker.capture import CaptureError
from l10n_checker.mutation_catalog import require
from l10n_checker.screen_manifest import digest
from l10n_checker.text_dump import canonical_bytes


def compare_rgba(first, second, rectangles):
    with Image.open(io.BytesIO(first)) as image:
        a = image.convert("RGBA")
    with Image.open(io.BytesIO(second)) as image:
        b = image.convert("RGBA")
    require(a.size == b.size, "RGBA image size mismatch")
    width, height = a.size
    mask = Image.new("L", a.size, 0)
    draw = ImageDraw.Draw(mask)
    rounded = []
    for rect in rectangles:
        require(
            len(rect) == 4
            and all(math.isfinite(v) for v in rect)
            and rect[0] <= rect[2]
            and rect[1] <= rect[3],
            "Invalid target extent",
        )
        left, top = max(0, math.floor(rect[0])), max(0, math.floor(rect[1]))
        right, bottom = min(width, math.ceil(rect[2])), min(height, math.ceil(rect[3]))
        if right > left and bottom > top:
            rounded.append([left, top, right, bottom])
            draw.rectangle((left, top, right - 1, bottom - 1), fill=255)
    channels = ImageChops.difference(a, b).split()
    difference = channels[0]
    for channel in channels[1:]:
        difference = ImageChops.lighter(difference, channel)
    different = difference.point(lambda value: 255 if value else 0)

    def stats(region):
        changed = ImageChops.multiply(different, region)
        bbox = changed.getbbox()
        return {
            "different_pixels": changed.histogram()[255],
            "bounding_box": list(bbox) if bbox else None,
            "max_channel_deltas": [
                ImageChops.multiply(channel, region).getextrema()[1]
                for channel in channels
            ],
        }

    inside, outside = stats(mask), stats(ImageChops.invert(mask))
    return {
        "passed": outside["different_pixels"] == 0,
        "total": stats(Image.new("L", a.size, 255)),
        "inside": inside,
        "outside": outside,
        "mask": {
            "policy": "target-extents-floor-ceil-v1",
            "rectangles": sorted(rounded),
            "sha256": digest(mask.tobytes()),
            "size": [width, height],
        },
        "bounding_box_convention": "[left,top,right-exclusive,bottom-exclusive]",
    }


def expected_input(recipe, before):
    """Apply an approved literal template to the observed clean component only."""
    original = recipe["original"] or recipe["key"]
    replacement = (
        recipe["key"] if recipe["operation"] == "remove" else recipe["replacement"]
    )
    tokens = re.findall(r"\[[^]]+\]", original)
    pattern = re.escape(original)
    for token in tokens:
        pattern = pattern.replace(re.escape(token), r"([^\n]+)", 1)
    matches = list(re.finditer(pattern, before))
    require(
        len(matches) == 1, "Cannot unambiguously resolve clean translation template"
    )
    match = matches[0]
    for token, value in zip(tokens, match.groups(), strict=True):
        replacement = replacement.replace(token, value)
    return before[: match.start()] + replacement + before[match.end() :]


def plain(text):
    # Remove only the known markup wrappers, never unknown placeholder tokens.
    return " ".join(
        re.sub(
            r"\[(?:RED|GREEN|BLUE|WHITE|BLACK|YELLOW|ORANGE|GRAY|GREY|#[0-9a-fA-F]{6,8})\]|\[\]",
            "",
            text,
        ).split()
    )


def verify_screen(first_png, second_png, before, after, mutations):
    require(
        (
            before.screen,
            before.language,
            before.state_sha256,
            before.image_size,
            before.viewport,
        )
        == (
            after.screen,
            after.language,
            after.state_sha256,
            after.image_size,
            after.viewport,
        ),
        "Cross-build dump identity mismatch",
    )
    language = {"English": "en", "German": "de"}.get(before.language)
    require(language is not None, "Unsupported dump language")
    target_before, target_after, rectangles, occurrences = set(), set(), [], []
    for mutation in mutations:
        recipe = mutation["recipe"]
        for intended in mutation["occurrences"]:
            if (intended["screen"], intended["language"]) != (before.screen, language):
                continue
            current = {
                "recipe_id": recipe["id"],
                "intended_class": recipe["intended_class"],
                "actor_path": intended["actor_path"],
                "qualified": False,
            }
            occurrences.append(current)
            old = [
                e
                for e in before.elements
                if not e.decoration
                and e.actor_path == intended["actor_path"]
                and e.input_text == intended["input_text"]
            ]
            new = [
                e
                for e in after.elements
                if not e.decoration and e.actor_path == intended["actor_path"]
            ]
            if len(old) != 1 or len(new) != 1:
                current["reason"] = "missing_or_ambiguous_owner"
                continue
            old, new = old[0], new[0]
            current.update(before=old.model_dump(), after=new.model_dump())
            try:
                expected = expected_input(recipe, old.input_text or "")
                current["expected_input_text"] = expected
                require(
                    new.input_text == expected and old.display_text != new.display_text,
                    "Intended translation not visible",
                )
                require(
                    new.drawn
                    and new.effective_alpha > 0
                    and new.visibility == "full"
                    and new.bounds is not None
                    and old.bounds is not None,
                    "Intended occurrence not fully visible",
                )
                known = [new.source_key, *new.source_keys]
                require(
                    new.source_key is None or recipe["key"] in known,
                    "Contradictory mutated source provenance",
                )
                kind = recipe["intended_class"]
                if kind == "overflow":
                    require(
                        new.overflow_x
                        and (
                            new.glyph_bounds[0] < new.bounds[0]
                            or new.glyph_bounds[2] > new.bounds[2]
                        )
                        and not new.ellipsis_applied
                        and new.clip_cause == "none",
                        "No visible horizontal own-label overflow",
                    )
                    require(
                        [new.bounds[2] - new.bounds[0], new.bounds[3] - new.bounds[1]]
                        == [
                            old.bounds[2] - old.bounds[0],
                            old.bounds[3] - old.bounds[1],
                        ],
                        "Overflow owner grew instead",
                    )
                    require(
                        plain(new.display_text) == plain(expected)
                        and len(new.lines) == len(old.lines),
                        "Overflow wrapped or lost text",
                    )
                elif kind == "truncated_text":
                    full = plain(expected)
                    require(
                        new.ellipsis_applied
                        and plain(new.display_text) != full
                        and new.clip_cause == "none",
                        "No qualified own-field truncation",
                    )
                    require(
                        not any(
                            full in plain(e.display_text)
                            for e in after.elements
                            if e.drawn and e.visibility == "full" and not e.decoration
                        ),
                        "Full text visible elsewhere",
                    )
                else:
                    require(
                        not new.ellipsis_applied
                        and plain(new.display_text) == plain(expected),
                        "Intended foreign/placeholder text not fully rendered",
                    )
                    if kind == "other":
                        unknown = set(
                            re.findall(r"\[[^]]+\]", recipe["replacement"])
                        ) - set(re.findall(r"\[[^]]+\]", recipe["key"]))
                        require(
                            any(token in new.display_text for token in unknown),
                            "Broken placeholder not visible",
                        )
                current["qualified"] = True
            except CaptureError as exc:
                current["reason"] = str(exc)
            # Even unqualified matched targets cannot hide changes to other elements.
            for dump, primary, target in (
                (before, old, target_before),
                (after, new, target_after),
            ):
                group = [e for e in dump.elements if e.logical_id == primary.logical_id]
                for e in group:
                    target.add(e.id)
                    if e.bounds is not None:
                        rectangles.append(e.bounds)
                    rectangles.append(e.glyph_bounds)
                current["before_draw_ids" if dump is before else "after_draw_ids"] = [
                    e.id for e in group
                ]

    def unmutated(dump, excluded):
        grouped = defaultdict(list)
        for e in dump.elements:
            if e.id in excluded:
                continue
            key = (e.actor_path or e.logical_id, e.decoration)
            grouped[key].append(e.model_dump(exclude={"id", "logical_id"}))
        return grouped

    a, b = unmutated(before, target_before), unmutated(after, target_after)
    changed = [
        {
            "actor_path": key[0],
            "decoration": key[1],
            "before": a.get(key, []),
            "after": b.get(key, []),
        }
        for key in sorted(set(a) | set(b))
        if a.get(key) != b.get(key)
    ]
    pixels = compare_rgba(first_png, second_png, rectangles)
    passed = (
        pixels["passed"]
        and not changed
        and all(o["qualified"] for o in occurrences)
        and len(occurrences) <= 2
    )
    return {
        "passed": passed,
        "pixels": pixels,
        "changed_unmutated_elements": changed,
        "occurrences": occurrences,
        "visible_occurrences": sum(o["qualified"] for o in occurrences),
        "verification_version": "mutation-dynamic-v1",
    }


def split_rate(tests):
    unique = {
        r["id"]: r
        for r in tests
        if len(r["recipe_ids"]) > 1 and r.get("operational_failure") is not True
    }
    split = sum(r["split"] for r in unique.values())
    return {
        "split_batches": split,
        "tested_multi_recipe_batches": len(unique),
        "rate": split / len(unique) if unique else None,
    }


def manifest_bytes(value):
    """No clocks, paths or transport IDs enter the deterministic runtime content."""
    return canonical_bytes(value)


def occurrence_matrix(screenshots):
    """Count intended/qualified occurrences, not labels or decorative repeats."""
    cells = {}
    for screenshot in screenshots:
        if screenshot["role"] != "mutation" or screenshot["pass"] != 1:
            continue
        for occurrence in screenshot["verification"]["occurrences"]:
            key = (
                screenshot["screen"],
                screenshot["language"],
                occurrence["intended_class"],
            )
            cell = cells.setdefault(
                key, {"intended": 0, "qualified": 0, "targets": set()}
            )
            cell["intended"] += 1
            cell["qualified"] += occurrence["qualified"]
            cell["targets"].add(occurrence["actor_path"])
    return [
        {
            "screen": screen,
            "language": language,
            "intended_class": kind,
            "intended_occurrences": cell["intended"],
            "qualified_occurrences": cell["qualified"],
            "distinct_targets": len(cell["targets"]),
        }
        for (screen, language, kind), cell in sorted(cells.items())
    ]
