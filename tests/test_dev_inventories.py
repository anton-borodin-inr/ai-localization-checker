"""Verify committed Stage 4 dev screen inventories match schema and dev split."""

import json
from pathlib import Path

from l10n_checker.baseline import Inventory
from l10n_checker.screen_split import load_split

ROOT = Path(__file__).resolve().parents[1]
INVENTORIES_DIR = ROOT / "fixtures/baseline"
SPLIT_PATH = ROOT / "fixtures/stage2/split.json"
MANIFEST_PATH = ROOT / "fixtures/stage2/screens-v2.json"
EXPECTED_BASE_COMMIT = "b534a8ae67c390412984869c7a03b168d532c36c"


def test_dev_inventories_cover_all_dev_screens_and_validate():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    split = load_split(SPLIT_PATH, [screen["id"] for screen in manifest["screens"]])
    expected_screens = set(split.dev)
    files = sorted(INVENTORIES_DIR.glob("*.json"))
    assert {path.stem for path in files} == expected_screens

    total_slots = 0
    for path in files:
        raw = json.loads(path.read_text(encoding="utf-8"))
        inventory = Inventory.model_validate(raw)
        assert inventory.screen == path.stem
        assert inventory.base_commit == EXPECTED_BASE_COMMIT
        total_slots += len(inventory.slots)

    assert total_slots == 114
