"""Language step of capture, against a fake device. No adb or emulator calls."""

import json
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import Mock

import pytest
from conftest import make_png

from l10n_checker import capture as cap

ORIGINAL = b'{"version":{"number":4},"showTutorials":false,"windowState":{}}'
STAT = "10192 10192 600"


class FakeDevice(cap.Device):
    """Simulates adbd root state, Unciv's process and GameSettings.json."""

    def __init__(self, **faults):
        super().__init__(Path("sdk/platform-tools/adb"), "emulator-5554")
        self.file = ORIGINAL
        self.is_root = False
        self.running = True
        self.log = []
        self.faults = faults

    def fail(self, name):
        if self.faults.get(name):
            raise cap.CaptureError(f"injected {name}")

    def run(self, *args, input=None, allow_fail=False):
        self.log.append(args)
        match args:
            case ("root",):
                self.fail("root")
                self.is_root = True
            case ("unroot",):
                self.fail("unroot")
                self.is_root = False
            case ("wait-for-device",):
                pass
            case ("shell", "whoami"):
                return b"root\n" if self.is_root else b"shell\n"
            case ("shell", "am", "force-stop", cap.PACKAGE):
                if self.faults.get("app_resets_language") and self.running:
                    self.file = ORIGINAL
                self.running = False
            case ("shell", "stat", *_):
                assert self.is_root, "settings accessed without root"
                return f"{STAT} {len(self.file)}\n".encode()
            case ("exec-out", "cat", cap.SETTINGS_PATH):
                assert self.is_root, "settings accessed without root"
                return self.file
            case ("exec-in", command):
                assert self.is_root, "settings written without root"
                assert command == f"cat > {cap.SETTINGS_PATH}"
                restoring = input == ORIGINAL
                if restoring:
                    self.fail("restore")
                else:
                    self.fail("write")
                self.file = (
                    input[:-1]
                    if self.faults.get("short_write") and not restoring
                    else input
                )
            case ("shell", "pidof", cap.PACKAGE):
                return b"4242\n" if self.running else b""
            case ("shell", "am", "start", "-W", "-n", cap.ACTIVITY):
                if self.faults.get("no_start"):
                    return b"Error: Activity not started\n"
                self.running = True
                return b"Status: ok\nActivity: com.unciv.app/.AndroidLauncher\n"
            case ("shell", "dumpsys", "activity", "activities"):
                top = (
                    "com.example/.Other"
                    if self.faults.get("background")
                    else cap.ACTIVITY
                )
                return (
                    f"  topResumedActivity=ActivityRecord{{1 u0 {top} t8}}\n".encode()
                )
            case _:
                raise AssertionError(f"unexpected adb call {args}")
        return b""

    def language(self):
        return json.loads(self.file).get("language")


def run_language_step(device, tmp_path, lang="de", body=None):
    seen = {}
    with cap.unciv_language(device, lang, tmp_path / "backup"):
        seen["language"] = device.language()
        seen["running"] = device.running
        if body:
            body()
    return seen


def assert_restored(device, tmp_path):
    assert device.file == ORIGINAL
    assert device.log[-3:] == [("unroot",), ("wait-for-device",), ("shell", "whoami")]
    assert not device.is_root


@pytest.mark.parametrize("lang,language", [("en", "English"), ("de", "German")])
def test_language_applied_then_restored(tmp_path, lang, language):
    device = FakeDevice()
    seen = run_language_step(device, tmp_path, lang)
    assert seen == {"language": language, "running": True}
    assert_restored(device, tmp_path)
    assert not device.running
    assert not (tmp_path / "backup").exists()


def test_other_settings_are_preserved():
    changed = json.loads(cap.settings_with_language(ORIGINAL, "German"))
    assert changed.pop("language") == "German"
    assert changed == json.loads(ORIGINAL)


@pytest.mark.parametrize(
    "fault,message",
    [
        ("write", "not applied: writing"),
        ("short_write", "not applied: GameSettings.json on the device"),
    ],
)
def test_write_failure(tmp_path, fault, message):
    device = FakeDevice(**{fault: True})
    body = Mock()
    with pytest.raises(cap.CaptureError, match=message):
        run_language_step(device, tmp_path, body=body)
    body.assert_not_called()
    assert ("shell", "am", "start", "-W", "-n", cap.ACTIVITY) not in device.log
    assert_restored(device, tmp_path)


@pytest.mark.parametrize("fault", ["no_start", "background"])
def test_restart_failure(tmp_path, fault):
    device = FakeDevice(**{fault: True})
    body = Mock()
    with pytest.raises(cap.CaptureError, match="did not restart"):
        run_language_step(device, tmp_path, body=body)
    body.assert_not_called()
    assert_restored(device, tmp_path)


def test_language_reset_by_app_is_detected(tmp_path):
    device = FakeDevice(app_resets_language=True)
    with pytest.raises(cap.CaptureError, match="did not keep language German"):
        run_language_step(device, tmp_path)
    assert_restored(device, tmp_path)


def test_failure_inside_capture_restores(tmp_path):
    device = FakeDevice()

    def boom():
        raise cap.CaptureError("screenshot failed")

    with pytest.raises(cap.CaptureError, match="screenshot failed"):
        run_language_step(device, tmp_path, body=boom)
    assert_restored(device, tmp_path)


def test_restore_failure_keeps_backup(tmp_path):
    device = FakeDevice(restore=True)
    with pytest.raises(cap.CaptureError, match="Could not restore") as error:
        run_language_step(device, tmp_path)
    backup = tmp_path / "backup" / "GameSettings.json"
    assert str(backup) in str(error.value)
    assert backup.read_bytes() == ORIGINAL
    assert not device.is_root


def test_root_failure_touches_nothing(tmp_path):
    device = FakeDevice(root=True)
    with pytest.raises(cap.CaptureError, match="injected root"):
        run_language_step(device, tmp_path)
    assert device.file == ORIGINAL
    assert ("unroot",) in device.log


def test_unroot_failure_is_an_error(tmp_path):
    device = FakeDevice(unroot=True)
    with pytest.raises(cap.CaptureError, match="injected unroot"):
        run_language_step(device, tmp_path)
    assert device.file == ORIGINAL


def test_missing_settings_file(tmp_path, monkeypatch):
    device = FakeDevice()
    monkeypatch.setattr(device, "stat", lambda path: None)
    with pytest.raises(cap.CaptureError, match="launch Unciv once"):
        run_language_step(device, tmp_path)
    assert device.file == ORIGINAL
    assert not device.is_root


@pytest.mark.parametrize("data", [b"not json", b"[1, 2]", b"\xff"])
def test_invalid_settings_are_not_modified(data):
    with pytest.raises(cap.CaptureError, match="was not modified"):
        cap.settings_with_language(data, "German")


@pytest.fixture
def full_capture(tmp_path, monkeypatch):
    monkeypatch.setattr(cap, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(cap.time, "sleep", lambda s: None)
    device = FakeDevice()
    for name, value in {
        "connect": None,
        "check_cutout": None,
        "size": (2, 1),
        "build": "1271",
    }.items():
        monkeypatch.setattr(device, name, Mock(return_value=value))
    driver = Mock(current_package=cap.PACKAGE)

    @contextmanager
    def session(*args):
        driver.language = device.language()
        yield driver

    driver.get_screenshot_as_png.return_value = make_png(2, 1)
    monkeypatch.setattr(cap, "appium_session", session)
    return device, driver, tmp_path / "data" / "captures"


def test_capture_names_file_by_requested_language(full_capture):
    device, driver, folder = full_capture
    path = cap.capture(device, folder, "main-menu", "de", "original")
    assert path.name == "main-menu__de__2x1__original__1271.png"
    assert driver.language == "German"
    assert device.file == ORIGINAL
    assert not device.is_root


def test_capture_rejects_unknown_language(full_capture):
    device, _, folder = full_capture
    with pytest.raises(cap.CaptureError, match="Unsupported language"):
        cap.capture(device, folder, "main-menu", "fr", "original")
    assert device.log == []


def test_capture_failure_saves_nothing(full_capture):
    device, _, folder = full_capture
    device.faults["no_start"] = True
    with pytest.raises(cap.CaptureError, match="did not restart"):
        cap.capture(device, folder, "main-menu", "en", "original")
    assert not folder.exists()
    assert device.file == ORIGINAL
    assert not device.is_root
