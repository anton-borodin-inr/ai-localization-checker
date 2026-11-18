"""Pixel measurements, intended-occurrence qualification, and dump side effects."""

import io
import math
import re
from collections import defaultdict

from PIL import Image, ImageChops, ImageDraw

from l10n_checker.capture import CaptureError
from l10n_checker.mutation_catalog import require


def compare_rgba(first, second, rectangles):
    """Measure changes outside the union of before/after target extents."""
    with Image.open(io.BytesIO(first)) as image:
        a = image.convert("RGBA")
    with Image.open(io.BytesIO(second)) as image:
        b = image.convert("RGBA")
    require(a.size == b.size, "RGBA image size mismatch")
    width, height = a.size
    outside = Image.new("L", a.size, 255)
    draw = ImageDraw.Draw(outside)
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
            draw.rectangle((left, top, right - 1, bottom - 1), fill=0)
    channels = [
        ImageChops.multiply(channel, outside)
        for channel in ImageChops.difference(a, b).split()
    ]
    difference = channels[0]
    for channel in channels[1:]:
        difference = ImageChops.lighter(difference, channel)
    return {
        "different_pixels": sum(difference.histogram()[1:]),
        "max_channel_deltas": [channel.getextrema()[1] for channel in channels],
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
        )
        == (
            after.screen,
            after.language,
            after.state_sha256,
            after.image_size,
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
            for dump, matches, target, field in (
                (before, old, target_before, "before_draw_ids"),
                (after, new, target_after, "after_draw_ids"),
            ):
                if len(matches) != 1:
                    continue
                group = [
                    e for e in dump.elements if e.logical_id == matches[0].logical_id
                ]
                for e in group:
                    target.add(e.id)
                    if e.bounds is not None:
                        rectangles.append(e.bounds)
                    rectangles.append(e.glyph_bounds)
                current[field] = [e.id for e in group]

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

    moved_or_resized, flags = unmutated_changes(
        before, after, target_before, target_after
    )
    reasons = [
        {
            "recipe_id": o["recipe_id"],
            "intended_class": o["intended_class"],
            "actor_path": o["actor_path"],
            "reason": o["reason"],
        }
        for o in occurrences
        if not o["qualified"]
    ]
    if len(occurrences) > 2:
        reasons.append({"reason": "Intended occurrence limit exceeded (N > 2)"})
    return {
        "qualified": bool(occurrences) and not reasons,
        "qualification_reasons": reasons,
        "occurrences": occurrences,
        "measurements": {
            "outside_mask_pixels": compare_rgba(first_png, second_png, rectangles),
            "moved_or_resized_unmutated_groups": moved_or_resized,
        },
        "review_flags": flags,
    }


def unmutated_changes(before, after, target_before, target_after):
    def unmutated(dump, excluded):
        grouped = defaultdict(list)
        for e in dump.elements:
            if e.id in excluded:
                continue
            key = (e.actor_path or e.logical_id, e.decoration)
            grouped[key].append(e)
        return grouped

    a, b = unmutated(before, target_before), unmutated(after, target_after)
    moved_or_resized = 0
    flags = []
    for actor_path, decoration in sorted(a.keys() | b.keys()):
        key = (actor_path, decoration)
        old, new = a.get(key, []), b.get(key, [])
        moved_or_resized += any(
            first.bounds != second.bounds or first.glyph_bounds != second.glyph_bounds
            for first, second in zip(old, new)
        )
        old_text, new_text = visible_semantics(old), visible_semantics(new)
        if old_text != new_text:
            flags.append(
                {
                    "actor_path": actor_path,
                    "decoration": decoration,
                    "before": old_text,
                    "after": new_text,
                }
            )
    return moved_or_resized, flags


def visible_semantics(elements):
    result = []
    for element in elements:
        if element.visibility == "hidden":
            continue
        lines = [
            "".join(glyph.text for glyph in line.glyphs if glyph.visibility != "hidden")
            for line in element.lines
        ]
        visible = [index for index, line in enumerate(lines) if line]
        if visible:
            result.append(
                {
                    "visible_lines": lines[visible[0] : visible[-1] + 1],
                    "visibility": element.visibility,
                    "ellipsis_applied": element.ellipsis_applied,
                    "clipped_fraction": element.clipped_fraction,
                }
            )
    return result


def occurrence_matrix(screenshots):
    """Count intended occurrences and those retained in the review set."""
    cells = {}
    for screenshot in screenshots:
        if screenshot["role"] != "mutation":
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
            cell["qualified"] += "png" in screenshot
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
