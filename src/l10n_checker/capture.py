"""Capture the current Unciv screen without launching or navigating the app."""

import re
import struct
import subprocess
import warnings
import zlib
from contextlib import contextmanager
from pathlib import Path

from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.client_config import AppiumClientConfig
from selenium.common.exceptions import WebDriverException
from urllib3.exceptions import HTTPError

PACKAGE = "com.unciv.app"
OVERLAY = "com.android.internal.emulation.pixel_7"
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SERVER = "http://127.0.0.1:4723"


class CaptureError(Exception):
    """An actionable capture failure that is safe to show on the CLI."""


def filename(screen: str, lang: str, resolution: str, variant: str, build: str) -> str:
    fields = (screen, lang, resolution, variant, build)
    for field in fields:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", field) or "__" in field:
            raise CaptureError(
                "Filename fields must start with a letter or digit and contain only "
                "ASCII letters, digits, '.', '-', or '_'; empty fields and '__' are invalid."
            )
    return "__".join(fields) + ".png"


def output_directory(path: Path) -> Path:
    path = path.resolve()
    if not path.is_relative_to((REPO_ROOT / "data").resolve()):
        raise CaptureError("The output folder must be inside this repository's data/.")
    return path


def cutout_disabled(display: str, overlays: str) -> bool:
    line = next(
        (s for s in display.splitlines() if 'DisplayDeviceInfo{"Built-in Screen"' in s),
        None,
    )
    if line is not None and "cutout" in line:
        insets = re.search(
            r"cutout DisplayCutout\{insets=Rect\((\d+), (\d+) - (\d+), (\d+)\)", line
        )
        return insets is not None and all(int(n) == 0 for n in insets.groups())
    states = re.findall(
        r"^\[([ x])\] " + re.escape(OVERLAY) + r"\s*$", overlays, re.MULTILINE
    )
    return states == [" "]


class Device:
    def __init__(self, adb: Path, serial: str | None = None):
        self.adb = adb
        self.serial = serial

    def run(self, *args: str) -> bytes:
        command = [str(self.adb)]
        if self.serial:
            command += ["-s", self.serial]
        try:
            return subprocess.run(
                command + list(args), check=True, capture_output=True, timeout=30
            ).stdout
        except FileNotFoundError as exc:
            raise CaptureError("SDK adb was not found; check ANDROID_HOME.") from exc
        except (subprocess.SubprocessError, OSError) as exc:
            raise CaptureError(
                "SDK adb failed or timed out; check the emulator and adb connection."
            ) from exc

    def shell(self, *args: str) -> str:
        return (
            self.run("shell", *args).decode("utf-8", errors="replace").replace("\r", "")
        )

    def connect(self):
        devices = [
            line.split()[0]
            for line in self.run("devices").decode().splitlines()
            if re.fullmatch(r"emulator-\d+\s+device", line.strip())
        ]
        if self.serial is not None:
            if self.serial not in devices:
                raise CaptureError(
                    f"Emulator {self.serial} is not running or is not ready."
                )
        elif len(devices) == 1:
            self.serial = devices[0]
        elif not devices:
            raise CaptureError(
                "No running emulator found. Start the project AVD and run scripts/prepare_emulator.sh."
            )
        else:
            raise CaptureError(
                "Multiple emulators are running; select one with --serial."
            )
        if self.shell("getprop", "sys.boot_completed").strip() != "1":
            raise CaptureError("The emulator has not finished booting.")

    def check_cutout(self):
        display = self.shell("dumpsys", "display")
        overlays = ""
        line = next(
            (
                s
                for s in display.splitlines()
                if 'DisplayDeviceInfo{"Built-in Screen"' in s
            ),
            None,
        )
        if line is None or "cutout" not in line:
            overlays = self.shell("cmd", "overlay", "list", "android")
        if not cutout_disabled(display, overlays):
            raise CaptureError(
                "Display cutout is active or unknown; run scripts/prepare_emulator.sh before capture."
            )

    def size(self) -> tuple[int, int]:
        display = self.shell("dumpsys", "display")
        match = re.search(
            r'mOverrideDisplayInfo=DisplayInfo\{"Built-in Screen"[^\n]*?real (\d+) x (\d+)',
            display,
        )
        if not match:
            raise CaptureError(
                "Cannot determine the current device screen size from dumpsys display."
            )
        return tuple(int(n) for n in match.groups())

    def build(self) -> str:
        package = self.shell("dumpsys", "package", PACKAGE)
        match = re.search(r"\bversionCode=(\d+)\b", package)
        if not match:
            raise CaptureError(
                "Cannot read Unciv versionCode; check that com.unciv.app is installed."
            )
        return match[1]


@contextmanager
def appium_session(device: Device, server: str = DEFAULT_SERVER):
    driver = None
    try:
        options = UiAutomator2Options().load_capabilities(
            {
                "platformName": "Android",
                "appium:automationName": "UiAutomator2",
                "appium:udid": device.serial,
                "appium:noReset": True,
                "appium:autoLaunch": False,
                "appium:skipUnlock": True,
                "appium:newCommandTimeout": 120,
            }
        )
        driver = webdriver.Remote(
            options=options, client_config=AppiumClientConfig(server, timeout=60)
        )
        yield driver
    except (WebDriverException, HTTPError, OSError) as exc:
        raise CaptureError(
            f"Appium connection or capture failed at {server}; start the project server with npm run appium and check its log."
        ) from exc
    finally:
        if driver is not None:
            try:
                driver.quit()
            except (WebDriverException, HTTPError, OSError):
                warnings.warn(
                    "Could not close the Appium session; check the server log.",
                    stacklevel=2,
                )


def png_size(png: bytes) -> tuple[int, int]:
    if not png.startswith(b"\x89PNG\r\n\x1a\n"):
        raise CaptureError("The screenshot is not a PNG.")
    offset = 8
    size = None
    has_data = False
    while offset + 12 <= len(png):
        length = struct.unpack_from(">I", png, offset)[0]
        end = offset + 12 + length
        if end > len(png):
            break
        kind = png[offset + 4 : offset + 8]
        data = png[offset + 8 : end - 4]
        crc = struct.unpack_from(">I", png, end - 4)[0]
        if zlib.crc32(kind + data) != crc:
            break
        if offset == 8:
            if kind != b"IHDR" or length != 13:
                break
            size = struct.unpack_from(">II", data)
        if kind == b"IDAT":
            has_data = True
        if kind == b"IEND":
            if length == 0 and end == len(png) and size and all(size) and has_data:
                return size
            break
        offset = end
    raise CaptureError("The screenshot PNG is incomplete or invalid.")


def capture(
    device: Device,
    folder: Path,
    screen: str,
    lang: str,
    variant: str,
    server: str = DEFAULT_SERVER,
    overwrite: bool = False,
) -> Path:
    filename(screen, lang, "pending", variant, "pending")
    folder = output_directory(folder)
    device.connect()
    device.check_cutout()
    size = device.size()
    target = folder / filename(
        screen, lang, f"{size[0]}x{size[1]}", variant, device.build()
    )
    if target.is_symlink():
        raise CaptureError("Refusing to write a screenshot through a symbolic link.")
    if target.exists() and not overwrite:
        raise CaptureError(
            f"Screenshot already exists: {target}. Use --overwrite to replace it."
        )
    with appium_session(device, server) as driver:
        if driver.current_package != PACKAGE:
            raise CaptureError(
                "Unciv is not in the foreground; open the intended screen before capture."
            )
        device.check_cutout()
        png = driver.get_screenshot_as_png()
        device.check_cutout()
        if png_size(png) != size or device.size() != size:
            raise CaptureError(
                "Screenshot size does not match the device screen, or orientation changed; no PNG saved."
            )
    folder.mkdir(parents=True, exist_ok=True)
    with target.open("wb" if overwrite else "xb") as stream:
        stream.write(png)
    return target
