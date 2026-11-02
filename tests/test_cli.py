import sys
from pathlib import Path

import pytest

from l10n_checker import cli
from l10n_checker.capture import CaptureError


@pytest.mark.parametrize(
    "error",
    [
        CaptureError("No running emulator"),
        CaptureError("screencap failed"),
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

    def fail(*args, **kwargs):
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
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    check_argv(monkeypatch)

    def no_provider(*args):
        raise AssertionError("no provider may be created without a key")

    monkeypatch.setattr(cli, "make_provider", no_provider)
    assert cli.check_main() == 1
    output = capsys.readouterr()
    assert "DEEPSEEK_API_KEY is not set" in output.err
    assert "Traceback" not in output.err


def test_check_runs_dir_must_be_inside_data(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key-DO-NOT-LEAK")
    check_argv(monkeypatch, "--runs-dir", str(tmp_path))
    monkeypatch.setattr(cli, "make_provider", lambda key, timeout: object())
    assert cli.check_main() == 1
    output = capsys.readouterr()
    assert "data/" in output.err
    assert "test-key-DO-NOT-LEAK" not in output.err


def test_check_reports_not_checked(monkeypatch, capsys, screenshot, tmp_path):
    from l10n_checker.vision import ProviderError

    class Failing:
        name, model, sdk_version, settings = "fake", "fake-model", "0", {}
        wrapper_version = None

        def wrap_prompt(self, prompt):
            return prompt

        def estimate_cost(self, usage):
            return None

        def generate(self, *args):
            raise ProviderError("timeout", "read timed out")

    monkeypatch.setenv("DEEPSEEK_API_KEY", "k")
    check_argv(monkeypatch, "--runs-dir", str(tmp_path / "runs"))
    monkeypatch.setattr(sys, "argv", [*sys.argv[:2], str(screenshot), *sys.argv[3:]])
    monkeypatch.setattr(cli, "make_provider", lambda key, timeout: Failing())
    monkeypatch.setattr(cli, "output_directory", lambda path: path)
    assert cli.check_main() == 2
    out = capsys.readouterr().out.splitlines()
    assert out[0].startswith(str(tmp_path / "runs"))
    assert out[1] == "not_checked: timeout: read timed out"


def test_check_rejects_file_name_without_language(
    monkeypatch, capsys, screenshot, tmp_path
):
    class NoRequests:
        def wrap_prompt(self, prompt):
            raise AssertionError("no prompt may be prepared")

        def generate(self, *args):
            raise AssertionError("no request may be sent")

    image = tmp_path / "x.png"
    image.write_bytes(screenshot.read_bytes())
    runs = tmp_path / "runs"
    monkeypatch.setenv("DEEPSEEK_API_KEY", "k")
    monkeypatch.setattr(
        sys, "argv", ["l10n-check", "--image", str(image), "--runs-dir", str(runs)]
    )
    monkeypatch.setattr(cli, "make_provider", lambda key, timeout: NoRequests())
    monkeypatch.setattr(cli, "output_directory", lambda path: path)
    assert cli.check_main() == 1
    output = capsys.readouterr()
    assert "D-003" in output.err
    assert "Traceback" not in output.err
    assert not output.out
    assert not runs.exists()


def test_check_has_no_language_option(monkeypatch, capsys):
    check_argv(monkeypatch, "--lang", "de")
    with pytest.raises(SystemExit) as exit_info:
        cli.check_main()
    assert exit_info.value.code == 2
    assert "--lang" in capsys.readouterr().err


def test_make_provider_uses_deepseek():
    provider = cli.make_provider("k", 120)
    assert provider.name == "deepseek"
    assert provider.settings["timeout_s"] == 120


def capture_argv(monkeypatch, *langs):
    argv = ["l10n-capture", "--screen", "main-menu", "--variant", "original"]
    for lang in langs:
        argv += ["--lang", lang]
    monkeypatch.setattr(sys, "argv", [*argv, "--output-dir", "data/capture"])


def test_cli_captures_each_language_in_order(monkeypatch, capsys):
    capture_argv(monkeypatch, "en", "de")
    calls = []

    def fake(device, folder, screen, lang, *args, **kwargs):
        calls.append(lang)
        return f"data/capture/{screen}__{lang}.png"

    monkeypatch.setattr(cli, "capture", fake)
    assert cli.main() == 0
    assert calls == ["en", "de"]
    assert capsys.readouterr().out.split() == [
        "data/capture/main-menu__en.png",
        "data/capture/main-menu__de.png",
    ]


def test_cli_stops_after_first_failure(monkeypatch, capsys):
    capture_argv(monkeypatch, "en", "de")
    calls = []

    def fake(device, folder, screen, lang, *args, **kwargs):
        calls.append(lang)
        raise CaptureError("Unciv did not restart")

    monkeypatch.setattr(cli, "capture", fake)
    assert cli.main() == 1
    assert calls == ["en"]
    assert "Capture failed (en): Unciv did not restart" in capsys.readouterr().err


def test_cli_rejects_unsupported_language(monkeypatch):
    capture_argv(monkeypatch, "fr")
    monkeypatch.setattr(cli, "capture", lambda *args: pytest.fail("no capture"))
    with pytest.raises(SystemExit):
        cli.main()


@pytest.mark.parametrize("prepare", [False, True])
def test_manifest_requires_selector_before_device_access(
    monkeypatch, capsys, tmp_path, prepare
):
    from l10n_checker import capture

    monkeypatch.setattr(capture, "REPO_ROOT", tmp_path)
    manifest = Path(__file__).resolve().parents[1] / "fixtures/stage2/screens.json"
    folder = tmp_path / "data/run"
    argv = ["l10n-capture", "--manifest", str(manifest), "--output-dir", str(folder)]
    if prepare:
        argv.append("--prepare-only")
    monkeypatch.setattr(sys, "argv", argv)
    monkeypatch.setattr(
        cli.Device,
        "connect",
        lambda *_: pytest.fail("device access without a selector"),
    )
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 2
    assert "--split or --screen-id" in capsys.readouterr().err
    assert not folder.exists()
