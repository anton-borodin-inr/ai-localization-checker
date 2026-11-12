"""Device transaction safety; all APK bytes and device responses here are synthetic."""

import importlib
import importlib.util

import pytest

from l10n_checker.capture import CaptureError


@pytest.fixture(autouse=True)
def forbid_unstubbed_native_commands(monkeypatch):
    import subprocess

    def forbidden(*args, **kwargs):
        pytest.fail("Unstubbed native command forbidden in host-only mutation tests")

    monkeypatch.setattr(subprocess, "run", forbidden)


def api():
    assert importlib.util.find_spec("l10n_checker.mutation_device") is not None, (
        "Safe install orchestration missing"
    )
    return importlib.import_module("l10n_checker.mutation_device")


class Device:
    def __init__(self):
        self.calls = []

    def run(self, *args):
        self.calls.append(args)
        assert args[:3] == ("install", "-r", "-d")
        return b"Performing Streamed Install\nSuccess\n"

    def force_stop(self):
        self.calls.append(("stop",))

    def pid(self):
        return ""


BOOKKEEPING = (
    "files/profileInstalled",
    "no_backup/androidx.work.workdb",
    "no_backup/androidx.work.workdb-shm",
    "no_backup/androidx.work.workdb-wal",
)


def test_preflight_refuses_multiple_emulators_before_environment_root_check(
    monkeypatch,
):
    from types import SimpleNamespace

    monkeypatch.setattr(
        api().subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout=b""),
    )
    device = SimpleNamespace(
        serial="emulator-5554",
        connect=lambda: None,
        pid=lambda: "",
        run=lambda *args: (
            b"List of devices attached\nemulator-5554\tdevice\nemulator-5556\tdevice\n"
        ),
    )
    with pytest.raises(CaptureError, match="one emulator"):
        api().assert_idle(device)
