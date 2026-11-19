import hashlib

import pytest
from PIL import Image

from l10n_checker.tiling import (
    crop_tiles,
    grid_2x2_boxes,
    map_region,
    region_candidates,
)


def test_crop_pixels_provenance_and_source_unchanged(tmp_path):
    source = tmp_path / "source.png"
    image = Image.new("RGB", (9, 6))
    image.putdata([(x * 20, y * 30, x + y) for y in range(6) for x in range(9)])
    image.save(source)
    before = source.read_bytes()
    records = crop_tiles(source, tmp_path / "tiles", {"part": (2, 1, 8, 5)})
    with Image.open(records[0]["path"]) as tile:
        assert tile.size == (6, 4)
        assert tile.tobytes() == image.crop((2, 1, 8, 5)).tobytes()
    assert records[0]["source_sha256"] == hashlib.sha256(before).hexdigest()
    assert source.read_bytes() == before
    with pytest.raises(FileExistsError):
        crop_tiles(source, tmp_path / "tiles", {"part": (2, 1, 8, 5)})


@pytest.mark.parametrize("box", [(-1, 0, 3, 2), (0, 0, 5, 2), (1, 0, 1, 2)])
def test_invalid_crop_refused_before_writing(screenshot, tmp_path, box):
    destination = tmp_path / "tiles"
    with pytest.raises(ValueError):
        crop_tiles(screenshot, destination, {"part": box})
    assert not destination.exists()


def test_grid_mapping_preserves_ambiguity():
    assert region_candidates("center", (0, 0, 2400, 1080), (2400, 1080)) == ["center"]
    assert region_candidates("center", (0, 900, 2400, 1080), (2400, 1080)) == ["bottom"]
    assert region_candidates("right", (0, 0, 1320, 920), (2400, 1080)) == [
        "top",
        "center",
    ]


def test_grid_2x2_boxes_and_map_region_alignment():
    size = (2400, 1080)
    boxes = grid_2x2_boxes(size)
    assert boxes == {
        "top-left": (0, 0, 1440, 648),
        "top-right": (960, 0, 2400, 648),
        "bottom-left": (0, 432, 1440, 1080),
        "bottom-right": (960, 432, 2400, 1080),
    }
    # Every local cell maps to one of its region_candidates, and all 9 full-screen
    # cells are covered across the 4 tiles.
    covered = set()
    for box in boxes.values():
        for local in (
            "top-left",
            "top",
            "top-right",
            "left",
            "center",
            "right",
            "bottom-left",
            "bottom",
            "bottom-right",
        ):
            mapped = map_region(local, box, size)
            assert mapped in region_candidates(local, box, size)
            covered.add(mapped)
    assert len(covered) == 9
    # Shared overlap cells map to the exact same full-screen region from each tile.
    assert (
        map_region("top-right", boxes["top-left"], size)
        == map_region("top-left", boxes["top-right"], size)
        == "top"
    )
    assert (
        map_region("bottom-left", boxes["top-left"], size)
        == map_region("top-left", boxes["bottom-left"], size)
        == "left"
    )
    assert (
        map_region("bottom-right", boxes["top-left"], size)
        == map_region("bottom-left", boxes["top-right"], size)
        == map_region("top-right", boxes["bottom-left"], size)
        == map_region("top-left", boxes["bottom-right"], size)
        == "center"
    )
