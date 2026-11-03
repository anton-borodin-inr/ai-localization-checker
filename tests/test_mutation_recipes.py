"""Offline mutation contracts; these are synthetic tests, never labels."""

import importlib
import importlib.util

import pytest

from l10n_checker.capture import CaptureError
from l10n_checker.text_dump import canonical_bytes


def recipe(**changes):
    value = {
        "id": "mining-long-en",
        "language": "en",
        "intended_class": "truncated_text",
        "mechanism": "lengthen",
        "operation": "replace",
        "key": "Mining",
        "original": "",
        "replacement": "Mining and ore extraction",
        "targets": [{"screen": "tech-picker", "text": "Mining", "match": "exact"}],
        "source_evidence": "TechButton.kt:28-32; issue 45 truncation-mining",
    }
    value.update(changes)
    return value


def document(*recipes):
    return {
        "schema_version": 1,
        "recipe_version": "stage3-v1",
        "fork_commit": "b534a8ae67c390412984869c7a03b168d532c36c",
        "recipes": list(recipes or [recipe()]),
    }


def api():
    assert importlib.util.find_spec("l10n_checker.mutation_recipes") is not None, (
        "The versioned mutation recipe loader is missing"
    )
    return importlib.import_module("l10n_checker.mutation_recipes")


def test_loads_exact_english_rhs_patch_without_renaming_key():
    recipes = api().load_recipes(canonical_bytes(document()))
    edit = recipes.recipes[0].patch()
    assert edit == {
        "file": "android/assets/jsons/translations/English.properties",
        "operation": "replace",
        "key": "Mining",
        "original": "",
        "replacement": "Mining and ore extraction",
    }
    assert recipes.fork_commit == document()["fork_commit"]


@pytest.mark.parametrize(
    "changes",
    [
        {"operation": "add"},
        {"operation": "replace", "original": None},
        {"operation": "remove"},
        {"replacement": ""},
        {"replacement": "", "original": ""},
        {"replacement": "Mining"},
        {"key": "Mining\nWorker"},
        {"key": "Mining = Worker"},
        {"key": "Mining\\nWorker"},
        {"key": " Mining"},
        {"replacement": "text\nWorker = wrong"},
        {"replacement": "text\\nWorker"},
        {"mechanism": "placeholder"},
        {"intended_class": "overflow", "mechanism": "foreign_text"},
        {"targets": [{"screen": "tech-picker", "text": " ", "match": "contains"}]},
    ],
)
def test_rejects_invalid_patch_semantics_without_repairing_tokens(changes):
    with pytest.raises(CaptureError, match="Invalid mutation recipes"):
        api().load_recipes(canonical_bytes(document(recipe(**changes))))


def test_real_missing_translation_is_de_only_and_requires_populated_original():
    missing = recipe(
        id="mining-missing-de",
        language="de",
        intended_class="wrong_language",
        mechanism="missing_translation",
        operation="remove",
        original="Bergbau",
        replacement=None,
    )
    parsed = api().load_recipes(canonical_bytes(document(missing)))
    assert parsed.recipes[0].patch()["replacement"] is None
    for changes in ({"language": "en"}, {"original": ""}, {"operation": "replace"}):
        with pytest.raises(CaptureError):
            api().load_recipes(canonical_bytes(document({**missing, **changes})))


def test_rejects_duplicate_ids_and_duplicate_target_selectors():
    for value in (
        document(recipe(), recipe()),
        document(recipe(targets=recipe()["targets"] * 2)),
    ):
        with pytest.raises(CaptureError):
            api().load_recipes(canonical_bytes(value))


@pytest.mark.parametrize(
    "changes",
    [
        {},
        {"intended_class": "overflow"},
        {
            "targets": [
                {"screen": "options-gameplay", "text": "Mining", "match": "exact"}
            ]
        },
    ],
)
def test_rejects_identical_semantic_edits_with_different_recipe_ids(changes):
    alias = recipe(id="mining-alias-en", **changes)
    with pytest.raises(CaptureError, match="Duplicate.*edit"):
        api().load_recipes(canonical_bytes(document(recipe(), alias)))


def test_english_foreign_text_and_mismatched_placeholder_are_supported():
    foreign = recipe(
        id="worker-foreign-en",
        key="Worker",
        intended_class="wrong_language",
        mechanism="foreign_text",
        replacement="Arbeiter",
    )
    placeholder = recipe(
        id="research-placeholder-en",
        key="Research [technology]",
        intended_class="other",
        mechanism="placeholder",
        replacement="Research [amount]",
    )
    assert (
        len(api().load_recipes(canonical_bytes(document(foreign, placeholder))).recipes)
        == 2
    )


def test_versioned_catalog_has_every_mechanism_without_global_hourglass():
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "fixtures/stage3/recipes-v1.json"
    assert path.is_file(), "The versioned dev recipe catalog is missing"
    catalog = api().load_recipes(path.read_bytes())
    assert {r.mechanism for r in catalog.recipes} == {
        "lengthen",
        "missing_translation",
        "foreign_text",
        "placeholder",
    }
    assert not any(r.key == "⏳" for r in catalog.recipes)
    for language in ("en", "de"):
        overflow = [
            r
            for r in catalog.recipes
            if r.language == language and r.intended_class == "overflow"
        ]
        assert overflow[0].key == "?"
        assert overflow[0].replacement == {"en": "Help", "de": "Hilfe"}[language]
    # Keys remain literal; replacement values alone make the English defect.
    assert any(
        r.language == "en" and r.intended_class == "wrong_language"
        for r in catalog.recipes
    )
