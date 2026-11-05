"""Opt-in dev-only v2 capture; consumes a separately approved exact device plan."""

import json
import sys
from pathlib import Path

import pytest

from l10n_checker import capture as capture_module
from l10n_checker import cli
from l10n_checker.screen_capture import _is_within_directory
from l10n_checker.screen_manifest import Inputs, digest


@pytest.mark.device
def test_real_dev_manifest_capture(request, monkeypatch):
    plan_option = request.config.getoption("--capture-device-plan")
    output_option = request.config.getoption("--capture-output-dir")
    if not plan_option or not output_option:
        pytest.fail(
            "Dev capture needs --capture-device-plan and --capture-output-dir; prepare and obtain separate write approval first"
        )
    manifest = capture_module.REPO_ROOT / "fixtures/stage2/screens-v2.json"
    inputs = Inputs(manifest, split="dev")
    plan_path = Path(plan_option)
    folder = Path(output_option)
    assert not _is_within_directory(
        folder.resolve(), capture_module.REPO_ROOT.resolve()
    ), "This device verification requires external output"
    approved_bytes = plan_path.read_bytes()
    approved = json.loads(approved_bytes)
    selection = inputs.capture_selection(["en", "de"])
    assert approved["selection"] == selection
    assert approved["manifest_sha256"] == inputs.sha256
    ids = selection["screen_ids"]
    expected = [
        (n, lang, sid)
        for n, order in ((1, ids), (2, ids[::-1]))
        for lang in ("en", "de")
        for sid in order
    ]
    assert len(ids) == 5
    assert [
        (v["pass"], v["language"], v["screen"])
        for v in approved["planned_hook_output_operations"]
    ] == expected
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "l10n-capture",
            "--manifest",
            str(manifest),
            "--split",
            "dev",
            "--lang",
            "en",
            "--lang",
            "de",
            "--serial",
            approved["serial"],
            "--device-plan",
            str(plan_path),
            "--output-dir",
            str(folder),
        ],
    )
    assert cli.main() == 0
    summary = json.loads((folder / "summary.json").read_bytes())
    assert summary["status"] == "complete"
    assert summary["selection"] == selection
    assert summary["device_plan_sha256"] == digest(approved_bytes)
    assert summary["settings_restored"] and summary["saves_unchanged"]
    assert [
        (r["pass"], r["language"], r["screen"]) for r in summary["records"]
    ] == expected
    assert len(summary["records"]) == 20
    assert len(summary["comparisons"]) == 10
    assert all(
        c["status"] == c["dump_status"] == "identical" for c in summary["comparisons"]
    )
    for record in summary["records"]:
        assert record["status"] == "captured"
        assert digest((folder / record["png"]).read_bytes()) == record["png_sha256"]
        assert digest((folder / record["dump"]).read_bytes()) == record["dump_sha256"]
        assert (folder / record["pair"]).is_file()
