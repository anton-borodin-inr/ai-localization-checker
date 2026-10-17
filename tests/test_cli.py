import sys

import pytest

from l10n_checker import cli
from l10n_checker.capture import CaptureError


@pytest.mark.parametrize(
    "error",
    [
        CaptureError("No running emulator"),
        CaptureError("Appium unavailable"),
        OSError("Permission denied"),
    ],
)
def test_cli_failure_without_traceback(monkeypatch, capsys, error):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "l10n-capture",
            "--screen",
            "menu",
            "--lang",
            "en",
            "--variant",
            "original",
            "--output-dir",
            "data/capture",
        ],
    )

    def fail(*args):
        raise error

    monkeypatch.setattr(cli, "capture", fail)
    assert cli.main() == 1
    output = capsys.readouterr()
    assert str(error) in output.err
    assert "Traceback" not in output.err
    assert not output.out
