"""Load the single source-screen partition without reading any capture data."""

from collections.abc import Collection
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

from pydantic import Field, model_validator

from l10n_checker.capture import CaptureError
from l10n_checker.screen_manifest import Name, StrictModel, digest, json_bytes


class _SplitModel(StrictModel):
    schema_version: Annotated[int, Field(ge=1, le=1)]
    dev: Annotated[list[Name], Field(min_length=1)]
    holdout: Annotated[list[Name], Field(min_length=1)]

    @model_validator(mode="after")
    def disjoint_unique_ids(self):
        for ids in (self.dev, self.holdout):
            if len(set(ids)) != len(ids):
                raise ValueError("Duplicate screen ID in split")
        if set(self.dev) & set(self.holdout):
            raise ValueError("Dev and holdout must be disjoint")
        return self


@dataclass(frozen=True)
class ScreenSplit:
    dev: tuple[str, ...]
    holdout: tuple[str, ...]
    sha256: str


@dataclass(frozen=True)
class ScreenSelection:
    screen_ids: tuple[str, ...]
    split: str | None
    split_sha256: str
    contains_holdout: bool

    def metadata(self) -> dict:
        return {
            "screen_ids": list(self.screen_ids),
            "split": self.split,
            "split_sha256": self.split_sha256,
        }


def load_split(path: Path, screen_ids: Collection[str]) -> ScreenSplit:
    """Validate exact manifest coverage; callers supply the manifest's IDs."""
    try:
        raw = path.read_bytes()
        value = _SplitModel.model_validate(json_bytes(raw))
        if len(screen_ids) != 10 or len(set(screen_ids)) != 10:
            raise ValueError(
                "Manifest must contain exactly ten distinct source screen IDs"
            )
        if set(value.dev) | set(value.holdout) != set(screen_ids):
            raise ValueError("Split must cover exactly the manifest's source screens")
    except (OSError, ValueError, TypeError) as exc:
        raise CaptureError(f"Invalid screen split: {exc}") from exc
    return ScreenSplit(tuple(value.dev), tuple(value.holdout), digest(raw))
