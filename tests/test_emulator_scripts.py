import os
import subprocess
from pathlib import Path

import pytest

from l10n_checker.capture import OVERLAY, cutout_disabled

ROOT = Path(__file__).resolve().parents[1]
LINE = 'DisplayDeviceInfo{"Built-in Screen": '


@pytest.mark.parametrize(
    "display,overlay,expected",
    [
        (LINE + "1080 x 2400}", "", True),
        (LINE + "cutout DisplayCutout{insets=Rect(0, 0 - 0, 0)}", "", True),
        (
            LINE + "cutout DisplayCutout{insets=Rect(0, 136 - 0, 0)}",
            "[ ] " + OVERLAY,
            False,
        ),
        (LINE + "cutout unknown", "[ ] " + OVERLAY, False),
        ("", "[ ] " + OVERLAY, True),
        ("mPrimaryDisplayDevice=Built-in Screen", "[x] " + OVERLAY, False),
        ("", "", False),
        ("", "--- " + OVERLAY, False),
        ("", "[ ] " + OVERLAY + ".other", False),
    ],
)
def test_python_and_shell_cutout_policy(tmp_path, display, overlay, expected):
    adb = tmp_path / "adb"
    adb.write_text(
        '#!/bin/bash\nif [[ "$*" == *"dumpsys display" ]]; then printf "%s" "$DISPLAY_RESULT"; else printf "%s" "$OVERLAY_RESULT"; fi\n'
    )
    adb.chmod(0o755)
    env = dict(
        os.environ,
        ADB=str(adb),
        serial="emulator-5554",
        DISPLAY_RESULT=display,
        OVERLAY_RESULT=overlay,
    )
    result = subprocess.run(
        [
            "bash",
            "-c",
            'source "$1"; cutout_disabled',
            "bash",
            str(ROOT / "scripts/cutout.sh"),
        ],
        check=False,
        env=env,
        capture_output=True,
    )
    assert (result.returncode == 0) is expected
    assert cutout_disabled(display, overlay) is expected


def test_prepare_refuses_unknown_cutout(tmp_path):
    sdk = tmp_path / "sdk" / "platform-tools"
    sdk.mkdir(parents=True)
    adb = sdk / "adb"
    adb.write_text("""#!/bin/bash
case "$*" in
  devices) printf 'List of devices attached\nemulator-5554\tdevice\n' ;;
  *sys.boot_completed*) echo 1 ;;
esac
""")
    adb.chmod(0o755)
    sleep = tmp_path / "sleep"
    sleep.write_text("#!/bin/bash\nexit 0\n")
    sleep.chmod(0o755)
    env = dict(
        os.environ,
        ANDROID_HOME=str(sdk.parent),
        PATH=str(tmp_path) + ":" + os.environ["PATH"],
    )
    result = subprocess.run(
        ["bash", str(ROOT / "scripts/prepare_emulator.sh")],
        check=False,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 1
    assert "active or unknown" in result.stderr
    assert "ready" not in result.stdout
