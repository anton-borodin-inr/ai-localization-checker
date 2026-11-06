"""Strict dynamic isolation: a one-channel, one-pixel change is a failure."""

import importlib
import importlib.util
import io

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


@pytest.mark.parametrize(
    "value,delta",
    [((11, 20, 30, 255), [1, 0, 0, 0]), ((10, 20, 30, 254), [0, 0, 0, 1])],
)
def test_one_pixel_any_rgba_channel_fails_without_tolerance(value, delta):
    result = api().compare_rgba(png(), png([((99, 59), value)]), [])
    assert result["outside"]["different_pixels"] == 1
    assert result["outside"]["bounding_box"] == [99, 59, 100, 60]
    assert result["outside"]["max_channel_deltas"] == delta
    assert result["passed"] is False


def test_mask_union_rounds_outward_without_bridging_targets():
    result = api().compare_rgba(
        png(),
        png([((5, 5), (11, 20, 30, 255)), ((50, 5), (11, 20, 30, 255))]),
        [[4.2, 4.2, 5.2, 5.2], [90, 0, 100, 10]],
    )
    assert result["inside"]["different_pixels"] == 1
    assert result["outside"]["different_pixels"] == 1
    assert result["mask"]["rectangles"] == [[4, 4, 6, 6], [90, 0, 100, 10]]
    assert result["mask"]["policy"] == "target-extents-floor-ceil-v1"


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


def test_changed_unmutated_element_inside_target_mask_is_not_hidden():
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
    result = api().verify_screen(png(), png(), before, after, [mutation])
    assert result["passed"] is False
    assert result["changed_unmutated_elements"]
    assert result["occurrences"][0]["qualified"] is True


def test_missing_and_fitting_overflow_are_unqualified():
    first = element(
        "?", "target", input_text="?", source_key=None, ellipsis_applied=False
    )
    after = element(
        "Help", "target", input_text="Help", source_key="?", ellipsis_applied=False
    )
    before_dump = load_dump(canonical_bytes(dump_for(size=[100, 60], elements=[first])))
    after_dump = load_dump(canonical_bytes(dump_for(size=[100, 60], elements=[after])))
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
    result = api().verify_screen(png(), png(), before_dump, after_dump, [mutation])
    assert not result["passed"] and not result["occurrences"][0]["qualified"]


def test_split_rate_counts_unique_tested_multi_recipe_nodes():
    records = [
        {"id": "a", "recipe_ids": ["x", "y"], "split": True},
        {"id": "a", "recipe_ids": ["x", "y"], "split": True},
        {"id": "b", "recipe_ids": ["x"], "split": False},
        {"id": "c", "recipe_ids": ["q", "r"], "split": False},
    ]
    assert api().split_rate(records) == {
        "split_batches": 1,
        "tested_multi_recipe_batches": 2,
        "rate": 0.5,
    }
    assert api().split_rate([])["rate"] is None


def test_occurrence_matrix_excludes_controls_repeats_and_target_aliases():
    assert hasattr(api(), "occurrence_matrix"), "Runtime occurrence accounting missing"
    one = {
        "screen": "options-gameplay",
        "language": "en",
        "pass": 1,
        "role": "mutation",
        "verification": {
            "occurrences": [
                {"intended_class": "overflow", "actor_path": "owner", "qualified": True}
            ]
        },
    }
    second = {**one, "pass": 2}
    control = {**one, "role": "clean"}
    result = api().occurrence_matrix([one, one, second, control])
    assert result == [
        {
            "screen": "options-gameplay",
            "language": "en",
            "intended_class": "overflow",
            "intended_occurrences": 2,
            "qualified_occurrences": 2,
            "distinct_targets": 1,
        }
    ]
