"""Pixel measurements, review flags and intended-only qualification."""

import importlib
import importlib.util
import io
from copy import deepcopy

import pytest
from PIL import Image
from test_text_dump import dump_for, element

from l10n_checker.text_dump import canonical_bytes, load_dump


def api():
    assert importlib.util.find_spec("l10n_checker.mutation_verify") is not None, (
        "Dynamic verifier missing"
    )
    return importlib.import_module("l10n_checker.mutation_verify")


def png(changes=()):
    image = Image.new("RGBA", (100, 60), (10, 20, 30, 255))
    for xy, value in changes:
        image.putpixel(xy, value)
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


def test_review_flags_compare_visible_text_and_preserve_line_breaks():
    before = element(
        "ABC", visibility="partial", clipped_fraction=0.2, ellipsis_applied=False
    )
    before["lines"][0]["glyphs"][-1].update(visibility="hidden", visible_bounds=None)
    after = deepcopy(before)
    after["bounds"] = [10, 20, 99, 40]
    after["display_text"] = after["lines"][0]["text"] = "ABZ"
    after["lines"][0]["glyphs"][-1]["text"] = "Z"

    def compare():
        old = load_dump(canonical_bytes(dump_for(size=[100, 60], elements=[before])))
        new = load_dump(canonical_bytes(dump_for(size=[100, 60], elements=[after])))
        return api().verify_screen(png(), png(), old, new, [])

    geometry_only = compare()
    assert geometry_only["review_flags"] == []
    assert geometry_only["measurements"]["moved_or_resized_unmutated_groups"] == 1

    line = after["lines"][0]
    glyphs = line["glyphs"]
    after["lines"] = [
        {**line, "text": "A", "glyphs": glyphs[:1]},
        {**line, "text": "BZ", "glyphs": glyphs[1:]},
    ]
    after["display_text"] = "A\nBZ"
    after["clipped_fraction"] = 0.3
    after["ellipsis_applied"] = True
    (flag,) = compare()["review_flags"]
    assert flag["before"] == [
        {
            "visible_lines": ["AB"],
            "visibility": "partial",
            "ellipsis_applied": False,
            "clipped_fraction": 0.2,
        }
    ]
    assert flag["after"] == [
        {
            "visible_lines": ["A", "B"],
            "visibility": "partial",
            "ellipsis_applied": True,
            "clipped_fraction": 0.3,
        }
    ]


def test_mask_rounds_outward_and_measures_any_channel_outside_target_extents():
    result = api().compare_rgba(
        png(),
        png(
            [
                ((5, 5), (255, 255, 255, 0)),
                ((90, 0), (255, 255, 255, 0)),
                ((50, 5), (7, 29, 28, 255)),
                ((99, 59), (10, 20, 39, 254)),
            ]
        ),
        [[4.2, 4.2, 5.2, 5.2], [90, 0, 99, 10]],
    )
    assert result == {"different_pixels": 2, "max_channel_deltas": [3, 9, 9, 1]}


def test_expected_translation_keeps_wrappers_and_template_arguments():
    recipe = {
        "key": "Requires at least [amount] population",
        "original": "Benötigt mindestens [amount] Bevölkerung",
        "replacement": "Requiert au moins [amount] habitants",
        "operation": "replace",
    }
    assert (
        api().expected_input(recipe, "[RED]Benötigt mindestens 2 Bevölkerung[]")
        == "[RED]Requiert au moins 2 habitants[]"
    )
    recipe = {
        "key": "Research [technology]",
        "original": "",
        "replacement": "Research [amount]",
        "operation": "replace",
    }
    assert (
        api().expected_input(recipe, "Research \ue1aeArchery\n(0/24)")
        == "Research [amount]\n(0/24)"
    )


def test_outside_pixels_and_unmutated_text_inside_mask_allow_qualification():
    first = element(
        "?", "target", input_text="?", source_key=None, ellipsis_applied=False
    )
    second = element(
        "Help",
        "target",
        input_text="Help",
        source_key="?",
        ellipsis_applied=False,
        overflow_x=True,
        glyph_bounds=[8, 20, 100, 40],
    )
    unchanged = element("other", "other", input_text="other", source_key=None)
    changed = element("oops", "other", input_text="oops", source_key=None)
    before = load_dump(
        canonical_bytes(dump_for(size=[100, 60], elements=[first, unchanged]))
    )
    after = load_dump(
        canonical_bytes(dump_for(size=[100, 60], elements=[second, changed]))
    )
    mutation = {
        "recipe": {
            "id": "help",
            "key": "?",
            "original": "",
            "replacement": "Help",
            "operation": "replace",
            "intended_class": "overflow",
        },
        "occurrences": [
            {
                "actor_path": "target",
                "input_text": "?",
                "screen": "tech-picker",
                "language": "de",
            }
        ],
    }
    result = api().verify_screen(
        png(), png([((99, 59), (24, 20, 30, 200))]), before, after, [mutation]
    )
    assert result["qualified"] is True
    assert result["qualification_reasons"] == []
    assert [flag["actor_path"] for flag in result["review_flags"]] == ["other"]
    assert result["measurements"]["outside_mask_pixels"] == {
        "different_pixels": 1,
        "max_channel_deltas": [14, 0, 0, 55],
    }


@pytest.mark.parametrize(
    "case,reason",
    [
        ("fitting", "No visible horizontal own-label overflow"),
        ("missing", "missing_or_ambiguous_owner"),
        ("hidden", "Intended occurrence not fully visible"),
        ("over_cap", "Intended occurrence limit exceeded (N > 2)"),
    ],
)
def test_mutation_qualification_reasons(case, reason):
    targets = (
        ["target-a", "target-b", "target-c"] if case == "over_cap" else ["target-a"]
    )
    clean = [element("?", actor, input_text="?", source_key=None) for actor in targets]
    changed = [
        element(
            "Help",
            actor,
            input_text="Help",
            source_key="?",
            ellipsis_applied=False,
            overflow_x=case == "over_cap",
            glyph_bounds=[2, 20, 99, 40] if case == "over_cap" else [10, 20, 90, 40],
            visibility="hidden" if case == "hidden" else "full",
            visible_bounds=None if case == "hidden" else [10, 20, 90, 40],
        )
        for actor in targets
        if case != "missing"
    ]
    before = load_dump(canonical_bytes(dump_for(size=[100, 60], elements=clean)))
    after = load_dump(canonical_bytes(dump_for(size=[100, 60], elements=changed)))
    mutation = {
        "recipe": {
            "id": "help",
            "key": "?",
            "original": "",
            "replacement": "Help",
            "operation": "replace",
            "intended_class": "overflow",
        },
        "occurrences": [
            {
                "actor_path": actor,
                "input_text": "?",
                "screen": "tech-picker",
                "language": "de",
            }
            for actor in targets
        ],
    }
    result = api().verify_screen(png(), png(), before, after, [mutation])
    assert not result["qualified"]
    assert [item["reason"] for item in result["qualification_reasons"]] == [reason]
    assert result["review_flags"] == []
    if case == "over_cap":
        assert all(item["qualified"] for item in result["occurrences"])


def test_occurrence_matrix_counts_only_screenshots_retained_for_review():
    occurrence = {
        "intended_class": "overflow",
        "actor_path": "owner",
        "qualified": True,
    }
    one = {
        "screen": "options-gameplay",
        "language": "en",
        "role": "mutation",
        "verification": {"occurrences": [occurrence]},
    }
    retained = {**one, "png": "retained.png"}
    control = {**one, "role": "clean"}
    result = api().occurrence_matrix([retained, one, control])
    assert result == [
        {
            "screen": "options-gameplay",
            "language": "en",
            "intended_class": "overflow",
            "intended_occurrences": 2,
            "qualified_occurrences": 1,
            "distinct_targets": 1,
        }
    ]
