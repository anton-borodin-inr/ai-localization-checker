"""The partition is metadata, never a source of captured or labeled examples."""

import json
from pathlib import Path

import pytest

from l10n_checker.capture import CaptureError
from l10n_checker.screen_manifest import Inputs

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures/stage2"


@pytest.mark.parametrize("manifest", ["screens.json", "screens-v2.json"])
def test_partition_covers_exactly_the_committed_source_screens(manifest):
    from l10n_checker.screen_split import load_split

    inputs = Inputs(FIXTURES / manifest)
    ids = [s.id for s in inputs.manifest.screens]
    partition = load_split(FIXTURES / "split.json", ids)
    assert len(ids) == 10
    assert len(partition.dev) == len(partition.holdout) == 5
    assert set(partition.dev).isdisjoint(partition.holdout)
    assert set(partition.dev) | set(partition.holdout) == set(ids)
    assert {"tech-picker", "city-production"} <= set(partition.dev)


@pytest.mark.parametrize("selector", ["split", "ids"])
def test_selection_preserves_manifest_order_without_rewriting_manifest(selector):
    original = Inputs(FIXTURES / "screens.json")
    raw = original.manifest.model_dump()
    dev = json.loads((FIXTURES / "split.json").read_bytes())["dev"]
    assert hasattr(original, "select_screens"), (
        "manifest inputs need explicit selection"
    )
    selected = original.select_screens(
        **({"split": "dev"} if selector == "split" else {"screen_ids": dev[::-1]})
    )
    expected = [s.id for s in original.manifest.screens if s.id in dev]
    assert [s.id for s in selected.screens("de")] == expected
    assert [s.id for s in selected.screens("de", reverse=True)] == expected[::-1]
    assert [s.id for s in selected.screens()] == expected
    assert selected.sha256 == original.sha256
    assert selected.manifest.model_dump() == raw == original.manifest.model_dump()
    assert len(original.screens("de")) == 10
    assert selected.capture_selection(["en", "de"])["screen_ids"] == expected


@pytest.mark.parametrize(
    "selection",
    [
        {},
        {"split": "unknown"},
        {"screen_ids": []},
        {"screen_ids": ["unknown"]},
        {"screen_ids": ["tech-picker", "tech-picker"]},
        {"split": "dev", "screen_ids": ["tech-picker"]},
    ],
)
def test_invalid_selection_rejected(selection):
    inputs = Inputs(FIXTURES / "screens.json")
    with pytest.raises(CaptureError):
        inputs.select_screens(**selection)


@pytest.mark.parametrize(
    "change",
    [
        "version",
        "bool_version",
        "duplicate",
        "overlap",
        "missing",
        "unknown",
        "empty",
        "extra",
        "duplicate_key",
    ],
)
def test_invalid_partition_is_not_repaired(tmp_path, change):
    from l10n_checker.screen_split import load_split

    ids = [f"screen-{i}" for i in range(10)]
    value = {"schema_version": 1, "dev": ids[:5], "holdout": ids[5:]}
    if change == "version":
        value["schema_version"] = 2
    elif change == "bool_version":
        value["schema_version"] = True
    elif change == "duplicate":
        value["dev"].append(ids[0])
    elif change == "overlap":
        value["holdout"].append(ids[0])
    elif change == "missing":
        value["holdout"].pop()
    elif change == "unknown":
        value["holdout"].append("unknown-screen")
    elif change == "empty":
        value["dev"] = []
    elif change == "extra":
        value["other"] = []
    raw = json.dumps(value)
    if change == "duplicate_key":
        raw = raw.replace(
            '"schema_version": 1', '"schema_version": 1, "schema_version": 1'
        )
    path = tmp_path / "split.json"
    path.write_text(raw)
    with pytest.raises(CaptureError):
        load_split(path, ids)


def test_shortened_manifest_and_matching_registry_are_rejected(tmp_path):
    inputs = Inputs(FIXTURES / "screens.json")
    registry = json.loads((FIXTURES / "split.json").read_bytes())
    removed = registry["holdout"].pop()
    inputs.manifest = inputs.manifest.model_copy(
        update={"screens": [s for s in inputs.manifest.screens if s.id != removed]}
    )
    inputs.root = tmp_path
    (tmp_path / "split.json").write_text(json.dumps(registry))
    with pytest.raises(CaptureError, match="ten distinct"):
        inputs.select_screens(split="dev")


@pytest.mark.parametrize("size", [9, 11])
def test_matching_registry_does_not_allow_a_different_screen_count(tmp_path, size):
    from l10n_checker.screen_split import load_split

    ids = [f"screen-{i}" for i in range(size)]
    path = tmp_path / "split.json"
    path.write_text(
        json.dumps({"schema_version": 1, "dev": ids[:5], "holdout": ids[5:]})
    )
    with pytest.raises(CaptureError, match="ten distinct"):
        load_split(path, ids)


def test_manifest_id_collection_must_itself_have_ten_distinct_ids(tmp_path):
    from l10n_checker.screen_split import load_split

    ids = [f"screen-{i}" for i in range(9)]
    path = tmp_path / "split.json"
    path.write_text(
        json.dumps({"schema_version": 1, "dev": ids[:5], "holdout": ids[5:]})
    )
    with pytest.raises(CaptureError, match="ten distinct"):
        load_split(path, [*ids, ids[-1]])
