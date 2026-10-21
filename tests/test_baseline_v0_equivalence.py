"""Independent default-path regression, committed before OCR changes."""

import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest
from test_baseline import FakeOcr
from test_baseline import inputs as make_inputs

from l10n_checker import baseline
from l10n_checker.unciv_text import skeleton

ROOT = Path(__file__).resolve().parents[1]
ORACLE = ROOT / "tests/oracles/baseline_v0.py"
ORACLE_SHA256 = "23fc4b8f5a51120776ee8670f0cb90e4c741ef50617b512e00832fc1caa3cafb"
spec = importlib.util.spec_from_file_location("baseline_v0_oracle", ORACLE)
oracle = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = oracle
spec.loader.exec_module(oracle)


def test_oracle_is_frozen():
    assert hashlib.sha256(ORACLE.read_bytes()).hexdigest() == ORACLE_SHA256


@pytest.fixture
def baseline_inputs(tmp_path):
    return make_inputs.__wrapped__(tmp_path)


@pytest.mark.parametrize(
    "language,variant,text",
    [
        ("en", "clean", "Mining"),
        ("de", "clean", "Bergbau"),
        ("de", "injected", "Bergbau und Erzgew..."),
        ("de", "injected", "unrelated"),
    ],
)
def test_default_matches_frozen_v0(
    baseline_inputs, monkeypatch, language, variant, text
):
    images, manifest, inventory, fork, runs = baseline_inputs
    # Fix only operational values; everything else must compare byte-for-byte.
    for module in (baseline, oracle):
        monkeypatch.setattr(module, "new_run_id", lambda: "fixed")
        monkeypatch.setattr(module.time, "monotonic", lambda: 10.0)
        monkeypatch.setattr(module, "Tesseract", lambda: FakeOcr(text))
    actual, actual_dir = baseline.run_baseline(
        images[language, variant], manifest, inventory, fork, runs / "actual"
    )
    expected, expected_dir = oracle.run_baseline(
        images[language, variant], manifest, inventory, fork, runs / "oracle"
    )
    assert actual.model_dump() == expected.model_dump()
    assert {p.name for p in actual_dir.iterdir()} == {
        p.name for p in expected_dir.iterdir()
    }
    for path in actual_dir.iterdir():
        assert path.read_bytes() == (expected_dir / path.name).read_bytes()


def test_slice_replay_matches_oracle_when_evidence_exists():
    """Replay real T0 TSV without loading an OCR model or requiring the fork."""
    summary = ROOT / "docs/evidence/48/summary.json"
    if not summary.exists():
        pytest.skip("real slice evidence is added after the fixed experiment")
    rows = json.loads(summary.read_text())["rows"]
    selected = [
        r for r in rows if r["configuration"] == "T0" and r["scope"] == "labelled"
    ]
    assert len(selected) == 6
    for index, row in enumerate(selected):
        record = ROOT / row["record"]
        raw = (record / "ocr.tsv").read_text()
        entries = json.loads((record / "source-entries.json").read_text())
        inventory = baseline.Inventory.model_validate_json(
            (ROOT / "docs/evidence/12/tech-picker.json").read_text()
        )
        # Source entry snapshots are captured by the unchanged exact-commit renderer.
        tables = {
            lang: baseline.TranslationTable(
                {
                    skeleton(entry["key"]): (
                        entry["key"],
                        entry["value"],
                        entry["line"],
                    )
                    for entry in table
                    if entry["line"] is not None
                }
            )
            for lang, table in entries.items()
        }
        outputs = []
        for module in (baseline, oracle):
            words = module.parse_tsv(raw, (2400, 1080))
            # Copy mutable lookup tracking independently for each detector.
            findings, diagnostics = module.detect(
                inventory, copy.deepcopy(tables), row["language"], words, (2400, 1080)
            )
            outputs.append(([f.model_dump() for f in findings], diagnostics))
        assert outputs[0] == outputs[1], index
        assert (
            outputs[0][0]
            == json.loads((record / "result.json").read_text())["findings"]
        )
