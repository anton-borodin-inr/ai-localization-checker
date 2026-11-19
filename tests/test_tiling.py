import hashlib

import pytest
from PIL import Image

from l10n_checker.tiling import crop_tiles, region_candidates


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
