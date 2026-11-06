"""D054's glyph-confined per-comparison rule, separate from strict v1 verification.

These measurements do not establish a rendering cause or relax same-build PNG
or full-dump repeatability. Qualification also requires an exact second-pass proof
and every existing nonpixel/intended-occurrence gate in the caller.
"""

import math
import re
from copy import deepcopy

from l10n_checker.capture import CaptureError
from l10n_checker.mutation_catalog import require
from l10n_checker.mutation_diagnostics import attribute_outside_pixels
from l10n_checker.screen_manifest import digest
from l10n_checker.text_dump import canonical_bytes


def outside_rule_policy():
    """Return a fresh, versioned description of the owner-authorized rule."""
    return {
        "decision": "D054",
        "version": 2,
        "max_rgb_delta": None,
        "max_alpha_delta": 0,
        "pixel_criterion": "visible-per-glyph-pixel-centre-half-open",
        "repeat_criterion": "exact-outside-coordinates-and-before-after-RGBA",
    }


def _measure(first_png, second_png, before, after, verification):
    try:
        require(before.language in ("English", "German"), "Unsupported dump language")
        require(isinstance(verification["occurrences"], list), "Invalid occurrences")
        for dump, name in ((before, "before_draw_ids"), (after, "after_draw_ids")):
            excluded = set()
            for occurrence in verification["occurrences"]:
                ids = occurrence[name]
                require(
                    isinstance(ids, list)
                    and ids
                    and all(isinstance(identity, str) and identity for identity in ids),
                    "Missing target draw IDs",
                )
                excluded.update(ids)
            require(excluded <= {e.id for e in dump.elements}, "Unknown target draw ID")
            logical_ids = {e.logical_id for e in dump.elements if e.id in excluded}
            require(
                {e.id for e in dump.elements if e.logical_id in logical_ids}
                == excluded,
                "Incomplete target draw group",
            )
        return attribute_outside_pixels(
            first_png, second_png, before, after, verification
        )
    except (
        KeyError,
        TypeError,
        ValueError,
        AttributeError,
        IndexError,
        OSError,
    ) as exc:
        raise CaptureError(f"Invalid outside-rule measurement: {exc}") from exc


def _valid_rectangle(rect):
    return (
        isinstance(rect, list)
        and len(rect) == 4
        and all(type(n) in (int, float) and math.isfinite(n) for n in rect)
        and rect[0] < rect[2]
        and rect[1] < rect[3]
    )


def _genuine_glyph_hit(record, hit, x, y):
    signature = record["signature"]
    extent = signature["visible_bounds"]
    return (
        signature["drawn"] is True
        and signature["effective_alpha"] > 0
        and signature["visibility"] in ("full", "partial")
        and _valid_rectangle(extent)
        and extent[0] <= x + 0.5 < extent[2]
        and extent[1] <= y + 0.5 < extent[3]
        and _valid_rectangle(signature["glyph_bounds"])
        and (
            signature["clip_bounds"] is None
            or _valid_rectangle(signature["clip_bounds"])
        )
        and any(
            glyph["visibility"] in ("full", "partial")
            and _valid_rectangle(glyph["bounds"])
            and _valid_rectangle(glyph["visible_bounds"])
            for glyph in hit["glyphs"]
        )
    )


def assess_outside_rule(first_png, second_png, before, after, verification):
    """Measure original outside pixels without changing the strict verification."""
    measured = _measure(first_png, second_png, before, after, verification)
    failures = []
    if measured["changed_groups"]:
        failures.append("changed_unmutated_groups")
    deltas = measured["pixel_measurements"]["outside"]["max_channel_deltas"]
    if deltas[3] != 0:
        failures.append("outside_alpha_delta_nonzero")
    affected = set()
    by_id = {record["record_id"]: record for record in measured["elements"]}
    uncovered = False
    for pixel in measured["pixels"]:
        hits = [
            hit
            for hit in pixel["pixel_center"]["memberships"]
            if _genuine_glyph_hit(by_id[hit["record_id"]], hit, pixel["x"], pixel["y"])
        ]
        if not hits:
            uncovered = True
        affected.update(hit["record_id"] for hit in hits)
    if uncovered:
        failures.append("outside_pixels_not_in_visible_unmutated_glyphs")
    names = (
        "before_draw_id",
        "after_draw_id",
        "actor_path",
        "signature_sha256",
        "unchanged_group_sha256",
    )
    elements = [
        {name: record[name] for name in names}
        for record in measured["elements"]
        if record["record_id"] in affected
    ]
    elements.sort(key=canonical_bytes)
    pixels = sorted(measured["pixels"], key=lambda p: (p["x"], p["y"]))
    return {
        "policy": outside_rule_policy(),
        "screen": before.screen,
        "language": before.language,
        "state_sha256": before.state_sha256,
        "image_size": list(before.image_size),
        "mask_sha256": verification["pixels"]["mask"]["sha256"],
        "outside": deepcopy(verification["pixels"]["outside"]),
        "local_criteria_passed": not failures,
        "rule_needed": bool(pixels),
        "outside_pixel_set_sha256": digest(
            canonical_bytes([[p["x"], p["y"]] for p in pixels])
        ),
        "outside_pixel_values_sha256": digest(
            canonical_bytes(
                [[p["x"], p["y"], p["before_rgba"], p["after_rgba"]] for p in pixels]
            )
        ),
        "affected_elements": elements,
        "failure_reasons": failures,
        "measurements_complete": True,
    }


def _is_hash(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _complete_assessment(value):
    """Reject partial/invalid proofs; raw-pair authentication is the caller's job."""
    try:
        if not isinstance(value, dict):
            return False
        if (
            canonical_bytes(value["policy"]) != canonical_bytes(outside_rule_policy())
            or value["measurements_complete"] is not True
            or value["local_criteria_passed"] is not True
            or value["failure_reasons"] != []
            or not isinstance(value["screen"], str)
            or not value["screen"]
            or value["language"] not in ("English", "German")
            or not all(
                _is_hash(value[name])
                for name in (
                    "state_sha256",
                    "mask_sha256",
                    "outside_pixel_set_sha256",
                    "outside_pixel_values_sha256",
                )
            )
        ):
            return False
        size = value["image_size"]
        if not (
            isinstance(size, list)
            and len(size) == 2
            and all(type(n) is int and n > 0 for n in size)
        ):
            return False
        outside = value["outside"]
        count, bbox, deltas = (
            outside[name]
            for name in ("different_pixels", "bounding_box", "max_channel_deltas")
        )
        if not (
            type(count) is int
            and 0 <= count <= size[0] * size[1]
            and value["rule_needed"] is (count > 0)
            and isinstance(deltas, list)
            and len(deltas) == 4
            # Schema validity for measured 8-bit RGB, not an acceptance cap.
            and all(type(n) is int and 0 <= n <= 255 for n in deltas[:3])
            and type(deltas[3]) is int
            and deltas[3] == 0
        ):
            return False
        affected = value["affected_elements"]
        if not isinstance(affected, list) or bool(affected) != bool(count):
            return False
        for record in affected:
            if not (
                isinstance(record["before_draw_id"], str)
                and record["before_draw_id"]
                and isinstance(record["after_draw_id"], str)
                and record["after_draw_id"]
                and (
                    record["actor_path"] is None
                    or isinstance(record["actor_path"], str)
                )
                and _is_hash(record["signature_sha256"])
                and _is_hash(record["unchanged_group_sha256"])
            ):
                return False
        if count:
            return (
                isinstance(bbox, list)
                and len(bbox) == 4
                and all(type(n) is int for n in bbox)
                and 0 <= bbox[0] < bbox[2] <= size[0]
                and 0 <= bbox[1] < bbox[3] <= size[1]
                and count <= (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
                and any(deltas)
            )
        empty_hash = digest(canonical_bytes([]))
        return (
            bbox is None
            and deltas == [0, 0, 0, 0]
            and value["outside_pixel_set_sha256"] == empty_hash
            and value["outside_pixel_values_sha256"] == empty_hash
        )
    except (KeyError, TypeError, ValueError, IndexError):
        return False


def verify_outside_repeat(first_assessment, second_assessment):
    """Compare clean→mutated measurements from forward/reverse capture order.

    Hashes cover canonical lexicographically sorted [x,y] and
    [x,y,before_rgba,after_rgba] arrays independently, not counts/boxes/deltas.
    Inputs must be freshly recomputed from authenticated raw pairs by the caller;
    matching serialized claims alone are not authentication of the underlying PNGs.
    """
    first = first_assessment if isinstance(first_assessment, dict) else {}
    second = second_assessment if isinstance(second_assessment, dict) else {}
    failures = []
    for side, assessment in (
        ("forward", first_assessment),
        ("reverse", second_assessment),
    ):
        if not _complete_assessment(assessment):
            failures.append(f"{side}_incomplete_or_failed_local_assessment")
    identity = ("screen", "language", "state_sha256", "image_size", "mask_sha256")
    if any(first.get(name) != second.get(name) for name in identity):
        failures.append("comparison_identity_or_mask_mismatch")
    if first.get("outside") != second.get("outside"):
        failures.append("outside_statistics_mismatch")
    for kind in ("set", "values"):
        name = f"outside_pixel_{kind}_sha256"
        if first.get(name) != second.get(name):
            failures.append(f"outside_pixel_{kind}_mismatch")
    return {
        "passed": not failures,
        "failure_reasons": failures,
        "forward_pixel_set_sha256": first.get("outside_pixel_set_sha256"),
        "reverse_pixel_set_sha256": second.get("outside_pixel_set_sha256"),
        "forward_pixel_values_sha256": first.get("outside_pixel_values_sha256"),
        "reverse_pixel_values_sha256": second.get("outside_pixel_values_sha256"),
    }
