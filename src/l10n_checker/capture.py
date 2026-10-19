"""Capture the Unciv screen shown after launch, in a requested language."""

import json
import re
import struct
import subprocess
import time
import zlib
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

PACKAGE = "com.unciv.app"
OVERLAY = "com.android.internal.emulation.pixel_7"
REPO_ROOT = Path(__file__).resolve().parents[2]
ACTIVITY = f"{PACKAGE}/.AndroidLauncher"
SETTINGS_PATH = f"/data/user/0/{PACKAGE}/files/GameSettings.json"
DEFAULT_SETTLE_S = 8.0
# Filename language code -> Unciv's `language` value in GameSettings.json (D-021).
LANGUAGES = {"en": "English", "de": "German"}


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

    def run(
        self, *args: str, input: bytes | None = None, allow_fail: bool = False
    ) -> bytes:
        command = [str(self.adb)]
        if self.serial:
            command += ["-s", self.serial]
        try:
            return subprocess.run(
                command + list(args),
                check=not allow_fail,
                capture_output=True,
                input=input,
                timeout=30,
            ).stdout
        except FileNotFoundError as exc:
            raise CaptureError("SDK adb was not found; check ANDROID_HOME.") from exc
        except (subprocess.SubprocessError, OSError) as exc:
            raise CaptureError(
                "SDK adb failed or timed out; check the emulator and adb connection."
            ) from exc

    def shell(self, *args: str, allow_fail: bool = False) -> str:
        return (
            self.run("shell", *args, allow_fail=allow_fail)
            .decode("utf-8", errors="replace")
            .replace("\r", "")
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

    def root(self):
        self.run("root")
        self.run("wait-for-device")
        if self.shell("whoami").strip() != "root":
            raise CaptureError("adb root failed; adbd is not running as root.")

    def unroot(self):
        self.run("unroot")
        self.run("wait-for-device")
        if self.shell("whoami").strip() != "shell":
            raise CaptureError("adb unroot failed; adbd is still root. Run: adb unroot")

    def force_stop(self):
        self.shell("am", "force-stop", PACKAGE)

    def pid(self) -> str:
        """Unciv's process id, or an empty string when it is not running."""
        return self.shell("pidof", PACKAGE, allow_fail=True).strip()

    def start_app(self) -> str:
        return self.shell("am", "start", "-W", "-n", ACTIVITY)

    def foreground(self) -> str:
        activities = self.shell("dumpsys", "activity", "activities")
        return next(
            (s.strip() for s in activities.splitlines() if "topResumedActivity" in s),
            "",
        )

    def screenshot(self) -> bytes:
        try:
            return self.run("exec-out", "screencap", "-p")
        except CaptureError as exc:
            raise CaptureError("screencap failed or timed out; no PNG saved.") from exc

    def stat(self, path: str) -> str | None:
        """`uid gid mode size` of a file, or None when it does not exist."""
        # adb joins shell arguments with spaces, so the format must be quoted.
        result = self.shell(f"stat -c '%u %g %a %s' {path}", allow_fail=True)
        result = result.strip()
        return result if re.fullmatch(r"\d+ \d+ \d+ \d+", result) else None

    def read_file(self, path: str) -> bytes:
        return self.run("exec-out", "cat", path)

    def write_file(self, path: str, data: bytes):
        # exec-in passes stdin unchanged; overwriting keeps the owner and mode.
        self.run("exec-in", f"cat > {path}", input=data)


def settings_with_language(original: bytes, language: str) -> bytes:
    """Original settings with only the top-level `language` key set."""
    try:
        settings = json.loads(original)
    except (UnicodeDecodeError, ValueError) as exc:
        raise CaptureError(
            "GameSettings.json is not valid JSON; it was not modified."
        ) from exc
    if not isinstance(settings, dict):
        raise CaptureError(
            "GameSettings.json is not a JSON object; it was not modified."
        )
    changed = dict(settings, language=language)
    return json.dumps(changed, ensure_ascii=False, separators=(",", ":")).encode()


def settings_language(data: bytes) -> object:
    try:
        settings = json.loads(data)
    except (UnicodeDecodeError, ValueError):
        return None
    return settings.get("language") if isinstance(settings, dict) else None


def owner_and_mode(stat: str | None) -> list[str] | None:
    return stat.split()[:3] if stat else None


@contextmanager
def unciv_language(device: Device, lang: str, backup_dir: Path):
    """Run Unciv in `lang`, then restore GameSettings.json byte for byte.

    adbd runs as root only inside this block and is always unrooted on exit.
    The language is confirmed by reading the file back from the device, and
    again after the app has run. The app is left stopped.
    """
    language = LANGUAGES[lang]
    try:
        # Inside the try: a half-done `adb root` must still be undone.
        device.root()
        device.force_stop()
        original_stat = device.stat(SETTINGS_PATH)
        if original_stat is None:
            raise CaptureError(
                f"{SETTINGS_PATH} does not exist; launch Unciv once and pick a language first."
            )
        original = device.read_file(SETTINGS_PATH)
        if len(original) != int(original_stat.split()[3]):
            raise CaptureError("Could not read GameSettings.json completely.")
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup = backup_dir / "GameSettings.json"
        backup.write_bytes(original)
        backup.chmod(0o600)
        try:
            payload = settings_with_language(original, language)
            try:
                device.write_file(SETTINGS_PATH, payload)
            except CaptureError as exc:
                raise CaptureError(
                    f"Language {language} not applied: writing GameSettings.json failed."
                ) from exc
            readback = device.read_file(SETTINGS_PATH)
            if (
                readback != payload
                or settings_language(readback) != language
                or owner_and_mode(device.stat(SETTINGS_PATH))
                != owner_and_mode(original_stat)
            ):
                raise CaptureError(
                    f"Language {language} not applied: GameSettings.json on the device "
                    "does not match what was written."
                )
            if device.pid():
                raise CaptureError("Unciv is still running after force-stop.")
            started = device.start_app()
            if (
                "Status: ok" not in started
                or not device.pid()
                or PACKAGE not in device.foreground()
            ):
                raise CaptureError(
                    "Unciv did not restart in the foreground after the language change."
                )
            yield
            device.force_stop()
            if settings_language(device.read_file(SETTINGS_PATH)) != language:
                raise CaptureError(
                    f"Unciv did not keep language {language} while running; "
                    "the screenshot may show another language."
                )
        finally:
            restore_settings(device, original, original_stat, backup)
    finally:
        device.unroot()


def restore_settings(device: Device, original: bytes, original_stat: str, backup: Path):
    try:
        device.force_stop()
        device.write_file(SETTINGS_PATH, original)
        restored = device.read_file(SETTINGS_PATH) == original
        restored = restored and device.stat(SETTINGS_PATH) == original_stat
    except CaptureError:
        restored = False
    if not restored:
        raise CaptureError(
            f"Could not restore GameSettings.json. The original is kept at {backup}; "
            "see docs/capture.md, 'Manual restore'."
        )
    backup.unlink()
    backup.parent.rmdir()


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


def unciv_in_foreground(device: Device):
    if PACKAGE not in device.foreground():
        raise CaptureError("Unciv is not in the foreground; no PNG saved.")


def protected_target(target: Path, overwrite: bool):
    if target.is_symlink():
        raise CaptureError("Refusing to write a screenshot through a symbolic link.")
    if target.exists() and not overwrite:
        raise CaptureError(
            f"Screenshot already exists: {target}. Use --overwrite to replace it."
        )


def capture(
    device: Device,
    folder: Path,
    screen: str,
    lang: str,
    variant: str,
    overwrite: bool = False,
    settle_s: float = DEFAULT_SETTLE_S,
) -> Path:
    if lang not in LANGUAGES:
        raise CaptureError(
            f"Unsupported language {lang!r}; use one of: {', '.join(LANGUAGES)}."
        )
    filename(screen, lang, "pending", variant, "pending")
    folder = output_directory(folder)
    device.connect()
    device.check_cutout()
    build = device.build()
    # The resolution is known only after launch (Unciv runs in landscape), so
    # any resolution is checked here, before the device is changed.
    filename(screen, lang, "pending", variant, build)
    for existing in folder.glob(f"{screen}__{lang}__*__{variant}__{build}.png"):
        protected_target(existing, overwrite)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    backup_dir = REPO_ROOT / "data" / "capture-backups" / f"{stamp}-{lang}"
    with unciv_language(device, lang, backup_dir):
        # LibGDX draws on one canvas with no UI tree to wait on.
        time.sleep(settle_s)
        size = device.size()
        target = folder / filename(screen, lang, f"{size[0]}x{size[1]}", variant, build)
        protected_target(target, overwrite)
        unciv_in_foreground(device)
        device.check_cutout()
        png = device.screenshot()
        device.check_cutout()
        unciv_in_foreground(device)
        if png_size(png) != size or device.size() != size:
            raise CaptureError(
                "Screenshot size does not match the device screen, or orientation changed; no PNG saved."
            )
    folder.mkdir(parents=True, exist_ok=True)
    with target.open("wb" if overwrite else "xb") as stream:
        stream.write(png)
    return target
