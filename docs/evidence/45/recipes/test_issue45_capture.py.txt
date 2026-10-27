"""Exercise the issue-45 write gates and restoration after a failed hook request."""

import importlib
import io
import json
import tarfile
from pathlib import Path

import pytest


def archive():
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as stream:
        member = tarfile.TarInfo("./SaveFiles/fixture")
        data = b"original save bytes"
        member.size = len(data)
        stream.addfile(member, io.BytesIO(data))
    return buffer.getvalue()


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    module = importlib.import_module("issue45_capture")
    evidence = tmp_path / "evidence"
    backup = tmp_path / "backup"
    (backup / "private").mkdir(parents=True)
    (evidence / "inputs/settings").mkdir(parents=True)
    (evidence / "inputs/states").mkdir(parents=True)
    original = b'{"language":"English", "keep":"original formatting"}\n'
    template = b'{"language":"German"}\n'
    (backup / "private/GameSettings.json").write_bytes(original)
    (evidence / "inputs/settings/de.json").write_bytes(template)
    (evidence / "inputs/states/tech-picker.json").write_text("{}")
    saved = archive()
    (backup / "private/backup-manifest.json").write_text(
        json.dumps({"archives": {"external": {"files": module.inventory(saved)}}})
    )
    monkeypatch.setattr(module, "EVIDENCE", evidence)
    monkeypatch.setattr(module, "BACKUP", backup)
    plan = {
        "variant": "clean",
        "screens": ["tech-picker"],
        "languages": ["de"],
        "version_code": "1271045",
        "apk_sha256": "a" * 64,
        "original_settings_sha256": module.digest(original),
        "original_settings_stat": f"123:123:600:{len(original)}",
        "inputs": {},
    }

    class Device:
        current = original

        def __init__(self):
            self.writes = []

        def connect(self):
            pass

        def check_cutout(self):
            pass

        def build(self):
            return "1271045"

        def force_stop(self):
            pass

        def shell(self, *args):
            if args[:2] == ("pm", "path"):
                return "package:/data/app/test/base.apk\n"
            if args[0] == "sha256sum":
                return "a" * 64 + " base.apk\n"
            if args == ("wm", "density"):
                return "Physical density: 420\n"
            if "stat" in args:
                return f"123:123:600:{len(self.current)}\n"
            raise AssertionError(args)

        def run(self, *args, input=None):
            if "tee" in args:
                self.writes.append(input)
                self.current = input
                return input
            if "cat" in args:
                return self.current
            if "tar" in args:
                return saved
            raise AssertionError(args)

    return module, Device(), plan, tmp_path / "capture", original


def test_changed_settings_aborts_before_any_write(prepared):
    module, device, plan, output, _ = prepared
    device.current = b'{"language":"different"}'
    with pytest.raises(module.CaptureError, match="Settings changed since"):
        module.capture(device, plan, output)
    assert device.writes == []
    assert not output.exists()


def test_failed_hook_restores_exact_original_bytes_and_keeps_failure(
    prepared, monkeypatch
):
    module, device, plan, output, original = prepared

    def fail(*args):
        raise module.CaptureError("deliberate hook failure")

    monkeypatch.setattr(module, "request_screen", fail)
    with pytest.raises(module.CaptureError, match="deliberate hook failure"):
        module.capture(device, plan, output)
    assert len(device.writes) == 2
    assert device.current == original
    audit = json.loads((output / "capture-audit.json").read_text())
    assert audit["status"] == "failed"
    assert audit["settings_restored_byte_identical"] is True
    assert audit["all_saves_unchanged"] is True
    assert not list(output.glob("*.png"))
