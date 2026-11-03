"""Versioned translation-only recipe inputs; never labels or game-file writes."""

import re
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from l10n_checker.capture import CaptureError
from l10n_checker.screen_manifest import Name, StrictModel, json_bytes

Language = Literal["en", "de"]
DefectClass = Literal["overflow", "wrong_language", "truncated_text", "other"]


class Target(StrictModel):
    screen: Name
    text: Annotated[str, Field(min_length=1)]
    match: Literal["exact", "contains"]

    @field_validator("text")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Blank target text")
        return value


class Recipe(StrictModel):
    id: Name
    language: Language
    intended_class: DefectClass
    mechanism: Literal["lengthen", "missing_translation", "foreign_text", "placeholder"]
    operation: Literal["add", "replace", "remove"]
    key: Annotated[str, Field(min_length=1)]
    original: str | None
    replacement: str | None
    targets: Annotated[list[Target], Field(min_length=1)]
    source_evidence: Annotated[str, Field(min_length=1)]

    @model_validator(mode="after")
    def semantics(self):
        for value in (self.key, self.original, self.replacement):
            if value is not None and any(c in value for c in ("\n", "\r", "\\", "\0")):
                raise ValueError("Recipe v1 requires literal single-line properties")
        if self.key != self.key.strip() or " = " in self.key:
            raise ValueError("Invalid literal source key")
        if (self.operation == "add") != (self.original is None):
            raise ValueError("Only add has an absent original")
        if (self.operation == "remove") != (self.replacement is None):
            raise ValueError("Only remove has an absent replacement")
        if self.replacement is not None and (
            not self.replacement.strip() or self.replacement == self.original
        ):
            raise ValueError("Empty or unchanged replacement")
        allowed = {
            "lengthen": {"overflow", "truncated_text"},
            "missing_translation": {"wrong_language"},
            "foreign_text": {"wrong_language"},
            "placeholder": {"other"},
        }
        if self.intended_class not in allowed[self.mechanism]:
            raise ValueError("Mechanism and intended class disagree")
        if self.mechanism == "missing_translation":
            if self.operation != "remove" or self.language != "de" or not self.original:
                raise ValueError(
                    "Source-language fallback needs a populated DE deletion"
                )
        elif self.operation == "remove":
            raise ValueError("Removal requires missing_translation")
        replacement = self.replacement or ""
        if self.mechanism == "lengthen" and len(replacement) <= len(
            self.original or self.key
        ):
            raise ValueError("Lengthening must extend the original text")
        if self.mechanism == "placeholder":
            source = set(re.findall(r"\[[^]]+\]", self.key))
            changed = set(re.findall(r"\[[^]]+\]", replacement))
            if not source or not changed - source:
                raise ValueError("A broken-placeholder recipe needs a mismatched token")
        selectors = [(t.screen, t.text, t.match) for t in self.targets]
        if len(set(selectors)) != len(selectors):
            raise ValueError("Duplicate target selector")
        return self

    def patch(self) -> dict:
        language = {"en": "English", "de": "German"}[self.language]
        return {
            "file": f"android/assets/jsons/translations/{language}.properties",
            "operation": self.operation,
            "key": self.key,
            "original": self.original,
            "replacement": self.replacement,
        }


class RecipeSet(StrictModel):
    schema_version: Literal[1]
    recipe_version: Name
    fork_commit: Annotated[str, Field(pattern=r"^[a-f0-9]{40}$")]
    recipes: Annotated[list[Recipe], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_ids(self):
        if len({r.id for r in self.recipes}) != len(self.recipes):
            raise ValueError("Duplicate recipe ID")
        edits = [tuple(r.patch().items()) for r in self.recipes]
        if len(set(edits)) != len(edits):
            raise ValueError("Duplicate semantic recipe edit")
        return self


def load_recipes(raw: bytes) -> RecipeSet:
    try:
        return RecipeSet.model_validate(json_bytes(raw))
    except (ValueError, TypeError) as exc:
        raise CaptureError(f"Invalid mutation recipes: {exc}") from exc
