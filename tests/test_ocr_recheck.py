import shutil
from pathlib import Path

from test_ocr_experiment import copied_inputs as make_copied_inputs

from l10n_checker import ocr_recheck
from l10n_checker.ocr_experiment import read
from l10n_checker.vision import CheckResult

ROOT = Path(__file__).resolve().parents[1]


def test_recheck_scores_fresh_trio_records_without_changing_default(
    tmp_path, monkeypatch
):
    root = make_copied_inputs.__wrapped__(tmp_path)
    recorded = read(ROOT / "docs/evidence/48/summary.json")
    selected = [
        r
        for r in recorded["rows"]
        if r["configuration"] == "E2" and r["pass"] == 1 and r["scope"] == "labelled"
    ]
    calls, lifecycle = [], []

    class FakeEngine:
        def __init__(self, engine, preprocessing, models):
            lifecycle.append((engine, preprocessing))

        def close(self):
            lifecycle.append("closed")

    def replay(image, manifest, inventory, fork, runs, engine):
        row = next(r for r in selected if Path(r["image"]).name == image.name)
        destination = runs / image.stem
        shutil.copytree(ROOT / row["record"], destination)
        calls.append(image.name)
        return CheckResult.model_validate(
            read(destination / "result.json")
        ), destination

    monkeypatch.setattr(ocr_recheck, "ConfiguredOcr", FakeEngine)
    monkeypatch.setattr(ocr_recheck, "run_baseline", replay)
    result = ocr_recheck.recheck(
        root, Path("unused"), root / "data/rechecks", root / "data/models"
    )
    expected = next(
        t for t in recorded["totals"] if t["configuration"] == "E2" and t["pass"] == 1
    )
    assert result["metrics"] == expected["metrics"]
    assert result["primary_exact"] == expected["primary_exact"]
    assert result["primary_fuzzy"] == expected["primary_fuzzy"]
    assert result["clean_fp"] == expected["clean_fp"]
    assert len(calls) == len(set(calls)) == 3
    assert all(name.endswith(("1271001.png", "1271002.png")) for name in calls)
    assert lifecycle == [("easyocr", "upscale2x-otsu"), "closed"]
    assert (root / result["summary"]).is_file()
