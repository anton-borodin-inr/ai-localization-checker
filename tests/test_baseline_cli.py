import sys
from pathlib import Path

import pytest

from l10n_checker import baseline_cli
from l10n_checker.capture import CaptureError
from l10n_checker.vision import CheckResult


def argv(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "l10n-baseline",
            "--image",
            "image.png",
            "--manifest",
            "manifest.json",
            "--inventory",
            "inventory.json",
            "--unciv-fork",
            "fork",
        ],
    )


def test_cli_passes_only_offline_inputs(monkeypatch, capsys):
    argv(monkeypatch)
    monkeypatch.setattr(baseline_cli, "output_directory", lambda p: p)

    def run(*args):
        assert args[:4] == tuple(
            map(Path, ("image.png", "manifest.json", "inventory.json", "fork"))
        )
        return CheckResult(
            status="checked", findings=[], reason=None, metadata={}
        ), Path("data/run")

    monkeypatch.setattr(baseline_cli, "run_baseline", run)
    assert baseline_cli.main() == 0
    assert capsys.readouterr().out.splitlines() == ["data/run", "checked: 0 finding(s)"]


def test_cli_not_checked_is_nonzero(monkeypatch, capsys):
    argv(monkeypatch)
    monkeypatch.setattr(baseline_cli, "output_directory", lambda p: p)
    monkeypatch.setattr(
        baseline_cli,
        "run_baseline",
        lambda *args: (
            CheckResult(
                status="not_checked", findings=[], reason="OCR failed", metadata={}
            ),
            Path("data/run"),
        ),
    )
    assert baseline_cli.main() == 2
    assert "not_checked: OCR failed" in capsys.readouterr().out


def test_cli_cannot_record_a_run(monkeypatch, capsys):
    argv(monkeypatch)

    def fail(path):
        raise CaptureError("runs must be inside data/")

    monkeypatch.setattr(baseline_cli, "output_directory", fail)
    assert baseline_cli.main() == 1
    assert "Cannot record baseline run" in capsys.readouterr().err


def test_output_directory_works_without_an_editable_install(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert baseline_cli.output_directory(Path("data/runs")) == tmp_path / "data/runs"
    with pytest.raises(CaptureError):
        baseline_cli.output_directory(tmp_path / "outside")
    (tmp_path / "data").mkdir()
    (tmp_path / "data/link").symlink_to(tmp_path / "outside", target_is_directory=True)
    with pytest.raises(CaptureError):
        baseline_cli.output_directory(Path("data/link/runs"))
