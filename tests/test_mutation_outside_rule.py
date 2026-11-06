"""Host-only synthetic proofs for the bounded D053 outside-mask rule."""

import importlib
import importlib.util
from copy import deepcopy

import pytest
from test_mutation_diagnostics import dump, element, png

from l10n_checker.capture import CaptureError
from l10n_checker.mutation_verify import compare_rgba, verify_screen
from l10n_checker.screen_manifest import digest
from l10n_checker.text_dump import canonical_bytes


def api():
    assert importlib.util.find_spec("l10n_checker.mutation_outside_rule") is not None, (
        "D053 outside-mask rule missing"
    )
    return importlib.import_module("l10n_checker.mutation_outside_rule")


def assess(before=None, after=None, changes=(), *, first=None, verification=None):
    before = before if before is not None else dump([element()])
    after = after if after is not None else before
    first = png() if first is None else first
    second = png(changes)
    if verification is None:
        verification = verify_screen(first, second, before, after, [])
    return api().assess_outside_rule(first, second, before, after, verification)


def test_visible_unchanged_glyph_has_independent_exact_pixel_and_value_hashes():
    before = dump([element()])
    after = dump([element(id="new/draw-7", logical_id="new")])
    first, second = png(), png([((1, 1), (12, 18, 32, 255))])
    verification = verify_screen(first, second, before, after, [])
    original = deepcopy(verification)
    result = api().assess_outside_rule(first, second, before, after, verification)
    assert result["local_criteria_passed"] is True
    assert result["measurements_complete"] is True
    assert result["failure_reasons"] == []
    assert result["rule_needed"] is True
    assert result["policy"] == api().outside_rule_policy()
    assert result["screen"] == "options-gameplay"
    assert result["language"] == "English"
    assert result["state_sha256"] == "0" * 64
    assert result["image_size"] == [8, 4]
    assert result["mask_sha256"] == verification["pixels"]["mask"]["sha256"]
    assert result["outside"] == verification["pixels"]["outside"]
    assert result["outside_pixel_set_sha256"] == digest(canonical_bytes([[1, 1]]))
    assert result["outside_pixel_values_sha256"] == digest(
        canonical_bytes([[1, 1, [10, 20, 30, 255], [12, 18, 32, 255]]])
    )
    assert result["affected_elements"] == [
        {
            "before_draw_id": "owner/draw-0",
            "after_draw_id": "new/draw-7",
            "actor_path": "owner",
            "signature_sha256": digest(
                canonical_bytes(
                    before.elements[0].model_dump(exclude={"id", "logical_id"})
                )
            ),
            "unchanged_group_sha256": digest(
                canonical_bytes(
                    [before.elements[0].model_dump(exclude={"id", "logical_id"})]
                )
            ),
        }
    ]
    assert verification == original
    assert verification["passed"] is False  # Strict v1 is not promoted.


def test_element_recorded_visible_extent_can_only_narrow_per_glyph_coverage():
    d = dump([element(visibility="partial", visible_bounds=[2, 1, 3, 3])])
    result = assess(d, d, [((1, 1), (11, 20, 30, 255))])
    assert result["local_criteria_passed"] is False
    assert result["affected_elements"] == []
    visible = assess(d, d, [((2, 1), (11, 20, 30, 255))])
    assert visible["local_criteria_passed"] is True


def test_repeat_rejects_contradictory_raw_statistics_even_with_matching_hashes():
    d = dump([element(box=(1, 1, 4, 4))])
    first = assess(
        d, d, [((x, y), (12, 20, 30, 255)) for x, y in [(1, 1), (3, 3), (2, 1)]]
    )
    second = deepcopy(first)
    second["outside"]["different_pixels"] = 2
    assert api().verify_outside_repeat(first, second)["passed"] is False


@pytest.mark.parametrize("channel", range(4))
@pytest.mark.parametrize("magnitude", [1, 2, 3])
@pytest.mark.parametrize("sign", [-1, 1])
def test_each_channel_has_its_own_exact_threshold(channel, magnitude, sign):
    # Use a midrange alpha to exercise both signs without PNG clamping.
    import io

    from PIL import Image

    image = Image.new("RGBA", (8, 4), (10, 20, 30, 128))
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    first = stream.getvalue()
    value = [10, 20, 30, 128]
    value[channel] += sign * magnitude
    image.putpixel((1, 1), tuple(value))
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    second = stream.getvalue()
    d = dump([element()])
    verification = verify_screen(first, second, d, d, [])
    result = api().assess_outside_rule(first, second, d, d, verification)
    allowed = channel < 3 and magnitude <= 2
    assert result["local_criteria_passed"] is allowed
    assert bool(result["failure_reasons"]) is not allowed
    assert result["outside"] == verification["pixels"]["outside"]
    assert result["rule_needed"] is True
    assert result["measurements_complete"] is True


def test_policy_is_exact_and_returns_an_independent_value():
    expected = {
        "decision": "D053",
        "version": 1,
        "max_rgb_delta": 2,
        "max_alpha_delta": 0,
        "pixel_criterion": "visible-per-glyph-pixel-centre-half-open",
        "repeat_criterion": "exact-outside-coordinates-and-before-after-RGBA",
    }
    policy = api().outside_rule_policy()
    assert policy == expected
    policy["max_rgb_delta"] = 200
    assert api().outside_rule_policy() == expected


@pytest.mark.parametrize(
    "xy,allowed", [((1, 1), True), ((0, 0), False), ((7, 3), False)]
)
def test_only_actual_glyph_not_owner_or_elsewhere_can_cover_a_pixel(xy, allowed):
    result = assess(changes=[(xy, (11, 20, 30, 255))])
    assert result["local_criteria_passed"] is allowed
    assert bool(result["failure_reasons"]) is not allowed


@pytest.mark.parametrize(
    "xy,allowed", [((1, 0), True), ((2, 0), False), ((1, 1), False), ((0, 0), False)]
)
def test_fractional_glyphs_use_half_open_pixel_centres_not_rounding(xy, allowed):
    d = dump([element(box=(1.5, 0.5, 2.5, 1.5))])
    result = assess(d, d, [(xy, (11, 20, 30, 255))])
    assert result["local_criteria_passed"] is allowed


@pytest.mark.parametrize("limit", ["glyph_visible", "element_clip", "viewport"])
@pytest.mark.parametrize("x,allowed", [(1, False), (2, True)])
def test_each_recorded_clipping_boundary_limits_visible_glyphs(limit, x, allowed):
    e = element(visibility="partial")
    if limit == "glyph_visible":
        e["lines"][0]["glyphs"][0].update(
            visibility="partial", visible_bounds=[2, 1, 3, 3]
        )
    if limit == "element_clip":
        e["clip_bounds"] = [2, 0, 8, 4]
    d = dump([e])
    if limit == "viewport":
        d = d.model_copy(update={"viewport": [2, 0, 8, 4]})
    result = assess(d, d, [((x, 1), (11, 20, 30, 255))])
    assert result["local_criteria_passed"] is allowed


@pytest.mark.parametrize(
    "hidden", ["glyph", "element", "zero_alpha", "undrawn", "missing_visible_bounds"]
)
def test_hidden_flags_win_even_when_visible_bounds_are_contradictory(hidden):
    # model_copy/assignment deliberately bypass input validation to ensure this
    # security boundary does not trust inconsistent caller-owned model instances.
    d = dump([element()]).model_copy(deep=True)
    e = d.elements[0]
    if hidden == "glyph":
        e.lines[0].glyphs[0].visibility = "hidden"
    elif hidden == "element":
        e.visibility = "hidden"
    elif hidden == "zero_alpha":
        e.effective_alpha = 0
    elif hidden == "undrawn":
        e.drawn = False
    else:
        e.lines[0].glyphs[0].visible_bounds = None
    result = assess(d, d, [((1, 1), (11, 20, 30, 255))])
    assert result["local_criteria_passed"] is False
    assert result["failure_reasons"]
    assert result["affected_elements"] == []


def test_missing_per_glyph_geometry_never_uses_aggregate_bounds():
    d = dump([element(display_text="", input_text="", lines=[])])
    result = assess(d, d, [((1, 1), (11, 20, 30, 255))])
    assert result["local_criteria_passed"] is False
    assert result["affected_elements"] == []


def test_aggregate_gap_between_two_real_glyphs_is_not_visible_glyph_geometry():
    e = element(box=(1, 1, 6, 3), display_text="AA")
    e["lines"][0]["text"] = "AA"
    e["lines"][0]["glyphs"] = [
        {
            "text": "A",
            "bounds": [x, 1, x + 1, 3],
            "visible_bounds": [x, 1, x + 1, 3],
            "visibility": "full",
        }
        for x in (1, 5)
    ]
    d = dump([e])
    result = assess(d, d, [((3, 1), (11, 20, 30, 255))])
    assert result["local_criteria_passed"] is False


def test_all_overlapping_actual_draw_ids_are_reported_not_an_inferred_parent():
    d = dump([element("b"), element("a"), element("a", id="a/draw-1")])
    result = assess(d, d, [((1, 1), (11, 20, 30, 255))])
    assert result["local_criteria_passed"] is True
    assert {e["before_draw_id"] for e in result["affected_elements"]} == {
        "a/draw-0",
        "a/draw-1",
        "b/draw-0",
    }
    assert len(result["affected_elements"]) == 3
    assert result["affected_elements"] == sorted(
        result["affected_elements"], key=canonical_bytes
    )


@pytest.mark.parametrize(
    "change",
    [
        "input",
        "display",
        "owner",
        "glyph",
        "clip",
        "visibility",
        "warnings",
        "source",
        "secondary",
        "added",
        "removed",
        "order",
    ],
)
@pytest.mark.parametrize("pixels", [False, True])
def test_any_changed_full_unmutated_group_fails_even_away_from_pixels(change, pixels):
    old = [
        element("stable"),
        element("other", box=(5, 1, 7, 3)),
        element("other", id="other/draw-1", input_text="secondary"),
    ]
    new = deepcopy(old)
    target = new[1]
    if change == "input":
        target["input_text"] = "different"
    elif change == "display":
        target["display_text"] = target["lines"][0]["text"] = "B"
        target["lines"][0]["glyphs"][0]["text"] = "B"
    elif change == "owner":
        target["bounds"][0] += 0.25
    elif change == "glyph":
        target["lines"][0]["glyphs"][0]["bounds"][0] += 0.25
    elif change == "clip":
        target["clip_bounds"][0] += 0.25
    elif change == "visibility":
        target["visibility"] = "partial"
    elif change == "warnings":
        target["warnings"] = ["source_unavailable"]
    elif change == "source":
        target["source_keys"] = ["different"]
    elif change == "secondary":
        new[2]["bounds"][0] += 0.25
    elif change == "added":
        new.append(element("added"))
    elif change == "removed":
        new.pop()
    else:
        new[1], new[2] = new[2], new[1]
    changes = [((1, 1), (11, 20, 30, 255))] if pixels else []
    result = assess(dump(old), dump(new), changes)
    assert result["local_criteria_passed"] is False
    assert "changed_unmutated_groups" in result["failure_reasons"]


def test_hidden_secondary_glyph_cannot_poison_a_separate_visible_membership():
    d = dump([element("visible"), element("hidden")]).model_copy(deep=True)
    d.elements[1].lines[0].glyphs[0].visibility = "hidden"
    result = assess(d, d, [((1, 1), (11, 20, 30, 255))])
    assert result["local_criteria_passed"] is True
    assert [e["before_draw_id"] for e in result["affected_elements"]] == [
        "visible/draw-0"
    ]


def test_mutated_target_draws_cannot_supply_qualifying_glyphs():
    d = dump([element()])
    first, second = png(), png([((1, 1), (11, 20, 30, 255))])
    verification = {
        "pixels": compare_rgba(first, second, []),
        "occurrences": [
            {"before_draw_ids": ["owner/draw-0"], "after_draw_ids": ["owner/draw-0"]}
        ],
    }
    result = api().assess_outside_rule(first, second, d, d, verification)
    assert result["local_criteria_passed"] is False
    assert result["affected_elements"] == []


@pytest.mark.parametrize("side", ["before_draw_ids", "after_draw_ids"])
def test_partial_target_group_exclusion_fails_closed(side):
    d = dump([element(), element(id="owner/draw-1")])
    first, second = png(), png([((1, 1), (11, 20, 30, 255))])
    occurrence = {
        "before_draw_ids": ["owner/draw-0", "owner/draw-1"],
        "after_draw_ids": ["owner/draw-0", "owner/draw-1"],
    }
    occurrence[side].pop()
    verification = {
        "pixels": compare_rgba(first, second, []),
        "occurrences": [occurrence],
    }
    with pytest.raises(CaptureError, match="target.*group"):
        api().assess_outside_rule(first, second, d, d, verification)


@pytest.mark.parametrize(
    "missing",
    [
        "pixels",
        "mask",
        "rectangles",
        "occurrences",
        "before_draw_ids",
        "after_draw_ids",
    ],
)
def test_missing_comparison_measurement_fields_raise_capture_error(missing):
    d = dump([element()])
    verification = verify_screen(png(), png(), d, d, [])
    if missing == "mask":
        verification["pixels"].pop("mask")
    elif missing == "rectangles":
        verification["pixels"]["mask"].pop("rectangles")
    elif missing in ("before_draw_ids", "after_draw_ids"):
        occurrence = {
            "before_draw_ids": ["owner/draw-0"],
            "after_draw_ids": ["owner/draw-0"],
        }
        occurrence.pop(missing)
        verification["occurrences"] = [occurrence]
    else:
        verification.pop(missing)
    with pytest.raises(CaptureError):
        api().assess_outside_rule(png(), png(), d, d, verification)


@pytest.mark.parametrize(
    "identity", ["screen", "language", "state_sha256", "image_size", "viewport"]
)
def test_cross_build_comparison_identity_must_match(identity):
    d = dump([element()])
    value = {
        "screen": "tech-picker",
        "language": "German",
        "state_sha256": "1" * 64,
        "image_size": [9, 4],
        "viewport": [1, 0, 8, 4],
    }[identity]
    other = d.model_copy(update={identity: value})
    verification = verify_screen(png(), png(), d, d, [])
    with pytest.raises(CaptureError, match="identity"):
        api().assess_outside_rule(png(), png(), d, other, verification)


def test_unsupported_language_is_not_inferred_from_unknown_dump_value():
    d = dump([]).model_copy(update={"language": "en"})
    verification = {"pixels": compare_rgba(png(), png(), []), "occurrences": []}
    with pytest.raises(CaptureError, match="language"):
        api().assess_outside_rule(png(), png(), d, d, verification)


def test_stale_pixel_stats_and_image_dump_mismatch_are_not_trusted():
    d = dump([element()])
    verification = verify_screen(png(), png(), d, d, [])
    with pytest.raises(CaptureError, match="replay"):
        api().assess_outside_rule(
            png(), png([((1, 1), (11, 20, 30, 255))]), d, d, verification
        )
    other = d.model_copy(update={"image_size": [9, 4]})
    with pytest.raises(CaptureError, match="size mismatch"):
        api().assess_outside_rule(png(), png(), other, other, verification)


def test_zero_differences_have_explicit_empty_fingerprints_and_no_rule_usage():
    d = dump([]).model_copy(update={"language": "German"})
    result = assess(d, d)
    assert result["local_criteria_passed"] is True
    assert result["rule_needed"] is False
    assert result["measurements_complete"] is True
    assert result["affected_elements"] == []
    assert result["outside"] == {
        "different_pixels": 0,
        "bounding_box": None,
        "max_channel_deltas": [0, 0, 0, 0],
    }
    assert (
        result["outside_pixel_set_sha256"]
        == result["outside_pixel_values_sha256"]
        == digest(canonical_bytes([]))
    )


def test_inside_target_changes_are_not_subject_to_outside_delta_thresholds():
    d = dump([element()])
    first, second = png(), png([((7, 3), (255, 0, 0, 0)), ((1, 1), (12, 20, 30, 255))])
    verification = {
        "pixels": compare_rgba(first, second, [[7, 3, 8, 4]]),
        "occurrences": [],
    }
    result = api().assess_outside_rule(first, second, d, d, verification)
    assert result["local_criteria_passed"] is True
    assert result["outside"]["different_pixels"] == 1
    assert result["outside_pixel_set_sha256"] == digest(canonical_bytes([[1, 1]]))


def test_exact_forward_reverse_proof_reports_both_coordinate_and_value_hashes():
    first = assess(changes=[((1, 1), (12, 20, 30, 255))])
    second = assess(changes=[((1, 1), (12, 20, 30, 255))])
    assert hasattr(api(), "verify_outside_repeat"), "D053 exact repeat proof missing"
    result = api().verify_outside_repeat(first, second)
    assert result == {
        "passed": True,
        "failure_reasons": [],
        "forward_pixel_set_sha256": first["outside_pixel_set_sha256"],
        "reverse_pixel_set_sha256": second["outside_pixel_set_sha256"],
        "forward_pixel_values_sha256": first["outside_pixel_values_sha256"],
        "reverse_pixel_values_sha256": second["outside_pixel_values_sha256"],
    }


def test_count_bbox_and_max_delta_collision_does_not_prove_exact_pixel_set():
    d = dump([element(box=(1, 1, 4, 4))])
    first = assess(
        d, d, [((x, y), (12, 20, 30, 255)) for x, y in [(1, 1), (3, 3), (2, 1)]]
    )
    second = assess(
        d, d, [((x, y), (12, 20, 30, 255)) for x, y in [(1, 1), (3, 3), (1, 2)]]
    )
    assert first["outside"] == second["outside"]
    assert first["local_criteria_passed"] is second["local_criteria_passed"] is True
    result = api().verify_outside_repeat(first, second)
    assert result["passed"] is False
    assert "outside_pixel_set_mismatch" in result["failure_reasons"]


def test_equal_coordinates_and_deltas_do_not_hide_original_rgba_value_drift():
    first = assess(changes=[((1, 1), (12, 20, 30, 255))])
    second = assess(
        first=png([((1, 1), (20, 20, 30, 255))]), changes=[((1, 1), (22, 20, 30, 255))]
    )
    assert first["outside"] == second["outside"]
    assert first["outside_pixel_set_sha256"] == second["outside_pixel_set_sha256"]
    result = api().verify_outside_repeat(first, second)
    assert result["passed"] is False
    assert "outside_pixel_values_mismatch" in result["failure_reasons"]


def test_repeat_keeps_before_after_value_orientation_not_just_absolute_delta():
    d = dump([element()])
    first, second = png(), png([((1, 1), (12, 20, 30, 255))])
    a = api().assess_outside_rule(
        first, second, d, d, verify_screen(first, second, d, d, [])
    )
    b = api().assess_outside_rule(
        second, first, d, d, verify_screen(second, first, d, d, [])
    )
    assert a["outside"] == b["outside"]
    assert api().verify_outside_repeat(a, b)["passed"] is False


def test_coordinates_values_and_affected_ids_are_canonical_not_traversal_order():
    d = dump([element("z", box=(1, 1, 4, 4)), element("a", box=(1, 1, 4, 4))])
    other = d.model_copy(update={"elements": list(reversed(d.elements))})
    pixels = [((2, 1), (12, 20, 30, 255)), ((1, 2), (11, 20, 30, 255))]
    first = assess(d, d, pixels)
    second = assess(other, other, list(reversed(pixels)))
    assert first == second
    assert first["outside_pixel_set_sha256"] == digest(
        canonical_bytes([[1, 2], [2, 1]])
    )
    assert first["outside_pixel_values_sha256"] == digest(
        canonical_bytes(
            [
                [1, 2, [10, 20, 30, 255], [11, 20, 30, 255]],
                [2, 1, [10, 20, 30, 255], [12, 20, 30, 255]],
            ]
        )
    )
    assert api().verify_outside_repeat(first, second)["passed"] is True


@pytest.mark.parametrize("side", [0, 1])
@pytest.mark.parametrize(
    "field",
    [
        "policy",
        "screen",
        "language",
        "state_sha256",
        "image_size",
        "mask_sha256",
        "outside",
        "local_criteria_passed",
        "rule_needed",
        "outside_pixel_set_sha256",
        "outside_pixel_values_sha256",
        "affected_elements",
        "failure_reasons",
        "measurements_complete",
    ],
)
def test_repeat_rejects_every_missing_required_assessment_field(side, field):
    a = assess(changes=[((1, 1), (12, 20, 30, 255))])
    pair = [deepcopy(a), deepcopy(a)]
    pair[side].pop(field)
    assert api().verify_outside_repeat(*pair)["passed"] is False


@pytest.mark.parametrize("side", [0, 1])
@pytest.mark.parametrize("missing", [None, {}, [], "not an assessment"])
def test_repeat_missing_sibling_measurements_fail_closed(side, missing):
    a = assess()
    pair = [a, a]
    pair[side] = missing
    assert api().verify_outside_repeat(*pair)["passed"] is False


@pytest.mark.parametrize(
    "field,value",
    [
        ("screen", "tech-picker"),
        ("language", "German"),
        ("state_sha256", "1" * 64),
        ("image_size", [9, 4]),
        ("mask_sha256", "1" * 64),
    ],
)
def test_repeat_cannot_match_different_comparison_identity_or_mask(field, value):
    first = assess(changes=[((1, 1), (12, 20, 30, 255))])
    second = deepcopy(first)
    second[field] = value
    assert api().verify_outside_repeat(first, second)["passed"] is False


@pytest.mark.parametrize("value", [(13, 20, 30, 255), (10, 20, 30, 254)])
def test_exactly_repeated_disallowed_local_delta_is_still_disallowed(value):
    first = assess(changes=[((1, 1), value)])
    second = assess(changes=[((1, 1), value)])
    assert first["local_criteria_passed"] is second["local_criteria_passed"] is False
    assert api().verify_outside_repeat(first, second)["passed"] is False


@pytest.mark.parametrize(
    "field,value",
    [
        ("measurements_complete", False),
        ("measurements_complete", 1),
        ("local_criteria_passed", False),
        ("local_criteria_passed", 1),
        ("failure_reasons", ["failed"]),
        ("rule_needed", False),
        ("outside_pixel_set_sha256", None),
        ("outside_pixel_values_sha256", "bad"),
        ("state_sha256", "x" * 64),
        ("mask_sha256", "x" * 64),
        ("policy", {}),
        ("affected_elements", []),
        ("image_size", [0, 4]),
        ("outside", {"different_pixels": 1}),
    ],
)
def test_matching_invalid_or_incomplete_measurements_do_not_prove_repeat(field, value):
    first = assess(changes=[((1, 1), (12, 20, 30, 255))])
    first[field] = value
    assert api().verify_outside_repeat(first, deepcopy(first))["passed"] is False


def test_explicit_zero_difference_assessments_can_repeat_without_using_exception():
    first = assess(dump([]), dump([]))
    assert api().verify_outside_repeat(first, deepcopy(first))["passed"] is True


@pytest.mark.parametrize(
    "field,value",
    [
        ("visible_bounds", None),
        ("clip_bounds", []),
        ("glyph_bounds", None),
        ("clip_bounds", [0, 0, float("nan"), 4]),
        ("visible_bounds", [3, 3, 1, 1]),
    ],
)
def test_missing_or_invalid_active_element_geometry_is_not_guessed(field, value):
    d = dump([element()]).model_copy(deep=True)
    setattr(d.elements[0], field, value)
    try:
        result = assess(d, d, [((1, 1), (11, 20, 30, 255))])
    except CaptureError:
        return
    assert result["local_criteria_passed"] is False
    assert result["affected_elements"] == []


@pytest.mark.parametrize("field", ["bounds", "visible_bounds"])
@pytest.mark.parametrize("value", [None, [], [3, 3, 1, 1], [0, 0, float("inf"), 4]])
def test_missing_or_invalid_per_glyph_rectangles_fail_closed(field, value):
    d = dump([element()]).model_copy(deep=True)
    setattr(d.elements[0].lines[0].glyphs[0], field, value)
    try:
        result = assess(d, d, [((1, 1), (11, 20, 30, 255))])
    except CaptureError:
        return
    assert result["local_criteria_passed"] is False


def test_real_strict_verification_keeps_intended_target_and_raw_failure_unchanged():
    old = element("target", box=(6, 1, 7, 3), owner=(6, 1, 7, 3))
    new = deepcopy(old)
    new["display_text"] = new["input_text"] = new["lines"][0]["text"] = "B"
    new["lines"][0]["glyphs"][0]["text"] = "B"
    before, after = dump([element(), old]), dump([element(), new])
    mutation = {
        "recipe": {
            "id": "foreign",
            "key": "A",
            "original": "",
            "replacement": "B",
            "operation": "replace",
            "intended_class": "wrong_language",
        },
        "occurrences": [
            {
                "screen": "options-gameplay",
                "language": "en",
                "actor_path": "target",
                "input_text": "A",
            }
        ],
    }
    first, second = png(), png([((6, 1), (255, 0, 0, 0)), ((1, 1), (12, 20, 30, 255))])
    verification = verify_screen(first, second, before, after, [mutation])
    original = deepcopy(verification)
    assert verification["passed"] is False
    assert verification["visible_occurrences"] == 1
    assert verification["changed_unmutated_elements"] == []
    result = api().assess_outside_rule(first, second, before, after, verification)
    assert result["local_criteria_passed"] is True
    assert [e["before_draw_id"] for e in result["affected_elements"]] == [
        "owner/draw-0"
    ]
    assert result["outside"] == verification["pixels"]["outside"]
    assert verification == original
