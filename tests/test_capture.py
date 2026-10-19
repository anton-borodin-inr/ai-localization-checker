import struct
import subprocess
import zlib
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import Mock

import pytest

from l10n_checker import capture as cap


def png(width=2, height=1):
    def chunk(kind, data):
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data))
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress((b"\x00" + b"\xff\x00\x00" * width) * height))
        + chunk(b"IEND", b"")
    )


def test_filename():
    assert (
        cap.filename("main-menu", "en", "2400x1080", "original", "1271")
        == "main-menu__en__2400x1080__original__1271.png"
    )


@pytest.mark.parametrize(
    "field", ["", " ", "a__b", "../x", "/x", "x/y", "x\\y", "a\nb", "-x"]
)
@pytest.mark.parametrize("index", range(5))
def test_invalid_filename_field(field, index):
    fields = ["menu", "en", "2400x1080", "original", "1271"]
    fields[index] = field
    with pytest.raises(cap.CaptureError):
        cap.filename(*fields)


@pytest.mark.parametrize(
    "payload", [b"", b"not png", png()[:-1], png()[:40], png() + b"junk"]
)
def test_invalid_png(payload):
    with pytest.raises(cap.CaptureError):
        cap.png_size(payload)


def test_png_dimensions():
    assert cap.png_size(png(3, 2)) == (3, 2)


FOREGROUND = f"topResumedActivity=ActivityRecord{{1 u0 {cap.ACTIVITY} t8}}"
OTHER_APP = "topResumedActivity=ActivityRecord{1 u0 com.example/.Other t9}"


@pytest.fixture
def setup_capture(tmp_path, monkeypatch):
    monkeypatch.setattr(cap, "REPO_ROOT", tmp_path)
    device = Mock(spec=cap.Device)
    device.size.return_value = (2, 1)
    device.build.return_value = "1271"
    device.screenshot.return_value = png()
    device.foreground.return_value = FOREGROUND
    # The language step has its own tests (test_capture_language.py).
    language_step = Mock(side_effect=lambda *args: contextmanager(lambda: (yield))())
    monkeypatch.setattr(cap, "unciv_language", language_step)
    monkeypatch.setattr(cap.time, "sleep", lambda s: None)
    return device, tmp_path / "data" / "capture"


def run_capture(setup_capture, **kwargs):
    device, folder = setup_capture
    return cap.capture(device, folder, "menu", "en", "original", **kwargs)


def test_capture_and_explicit_overwrite(setup_capture):
    path = run_capture(setup_capture)
    assert path.name == "menu__en__2x1__original__1271.png"
    assert path.read_bytes() == png()
    with pytest.raises(cap.CaptureError, match="already exists"):
        run_capture(setup_capture)
    assert run_capture(setup_capture, overwrite=True) == path


@pytest.mark.parametrize(
    "failure",
    [
        "size",
        "orientation",
        "cutout-before",
        "cutout-after",
        "foreground",
        "foreground-after",
        "png",
        "empty-png",
        "truncated-png",
        "screencap-error",
    ],
)
def test_failed_capture_saves_nothing(setup_capture, failure):
    device, folder = setup_capture
    if failure == "size":
        device.screenshot.return_value = png(1, 2)
    elif failure == "orientation":
        device.size.side_effect = [(2, 1), (1, 2)]
    elif failure == "cutout-before":
        device.check_cutout.side_effect = cap.CaptureError("cutout")
    elif failure == "cutout-after":
        device.check_cutout.side_effect = [None, None, cap.CaptureError("cutout")]
    elif failure == "foreground":
        device.foreground.return_value = OTHER_APP
    elif failure == "foreground-after":
        device.foreground.side_effect = [FOREGROUND, OTHER_APP]
    elif failure == "png":
        device.screenshot.return_value = b"invalid"
    elif failure == "empty-png":
        device.screenshot.return_value = b""
    elif failure == "truncated-png":
        device.screenshot.return_value = png()[:-5]
    else:
        device.screenshot.side_effect = cap.CaptureError("screencap failed")
    with pytest.raises(cap.CaptureError):
        run_capture(setup_capture)
    assert not folder.exists()


def test_output_outside_data_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(cap, "REPO_ROOT", tmp_path)
    with pytest.raises(cap.CaptureError, match="inside"):
        cap.output_directory(tmp_path / "other")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "link").symlink_to(
        tmp_path / "other", target_is_directory=True
    )
    with pytest.raises(cap.CaptureError, match="inside"):
        cap.output_directory(tmp_path / "data" / "link")


def test_output_symlink_rejected(setup_capture, tmp_path):
    _, folder = setup_capture
    folder.mkdir(parents=True)
    target = folder / "menu__en__2x1__original__1271.png"
    target.symlink_to(tmp_path / "outside.png")
    with pytest.raises(cap.CaptureError, match="symbolic link"):
        run_capture(setup_capture, overwrite=True)
    assert not (tmp_path / "outside.png").exists()


@pytest.mark.parametrize(
    "listing",
    ["List of devices attached\n", "emulator-5554\toffline\n", "phone\tdevice\n"],
)
def test_no_emulator(listing, monkeypatch):
    device = cap.Device(Path("sdk/platform-tools/adb"))
    monkeypatch.setattr(device, "run", lambda *args: listing.encode())
    with pytest.raises(cap.CaptureError, match="No running emulator"):
        device.connect()


def test_sdk_adb_timeout(monkeypatch):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("adb", 30)

    monkeypatch.setattr(subprocess, "run", timeout)
    with pytest.raises(cap.CaptureError, match="timed out"):
        cap.Device(Path("sdk/platform-tools/adb")).connect()


def test_installed_version_and_rotated_size(monkeypatch):
    device = cap.Device(Path("adb"))
    replies = iter(
        [
            "versionCode=1271 minSdk=21 versionName=4.22.10",
            'mOverrideDisplayInfo=DisplayInfo{"Built-in Screen", real 2400 x 1080, rotation 1}',
        ]
    )
    monkeypatch.setattr(device, "shell", lambda *args: next(replies))
    assert device.build() == "1271"
    assert device.size() == (2400, 1080)


@pytest.mark.parametrize(
    "error",
    [
        subprocess.CalledProcessError(1, "adb", stderr=b"error: closed"),
        subprocess.TimeoutExpired("adb", 30),
    ],
)
def test_screencap_failure_is_clear(monkeypatch, error):
    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(subprocess, "run", fail)
    with pytest.raises(cap.CaptureError, match="screencap failed") as raised:
        cap.Device(Path("adb"), "emulator-5554").screenshot()
    assert isinstance(raised.value.__cause__, cap.CaptureError)


def test_screenshot_reads_screen_only(monkeypatch):
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout=png())

    monkeypatch.setattr(subprocess, "run", run)
    assert cap.Device(Path("adb"), "emulator-5554").screenshot() == png()
    assert calls == [["adb", "-s", "emulator-5554", "exec-out", "screencap", "-p"]]
