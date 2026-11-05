"""Offline diagnostic attribution; no device, fixture or provider access."""

import csv
import importlib
import importlib.util
import io
import json
from copy import deepcopy

import pytest
from PIL import Image

from l10n_checker.capture import CaptureError
from l10n_checker.mutation_verify import compare_rgba
from l10n_checker.text_dump import TextDump


def api():
    assert importlib.util.find_spec("l10n_checker.mutation_diagnostics") is not None, (
        "Per-pixel attribution diagnostics missing"
    )
    return importlib.import_module("l10n_checker.mutation_diagnostics")


def png(changes=()):
    image = Image.new("RGBA", (8, 4), (10, 20, 30, 255))
    for xy, value in changes:
        image.putpixel(xy, value)
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


def element(identity="owner", box=(1, 1, 3, 3), *, owner=(0, 0, 4, 4), **changes):
    value = {
        "id": identity + "/draw-0",
        "logical_id": identity,
        "actor_path": identity,
        "source_key": "A",
        "source_keys": [],
        "input_text": "A",
        "display_text": "A",
        "bounds": list(owner) if owner is not None else None,
        "glyph_bounds": list(box),
        "visible_bounds": list(box),
        "drawn": True,
        "effective_alpha": 1,
        "visibility": "full",
        "clip_bounds": [0, 0, 8, 4],
        "clipped_fraction": 0,
        "clip_cause": "none",
        "ellipsis_applied": False,
        "overflow_x": False,
        "overflow_y": False,
        "font_scale": [1, 1],
        "pixel_scale": [1, 1],
        "decoration": False,
        "warnings": [] if owner is not None else ["owner_unavailable"],
        "lines": [
            {
                "text": "A",
                "bounds": list(box),
                "glyphs": [
                    {
                        "text": "A",
                        "bounds": list(box),
                        "visible_bounds": list(box),
                        "visibility": "full",
                    }
                ],
            }
        ],
    }
    value.update(changes)
    return value


def dump(elements):
    return TextDump.model_validate(
        {
            "dump_version": 1,
            "protocol_version": 2,
            "build_version_code": 1,
            "screen": "options-gameplay",
            "language": "English",
            "state_sha256": "0" * 64,
            "image_size": [8, 4],
            "viewport": [0, 0, 8, 4],
            "elements": elements,
        }
    )


def diagnose(before, after, changes, *, rectangles=(), occurrences=()):
    a, b = png(), png(changes)
    verification = {
        "pixels": compare_rgba(a, b, rectangles),
        "occurrences": list(occurrences),
        "passed": False,
    }
    return api().attribute_outside_pixels(a, b, before, after, verification)


def test_pixel_is_attributed_to_unchanged_glyph_with_raw_rgba():
    before = dump([element()])
    after = dump([element(id="new/draw-0", logical_id="new")])
    result = diagnose(before, after, [((1, 1), (11, 20, 30, 255))])
    counts = result["counts"]["pixel_center"]
    assert counts["glyph"] == counts["union"] == 1
    assert counts["owner_only"] == counts["elsewhere"] == 0
    assert result["pixels"][0]["before_rgba"] == [10, 20, 30, 255]
    assert result["pixels"][0]["absolute_rgba_delta"] == [1, 0, 0, 0]
    assert result["elements"][0]["before_draw_id"] == "owner/draw-0"
    assert result["elements"][0]["after_draw_id"] == "new/draw-0"
    assert result["elements"][0]["status"] == "stable_unmutated"


@pytest.mark.parametrize("change", ["target", "moved", "text", "metadata", "removed"])
def test_target_or_nonidentical_full_groups_never_count_as_stable(change):
    old = element()
    new = deepcopy(old)
    occurrences = []
    if change == "target":
        occurrences = [{"before_draw_ids": [old["id"]], "after_draw_ids": [new["id"]]}]
    elif change == "moved":
        new["bounds"] = [1, 0, 4, 4]
    elif change == "text":
        new = element(input_text="changed input")
    elif change == "metadata":
        new["warnings"] = ["source_unavailable"]
    result = diagnose(
        dump([old]),
        dump([] if change == "removed" else [new]),
        [((1, 1), (11, 20, 30, 255))],
        occurrences=occurrences,
    )
    assert result["counts"]["pixel_center"]["elsewhere"] == 1
    assert all(e["status"] != "stable_unmutated" for e in result["elements"])
    assert result["pixels"][0]["pixel_center"]["other_memberships"]
    if change != "target":
        assert result["changed_groups"]


def test_actual_changed_display_text_is_not_accepted():
    new = element()
    new["display_text"] = new["input_text"] = "B"
    new["lines"][0]["text"] = new["lines"][0]["glyphs"][0]["text"] = "B"
    result = diagnose(dump([element()]), dump([new]), [((1, 1), (11, 20, 30, 255))])
    assert result["counts"]["pixel_center"]["elsewhere"] == 1


def test_fractional_half_open_centers_and_outward_enclosure_are_separate():
    d = dump([element(box=(1.5, 0.5, 2.5, 1.5), owner=None)])
    changes = [((x, y), (11, 20, 30, 255)) for x, y in [(1, 0), (2, 0), (1, 1)]]
    result = diagnose(d, d, changes)
    assert result["counts"]["pixel_center"]["glyph"] == 1
    assert result["counts"].get("outward_enclosure", {}).get("glyph") == 3
    assert result["counts"]["pixel_center"]["elsewhere"] == 2
    assert result["geometry_diagnostics"][0]["owner_bounds_missing"] is True


def test_overlap_memberships_are_exhaustive_but_global_partition_is_disjoint():
    d = dump([element("first"), element("second", box=(2, 1, 4, 3))])
    result = diagnose(
        d,
        d,
        [
            ((2, 1), (10, 20, 30, 254)),
            ((0, 0), (11, 20, 30, 255)),
            ((7, 3), (11, 20, 30, 255)),
        ],
    )
    c = result["counts"]["pixel_center"]
    assert (
        c["glyph"],
        c["owner_only"],
        c["elsewhere"],
        c["union"],
        c["glyph_owner_overlap"],
    ) == (1, 1, 1, 2, 1)
    assert result["pixels"][1]["absolute_rgba_delta"] == [0, 0, 0, 1]
    assert len(result["pixels"][1]["pixel_center"]["memberships"]) == 2
    assert sum(e["counts"]["pixel_center"]["glyph"] for e in result["elements"]) == 2
    assert result["pixels"][0]["pixel_center"]["category"] == "owner_only"


def test_recorded_glyph_visibility_and_clip_bounds_limit_geometry():
    e = element(visibility="partial", clip_bounds=[2, 0, 8, 4])
    e["lines"][0]["glyphs"][0].update(visibility="partial", visible_bounds=[2, 1, 3, 3])
    d = dump([e])
    result = diagnose(d, d, [((1, 1), (11, 20, 30, 255)), ((2, 1), (11, 20, 30, 255))])
    assert result["counts"]["pixel_center"]["elsewhere"] == 1
    assert result["counts"]["pixel_center"]["glyph"] == 1


@pytest.mark.parametrize("visibility", ["hidden", "zero_alpha", "undrawn"])
def test_invisible_draws_have_no_qualifying_geometry(visibility):
    e = element(visibility="hidden", visible_bounds=None)
    e["lines"][0]["glyphs"][0].update(visibility="hidden", visible_bounds=None)
    if visibility == "zero_alpha":
        e["effective_alpha"] = 0
    if visibility == "undrawn":
        e["drawn"] = False
    d = dump([e])
    result = diagnose(d, d, [((1, 1), (11, 20, 30, 255))])
    assert result["counts"]["pixel_center"]["elsewhere"] == 1


def test_missing_glyph_geometry_is_not_replaced_with_aggregate_bounds():
    e = element(owner=None, display_text="", input_text="", lines=[])
    d = dump([e])
    result = diagnose(d, d, [((1, 1), (11, 20, 30, 255))])
    assert result["counts"]["pixel_center"]["elsewhere"] == 1
    assert result.get("geometry_diagnostics")


def test_export_preserves_all_rgba_channels_exhaustive_csv_and_images(tmp_path):
    assert hasattr(api(), "write_diagnostics"), "Offline artifact exporter missing"
    d = dump([element()])
    changes = [((1, 1), (10, 20, 30, 253)), ((7, 3), (12, 21, 30, 255))]
    result = diagnose(d, d, changes)
    paths = api().write_diagnostics(
        tmp_path / "analysis", result, png(), png(changes), context=0
    )
    with open(paths["csv"], newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 2
    assert json.loads(rows[0]["absolute_rgba_delta"]) == [0, 0, 0, 2]
    assert json.loads(rows[0]["pixel_center"])["memberships"][0]["display_text"] == "A"
    with open(paths["summary"], encoding="utf-8") as stream:
        data = json.load(stream)
    assert data["visualization"]["crop_exclusive"] == [1, 1, 8, 4]
    with Image.open(paths["difference_alpha_x50"]) as image:
        assert image.getpixel((0, 0)) == 100
    with Image.open(paths["control_crop"]) as image:
        assert image.mode == "RGBA"
    with Image.open(paths["contact_sheet"]) as image:
        image.verify()
    with pytest.raises(FileExistsError):
        api().write_diagnostics(tmp_path / "analysis", result, png(), png(changes))


def test_empty_mask_and_zero_differences_in_german_are_valid(tmp_path):
    assert hasattr(api(), "write_diagnostics"), "Offline artifact exporter missing"
    d = dump([]).model_copy(update={"language": "German"})
    result = diagnose(d, d, [])
    assert result["pixels"] == []
    assert all(
        value == 0 for counts in result["counts"].values() for value in counts.values()
    )
    paths = api().write_diagnostics(tmp_path / "empty", result, png(), png())
    with open(paths["csv"], newline="", encoding="utf-8") as stream:
        assert list(csv.DictReader(stream)) == []


def test_stale_pixel_verification_and_cross_dump_identity_are_rejected():
    d = dump([element()])
    other = d.model_copy(update={"state_sha256": "1" * 64})
    with pytest.raises(CaptureError, match="identity"):
        diagnose(d, other, [((1, 1), (11, 20, 30, 255))])
    with pytest.raises(CaptureError, match="replay"):
        api().attribute_outside_pixels(
            png(),
            png(),
            d,
            d,
            {
                "pixels": compare_rgba(png(), png([((1, 1), (11, 20, 30, 255))]), []),
                "occurrences": [],
            },
        )


def test_target_mask_membership_is_not_diagnostic_tolerance():
    d = dump([element()])
    result = diagnose(
        d,
        d,
        [((1, 1), (10, 20, 30, 254)), ((7, 3), (11, 20, 30, 255))],
        rectangles=[[1, 1, 2, 2]],
    )
    assert [(p["x"], p["y"]) for p in result["pixels"]] == [(7, 3)]


@pytest.mark.parametrize("channel", range(4))
def test_each_rgba_channel_independently_counts_a_changed_pixel(channel):
    value = [10, 20, 30, 255]
    value[channel] -= 1
    d = dump([element()])
    result = diagnose(d, d, [((1, 1), tuple(value))])
    expected = [0, 0, 0, 0]
    expected[channel] = 1
    assert len(result["pixels"]) == 1
    assert result["pixels"][0]["absolute_rgba_delta"] == expected


def test_changed_secondary_draw_invalidates_the_entire_ordered_group():
    first, second = element(), element(id="owner/draw-1")
    changed = deepcopy(second)
    changed["bounds"] = [0, 0, 5, 4]
    result = diagnose(
        dump([first, second]), dump([first, changed]), [((1, 1), (11, 20, 30, 255))]
    )
    assert result["counts"]["pixel_center"]["elsewhere"] == 1
    assert len(result["changed_groups"]) == 1
    assert not any(e["status"] == "stable_unmutated" for e in result["elements"])


def test_fallback_logical_id_stability_retains_unmapped_actor_diagnostic():
    d = dump([element(actor_path=None)])
    result = diagnose(d, d, [((1, 1), (11, 20, 30, 255))])
    assert result["counts"]["pixel_center"]["glyph"] == 1
    assert result["geometry_diagnostics"][0]["actor_path_missing"] is True


def test_unknown_target_draw_id_is_rejected():
    d = dump([element()])
    with pytest.raises(CaptureError, match="target draw ID"):
        diagnose(d, d, [], occurrences=[{"before_draw_ids": ["missing"]}])


def test_same_helper_accepts_all_twenty_dev_screen_language_pass_pairs():
    measured = []
    for screen in (
        "options-gameplay",
        "tech-picker",
        "city-production",
        "empire-stats",
        "civilopedia",
    ):
        for language in ("English", "German"):
            for pass_number in (1, 2):
                d = dump([element()]).model_copy(
                    update={"screen": screen, "language": language}
                )
                result = diagnose(d, d, [((1, 1), (10, 20, 30, 254))])
                measured.append(
                    (
                        screen,
                        language,
                        pass_number,
                        result["counts"]["pixel_center"]["glyph"],
                    )
                )
    assert len(measured) == 20
    assert {record[3] for record in measured} == {1}
