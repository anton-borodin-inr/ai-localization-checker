"""Pixel-preserving PNG crops. No provider, SDK, or detector dependency."""

import hashlib
from pathlib import Path

from PIL import Image

Box = tuple[int, int, int, int]
DEFAULT_TILING = "none"
TILING_MODES = ("none", "2x2")
_NAMES = (
    "top-left",
    "top",
    "top-right",
    "left",
    "center",
    "right",
    "bottom-left",
    "bottom",
    "bottom-right",
)


def grid_2x2_boxes(size: tuple[int, int]) -> dict[str, Box]:
    """2x2 overlapping tiles (3/5 width x 3/5 height; 1440x648 on 2400x1080)."""
    width, height = size
    tile_w = round(width * 3 / 5)
    tile_h = round(height * 3 / 5)
    if not (0 < tile_w <= width and 0 < tile_h <= height):
        raise ValueError(f"Invalid image size for 2x2 tiling: {size!r}")
    return {
        "top-left": (0, 0, tile_w, tile_h),
        "top-right": (width - tile_w, 0, width, tile_h),
        "bottom-left": (0, height - tile_h, tile_w, height),
        "bottom-right": (width - tile_w, height - tile_h, width, height),
    }


def map_region(region: str, box: Box, size: tuple[int, int]) -> str:
    """Map a tile's local 3x3 grid cell to the full-screen 3x3 cell of its centre."""
    index = _NAMES.index(region)
    row, col = divmod(index, 3)
    left, top, right, bottom = box
    width, height = size
    if not (0 <= left < right <= width and 0 <= top < bottom <= height):
        raise ValueError(f"Invalid tile box {box!r} for image size {size!r}")
    cx = left + (right - left) * (col + 0.5) / 3
    cy = top + (bottom - top) * (row + 0.5) / 3
    full_col = min(2, int(cx * 3 / width))
    full_row = min(2, int(cy * 3 / height))
    return _NAMES[full_row * 3 + full_col]


def crop_tiles(source: Path, destination: Path, boxes: dict[str, Box]) -> list[dict]:
    """Create new crops and provenance; refuse overwrite and invalid rectangles."""
    original = source.read_bytes()
    source_hash = hashlib.sha256(original).hexdigest()
    with Image.open(source) as image:
        if image.format != "PNG":
            raise ValueError("The source must be a PNG")
        width, height = image.size
        for name, (left, top, right, bottom) in boxes.items():
            if Path(name).name != name or name in ("", ".", ".."):
                raise ValueError("Tile names must be single path components")
            if not (0 <= left < right <= width and 0 <= top < bottom <= height):
                raise ValueError(f"Invalid crop rectangle: {name}")
        # Exclusive creation makes a repeated preparation fail before any writes.
        destination.mkdir(parents=True, exist_ok=False)
        records = []
        for name, box in boxes.items():
            target = destination / f"{name}.png"
            image.crop(box).save(target, format="PNG")
            records.append(
                {
                    "name": name,
                    "path": str(target),
                    "box": list(box),
                    "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                    "source_sha256": source_hash,
                    "source_size": [width, height],
                }
            )
    if source.read_bytes() != original:
        raise RuntimeError("Source changed while preparing tiles")
    return records


def region_candidates(region: str, box: Box, size: tuple[int, int]) -> list[str]:
    """Map a local grid cell to all intersecting original-image grid cells.

    A coarse local region does not identify a pixel. Preserve that uncertainty
    rather than claiming its cell centre was the text centre.
    """
    index = _NAMES.index(region)
    row, col = divmod(index, 3)
    left, top, right, bottom = box
    x1 = left + (right - left) * col / 3
    x2 = left + (right - left) * (col + 1) / 3
    y1 = top + (bottom - top) * row / 3
    y2 = top + (bottom - top) * (row + 1) / 3
    width, height = size
    return [
        _NAMES[r * 3 + c]
        for r in range(3)
        for c in range(3)
        if max(x1, width * c / 3) < min(x2, width * (c + 1) / 3)
        and max(y1, height * r / 3) < min(y2, height * (r + 1) / 3)
    ]
