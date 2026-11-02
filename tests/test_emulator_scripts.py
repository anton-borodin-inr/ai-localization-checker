import json
import os
import subprocess
from pathlib import Path

import pytest

from l10n_checker.capture import OVERLAY, CaptureError, Device, cutout_disabled

ROOT = Path(__file__).resolve().parents[1]
LINE = 'DisplayDeviceInfo{"Built-in Screen": '


@pytest.mark.parametrize(
    "display,overlay,expected",
    [
        (LINE + "1080 x 2400}", "", False),
        (LINE + "1080 x 2400}", "[ ] " + OVERLAY, True),
        (LINE + "1080 x 2400}", "[x] " + OVERLAY, False),
        (
            LINE + "1080 x 2400}",
            "[ ] " + OVERLAY + "_pro\n[ ] " + OVERLAY + "a\n[ ] " + OVERLAY,
            True,
        ),
        (LINE + "1080 x 2400}", "--- " + OVERLAY, False),
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


def test_prepare_never_calls_root(tmp_path):
    sdk = tmp_path / "sdk" / "platform-tools"
    sdk.mkdir(parents=True)
    log = tmp_path / "adb.log"
    adb = sdk / "adb"
    adb.write_text(f"""#!/bin/bash
echo "$*" >> {log}
case "$*" in
  devices) printf 'List of devices attached\\nemulator-5554\\tdevice\\n' ;;
  *sys.boot_completed*) echo 1 ;;
  *"dumpsys display"*) echo 'DisplayDeviceInfo{{"Built-in Screen": cutout DisplayCutout{{insets=Rect(0, 0 - 0, 0)}}' ;;
esac
""")
    adb.chmod(0o755)
    result = subprocess.run(
        ["bash", str(ROOT / "scripts/prepare_emulator.sh")],
        check=False,
        env=dict(os.environ, ANDROID_HOME=str(sdk.parent)),
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    calls = log.read_text().splitlines()
    assert "-s emulator-5554 shell cmd overlay disable " + OVERLAY in calls
    assert not [c for c in calls if c.split()[-1] in ("root", "unroot")]


@pytest.mark.parametrize(
    "overlay,expected",
    [("[ ] " + OVERLAY, True), ("[x] " + OVERLAY, False), ("", False)],
)
def test_device_queries_overlay_when_cutout_field_is_absent(
    monkeypatch, overlay, expected
):
    device = Device(Path("sdk/platform-tools/adb"), "emulator-5554")
    calls = []

    def shell(*args):
        calls.append(args)
        if args == ("dumpsys", "display"):
            return LINE + "1080 x 2400}"
        assert args == ("cmd", "overlay", "list", "android")
        return overlay

    monkeypatch.setattr(device, "shell", shell)
    if expected:
        device.check_cutout()
    else:
        with pytest.raises(CaptureError, match="cutout is active or unknown"):
            device.check_cutout()
    assert ("cmd", "overlay", "list", "android") in calls


CHECK_ENV_OTHER_CHECKS = {
    "cmdline-tools/latest",
    "platform-tools",
    "emulator",
    "system-image",
    "avd",
    "emulator-running",
    "adb-root",
    "display-cutout",
}
V2_MANIFEST = "fixtures/stage2/screens-v2.json"


def v2_version_code():
    return json.loads((ROOT / V2_MANIFEST).read_text())["build"]["version_code"]


def run_check_env(tmp_path, installed, *args):
    """Run the real script against a fake SDK, AVD and adb; `installed` may be None."""
    sdk = tmp_path / "sdk"
    for package in (
        "cmdline-tools/latest",
        "platform-tools",
        "emulator",
        "system-images/android-34/google_apis/arm64-v8a",
    ):
        (sdk / package).mkdir(parents=True)
        (sdk / package / "source.properties").write_text("Pkg.Revision=1.0\n")
    avd = tmp_path / "home/.android/avd/unciv_api34.avd"
    avd.mkdir(parents=True)
    (avd / "config.ini").write_text(
        "image.sysdir.1=system-images/android-34/google_apis/arm64-v8a/\n"
        "PlayStore.enabled=false\n"
        "hw.lcd.width=1080\nhw.lcd.height=2400\nhw.lcd.density=420\n"
    )
    log = tmp_path / "adb.log"
    log.touch()
    state = tmp_path / "whoami"
    state.write_text("shell\n")
    package = f"echo '    versionCode={installed} minSdk=21'" if installed else ":"
    adb = sdk / "platform-tools/adb"
    adb.write_text(f"""#!/bin/bash
echo "$*" >> {log}
case "$*" in
  devices) printf 'List of devices attached\\nemulator-5554\\tdevice\\n' ;;
  *"emu avd name"*) printf 'unciv_api34\\nOK\\n' ;;
  *" unroot") echo shell > {state} ;;
  *" root") echo root > {state} ;;
  *"shell whoami"*) cat {state} ;;
  *"dumpsys package"*) {package} ;;
  *"dumpsys display"*) echo 'DisplayDeviceInfo{{"Built-in Screen": cutout DisplayCutout{{insets=Rect(0, 0 - 0, 0)}}' ;;
esac
""")
    adb.chmod(0o755)
    result = subprocess.run(
        ["bash", str(ROOT / "scripts/check_env.sh"), *args],
        check=False,
        env=dict(os.environ, ANDROID_HOME=str(sdk), HOME=str(tmp_path / "home")),
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result, log.read_text()


def check_lines(stdout):
    lines = {}
    for line in stdout.splitlines():
        if line.startswith(("PASS", "FAIL")):
            status, name, *detail = line.split(maxsplit=2)
            lines[name] = (status, detail[0] if detail else "")
    return lines


def assert_only_apk_differs(result, apk_status):
    """The JDK check has a fixed path, so its result depends on this host."""
    lines = check_lines(result.stdout)
    assert {n for n, v in lines.items() if v[0] == "PASS"} >= CHECK_ENV_OTHER_CHECKS
    assert lines["unciv-apk"][0] == apk_status
    jdk_passed = lines["jdk"][0] == "PASS"
    assert result.returncode == (0 if apk_status == "PASS" and jdk_passed else 1)
    return lines["unciv-apk"][1]


def test_check_env_default_expects_the_v2_manifest_build(tmp_path):
    result, _ = run_check_env(tmp_path, v2_version_code())
    detail = assert_only_apk_differs(result, "PASS")
    assert v2_version_code() in detail
    assert V2_MANIFEST in detail


def test_check_env_default_mismatch_names_both_values_and_source(tmp_path):
    result, _ = run_check_env(tmp_path, "1271")
    detail = assert_only_apk_differs(result, "FAIL")
    assert "versionCode 1271," in detail
    assert f"expected {v2_version_code()}" in detail
    assert V2_MANIFEST in detail


def test_check_env_explicit_stage0_version_passes(tmp_path):
    result, _ = run_check_env(tmp_path, "1271", "--version-code", "1271")
    detail = assert_only_apk_differs(result, "PASS")
    assert "versionCode 1271" in detail
    assert "--version-code" in detail


def test_check_env_explicit_stage0_version_mismatch_fails(tmp_path):
    result, _ = run_check_env(tmp_path, "1271048", "--version-code", "1271")
    detail = assert_only_apk_differs(result, "FAIL")
    assert "versionCode 1271048, expected 1271 (from --version-code)" in detail


def test_check_env_explicit_manifest_is_the_source(tmp_path):
    manifest = ROOT / "fixtures/stage2/screens.json"
    code = json.loads(manifest.read_text())["build"]["version_code"]
    result, _ = run_check_env(tmp_path, code, "--manifest", str(manifest))
    detail = assert_only_apk_differs(result, "PASS")
    assert code in detail
    assert str(manifest) in detail


def test_check_env_not_installed_names_expected_and_source(tmp_path):
    result, _ = run_check_env(tmp_path, None)
    detail = assert_only_apk_differs(result, "FAIL")
    assert "not installed" in detail
    assert v2_version_code() in detail
    assert V2_MANIFEST in detail


@pytest.mark.parametrize(
    "args,manifest_text,message",
    [
        (["--version-code", "1271", "--manifest", "m.json"], None, "exclusive"),
        (["--stage0"], None, "unknown argument"),
        (["--manifest"], None, "needs a value"),
        (["--version-code"], None, "needs a value"),
        (["--version-code", "12a"], None, "must be digits"),
        (["--version-code", ""], None, "must be digits"),
        (["--manifest", ""], None, "bad manifest"),
        (["--manifest", "{manifest}"], None, "bad manifest"),
        (["--manifest", "{manifest}"], "not json", "bad manifest"),
        (["--manifest", "{manifest}"], "{}", "bad manifest"),
        (["--manifest", "{manifest}"], '{"build": []}', "bad manifest"),
        (
            ["--manifest", "{manifest}"],
            '{"build": {"version_code": 1}}',
            "bad manifest",
        ),
        (
            ["--manifest", "{manifest}"],
            '{"build": {"version_code": "12a"}}',
            "bad manifest",
        ),
    ],
)
def test_check_env_invalid_input_exits_2_before_any_adb_call(
    tmp_path, args, manifest_text, message
):
    manifest = tmp_path / "manifest.json"
    if manifest_text is not None:
        manifest.write_text(manifest_text)
    result, adb_calls = run_check_env(
        tmp_path, "1271048", *[a.format(manifest=manifest) for a in args]
    )
    assert result.returncode == 2
    assert message in result.stderr
    assert result.stdout == ""
    assert adb_calls == ""
