"""Strict engine-dump input; no OCR, translation lookup or detector imports."""

import io
import json
import math
import re
from typing import Annotated, Literal

from PIL import Image
from pydantic import Field, ValidationError, field_validator, model_validator

from l10n_checker.capture import PACKAGE, CaptureError
from l10n_checker.screen_manifest import Hash, StrictModel, digest, json_bytes

Rect = Annotated[list[float], Field(min_length=4, max_length=4)]
Scale = Annotated[
    list[Annotated[float, Field(gt=0)]], Field(min_length=2, max_length=2)
]
Visibility = Literal["full", "partial", "hidden"]
Fraction = Annotated[float, Field(ge=0, le=1)]


def canonical_bytes(value) -> bytes:
    """Canonical client payload/candidate bytes; dumps themselves stay verbatim."""

    def numbers(item):
        if isinstance(item, float):
            if not math.isfinite(item):
                raise ValueError("Non-finite JSON number")
            return int(item) if item.is_integer() else item
        if isinstance(item, dict):
            return {k: numbers(v) for k, v in item.items()}
        if isinstance(item, list):
            return [numbers(v) for v in item]
        return item

    return (
        json.dumps(
            numbers(value),
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def rectangle(value):
    if value is not None and (value[2] < value[0] or value[3] < value[1]):
        raise ValueError("Reversed rectangle")
    return value


class Glyph(StrictModel):
    text: str
    bounds: Rect
    visible_bounds: Rect | None
    visibility: Visibility

    _rect = field_validator("bounds", "visible_bounds")(rectangle)

    @model_validator(mode="after")
    def visible(self):
        if (self.visibility == "hidden") != (self.visible_bounds is None):
            raise ValueError("Glyph visibility disagrees with visible bounds")
        return self


class Line(StrictModel):
    text: str
    bounds: Rect
    glyphs: list[Glyph]

    _rect = field_validator("bounds")(rectangle)

    @model_validator(mode="after")
    def text_mapping(self):
        if "".join(g.text for g in self.glyphs) != self.text:
            raise ValueError("Line glyph/text mapping disagrees")
        return self


class Element(StrictModel):
    id: Annotated[str, Field(min_length=1)]
    logical_id: Annotated[str, Field(min_length=1)]
    actor_path: str | None
    source_key: str | None
    source_keys: list[str]
    input_text: str | None
    display_text: str
    bounds: Rect | None
    glyph_bounds: Rect
    visible_bounds: Rect | None
    drawn: bool
    effective_alpha: Fraction
    visibility: Visibility
    clip_bounds: Rect | None
    clipped_fraction: Fraction
    clip_cause: Literal["none", "ancestor_scissor", "screen", "mixed"]
    ellipsis_applied: bool
    overflow_x: bool
    overflow_y: bool
    font_scale: Scale
    pixel_scale: Scale
    decoration: bool
    warnings: list[str]
    lines: list[Line]

    _rect = field_validator("bounds", "glyph_bounds", "visible_bounds", "clip_bounds")(
        rectangle
    )

    @model_validator(mode="after")
    def consistent(self):
        if "\n".join(line.text for line in self.lines) != self.display_text:
            raise ValueError("Displayed text disagrees with rendered lines")
        if (self.visibility == "hidden") != (self.visible_bounds is None):
            raise ValueError("Element visibility disagrees with visible bounds")
        if (
            not self.drawn or self.effective_alpha == 0
        ) and self.visibility != "hidden":
            raise ValueError("Undrawn/zero-alpha element cannot be visible")
        if self.bounds is None and not self.warnings:
            raise ValueError("Unknown owner must carry a warning")
        if self.visibility == "full" and any(
            glyph.visibility != "full" for line in self.lines for glyph in line.glyphs
        ):
            raise ValueError("Fully visible element contains clipped glyphs")
        return self


class TextDump(StrictModel):
    dump_version: Literal[1]
    protocol_version: Literal[2]
    build_version_code: Annotated[int, Field(gt=0)]
    screen: str
    language: str
    state_sha256: Hash
    image_size: Annotated[
        list[Annotated[int, Field(gt=0)]], Field(min_length=2, max_length=2)
    ]
    viewport: Rect
    elements: list[Element]

    _rect = field_validator("viewport")(rectangle)

    @model_validator(mode="after")
    def unique_draws(self):
        if len({e.id for e in self.elements}) != len(self.elements):
            raise ValueError("Duplicate element id")
        return self


def load_dump(data: bytes, *, expected: dict | None = None) -> TextDump:
    if len(data) > 32 * 1024 * 1024:
        raise CaptureError("Engine dump exceeds 32 MiB")
    try:
        result = TextDump.model_validate(json_bytes(data))
        for key, value in (expected or {}).items():
            if getattr(result, key) != value:
                raise ValueError(f"Engine dump {key} mismatch")
        return result
    except (ValueError, TypeError, ValidationError) as exc:
        raise CaptureError(f"Invalid engine text dump: {exc}") from exc


def read_dump(device, event: dict, expected: dict) -> bytes:
    if (
        re.fullmatch(r"files/l10n-hook/[A-Za-z0-9._-]{1,64}\.json", event["file"])
        is None
    ):
        raise CaptureError("Engine dump path is outside declared hook outputs")
    data = device.run("exec-out", "run-as", PACKAGE, "cat", event["file"])
    if digest(data) != event["sha256"]:
        raise CaptureError("Engine dump SHA-256 mismatch")
    load_dump(data, expected=expected)
    return data


def rgba_digest(png: bytes) -> str:
    with Image.open(io.BytesIO(png)) as image:
        return digest(image.convert("RGBA").tobytes())


def grid_region(bounds: list[float], size: list[int]) -> str:
    x = (bounds[0] + bounds[2]) / 2
    y = (bounds[1] + bounds[3]) / 2
    column = min(2, max(0, math.floor(x * 3 / size[0])))
    row = min(2, max(0, math.floor(y * 3 / size[1])))
    return (
        ("top-left", "top", "top-right"),
        ("left", "center", "right"),
        ("bottom-left", "bottom", "bottom-right"),
    )[row][column]


def scene_to_pixels(bounds, stage_size, viewport, image_height):
    """Scene2D bottom-left layout rectangle -> top-left physical PNG rectangle."""
    x, y, width, height = viewport  # OpenGL viewport, bottom-left origin
    left, bottom, right, top = bounds
    return [
        x + left * width / stage_size[0],
        image_height - (y + top * height / stage_size[1]),
        x + right * width / stage_size[0],
        image_height - (y + bottom * height / stage_size[1]),
    ]
