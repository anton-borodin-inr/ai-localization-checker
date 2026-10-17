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


def check_argv(monkeypatch, *extra):
    monkeypatch.setattr(sys, "argv", ["l10n-check", "--image", "x.png", *extra])


def test_check_without_key_sends_nothing(monkeypatch, capsys):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    check_argv(monkeypatch)

    def no_provider(*args):
        raise AssertionError("no provider may be created without a key")

    monkeypatch.setattr(cli, "make_provider", no_provider)
    assert cli.check_main() == 1
    output = capsys.readouterr()
    assert "GEMINI_API_KEY is not set" in output.err
    assert "Traceback" not in output.err


def test_check_runs_dir_must_be_inside_data(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-DO-NOT-LEAK")
    check_argv(monkeypatch, "--runs-dir", str(tmp_path))
    monkeypatch.setattr(cli, "make_provider", lambda key, model, timeout: object())
    assert cli.check_main() == 1
    output = capsys.readouterr()
    assert "data/" in output.err
    assert "test-key-DO-NOT-LEAK" not in output.err


def test_check_reports_not_checked(monkeypatch, capsys, screenshot, tmp_path):
    from l10n_checker.vision import ProviderError

    class Failing:
        name, model, sdk_version, settings = "fake", "fake-model", "0", {}

        def generate(self, *args):
            raise ProviderError("timeout", "read timed out")

    monkeypatch.setenv("GEMINI_API_KEY", "k")
    check_argv(monkeypatch, "--runs-dir", str(tmp_path / "runs"))
    monkeypatch.setattr(sys, "argv", [*sys.argv[:2], str(screenshot), *sys.argv[3:]])
    monkeypatch.setattr(cli, "make_provider", lambda key, model, timeout: Failing())
    monkeypatch.setattr(cli, "output_directory", lambda path: path)
    assert cli.check_main() == 2
    out = capsys.readouterr().out.splitlines()
    assert out[0].startswith(str(tmp_path / "runs"))
    assert out[1] == "not_checked: timeout: read timed out"
