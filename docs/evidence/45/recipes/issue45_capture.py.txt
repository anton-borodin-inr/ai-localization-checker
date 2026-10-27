"""Issue-45 captures using the unchanged D-038 client, after separate approval."""

import argparse
import hashlib
import io
import json
import uuid
from pathlib import Path

from issue45_backup import inventory
from PIL import Image

from l10n_checker.capture import (
    PACKAGE,
    SETTINGS_PATH,
    CaptureError,
    Device,
    filename,
    png_size,
    unciv_in_foreground,
)
from l10n_checker.hook import request_screen

REPO = Path(__file__).resolve().parents[1]
EVIDENCE = REPO / "docs/evidence/45"
BACKUP = REPO / "data/issue-45/pre-task-backup"
ALLOWED = {"tech-picker", "city-production"}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    temporary.replace(path)


def settings(device):
    return device.run("exec-out", "run-as", PACKAGE, "cat", SETTINGS_PATH)


def settings_stat(device):
    return device.shell(
        "run-as", PACKAGE, "stat", "-c", "%u:%g:%a:%s", SETTINGS_PATH
    ).strip()


def saves(device):
    directory = f"/sdcard/Android/data/{PACKAGE}/files"
    return inventory(device.run("exec-out", "tar", "-C", directory, "-cf", "-", "."))


def make_plan(variant):
    design = json.loads((EVIDENCE / "probe-design.json").read_text())
    backup = json.loads((BACKUP / "private/backup-manifest.json").read_text())
    if variant == "clean":
        build = design["clean_build"]
        screens = sorted(ALLOWED)
        languages = ["de", "en"]
    else:
        item = next(v for v in design["variants"] if v["id"] == variant)
        build = next(
            v
            for v in json.loads((EVIDENCE / "builds.json").read_text())
            if v["variant"] == variant
        )
        if not build.get("apk_sha256") or build["exit_code"]:
            raise CaptureError("Probe APK is not built and verified")
        screens, languages = [item["screen"]], item["languages"]
    plan = {
        "issue": 45,
        "variant": variant,
        "screens": screens,
        "languages": languages,
        "version_code": build["version_code"],
        "apk_sha256": build["apk_sha256"],
        "original_settings_sha256": backup["settings_sha256"],
        "original_settings_stat": backup["settings_stat"],
        "save_file_writes": 0,
        "installs_in_this_capture_command": 0,
        "device_operations": [
            "force-stop before every settings write; run-as, never adb root",
            "cold D-038 hook launch for the first screen of each language, with matching READY",
            "unique Android log barrier and request id per screen",
            "full unchanged 2400x1080 SDK adb screenshots after READY",
            "force-stop and restore original settings in finally; independent readback",
            "verify the complete external save-file inventory before and after",
        ],
        "app_data_operations": [],
        "inputs": {},
    }
    for lang in languages:
        relative = f"inputs/settings/{lang}.json"
        data = (EVIDENCE / relative).read_bytes()
        if digest(data) != design["inputs"][f"settings/{lang}.json"]["sha256"]:
            raise CaptureError("Settings template changed since design freeze")
        plan["inputs"][relative] = digest(data)
        plan["app_data_operations"].append(
            {
                "operation": "replace_settings",
                "language": lang,
                "path": SETTINGS_PATH,
                "sha256": digest(data),
                "bytes": len(data),
            }
        )
    for screen in screens:
        if screen not in ALLOWED:
            raise CaptureError("Screen outside the issue-45 allowlist")
        relative = f"inputs/states/{screen}.json"
        data = (EVIDENCE / relative).read_bytes()
        if digest(data) != design["inputs"][f"states/{screen}.json"]["sha256"]:
            raise CaptureError("Hook state changed since design freeze")
        plan["inputs"][relative] = digest(data)
    plan["app_data_operations"].append(
        {
            "operation": "restore_original_settings",
            "path": SETTINGS_PATH,
            "sha256": backup["settings_sha256"],
        }
    )
    return plan


def capture(device, plan, folder):
    backup = json.loads((BACKUP / "private/backup-manifest.json").read_text())
    original = (BACKUP / "private/GameSettings.json").read_bytes()
    if digest(original) != plan["original_settings_sha256"]:
        raise CaptureError("Original private backup changed")
    for relative, checksum in plan["inputs"].items():
        if digest((EVIDENCE / relative).read_bytes()) != checksum:
            raise CaptureError("Prepared input changed")
    device.connect()
    device.check_cutout()
    if device.build() != plan["version_code"]:
        raise CaptureError("Installed build differs from prepared device plan")
    paths = device.shell("pm", "path", PACKAGE).strip().splitlines()
    if len(paths) != 1 or not paths[0].startswith("package:/data/app/"):
        raise CaptureError("Unexpected installed APK paths")
    checksum = device.shell("sha256sum", paths[0].removeprefix("package:")).split()[0]
    if checksum != plan["apk_sha256"]:
        raise CaptureError("Installed APK hash differs from device plan")
    if device.shell("wm", "density").strip() != "Physical density: 420":
        raise CaptureError("Display density differs from D-014")
    device.force_stop()
    if (
        settings(device) != original
        or settings_stat(device) != plan["original_settings_stat"]
    ):
        raise CaptureError(
            "Settings changed since pre-task backup; no app-data write made"
        )
    if saves(device) != backup["archives"]["external"]["files"]:
        raise CaptureError("Saves changed since backup; no app-data write made")
    folder.mkdir(parents=True, exist_ok=False)
    audit = {
        "plan": plan,
        "captures": [],
        "app_data_operations": [],
        "status": "started",
    }

    def flush():
        write_json(folder / "capture-audit.json", audit)

    def write_settings(data, kind):
        device.force_stop()
        entry = {"operation": kind, "sha256": digest(data), "attempted": True}
        audit["app_data_operations"].append(entry)
        flush()
        echoed = device.run(
            "shell", "-T", "run-as", PACKAGE, "tee", SETTINGS_PATH, input=data
        )
        actual = settings(device)
        entry["transfer"] = "adb shell -T run-as tee"
        entry["readback_sha256"] = digest(actual)
        entry["readback_bytes"] = len(actual)
        flush()
        if echoed != data or actual != data:
            raise CaptureError("Settings write readback mismatch")
        if (
            settings_stat(device).split(":")[:3]
            != plan["original_settings_stat"].split(":")[:3]
        ):
            raise CaptureError("Settings uid/gid/mode changed")
        entry["readback_verified"] = True
        flush()

    try:
        for language in plan["languages"]:
            template = (EVIDENCE / f"inputs/settings/{language}.json").read_bytes()
            write_settings(template, f"apply_{language}")
            for screen in plan["screens"]:
                record = {"screen": screen, "language": language, "status": "requested"}
                audit["captures"].append(record)
                flush()
                state = json.loads(
                    (EVIDENCE / f"inputs/states/{screen}.json").read_text()
                )
                request = f"i45-{plan['variant']}-{language}-{uuid.uuid4().hex[:12]}"
                record["request_id"] = request
                record["hook"] = request_screen(device, screen, request, state, 90)
                unciv_in_foreground(device)
                device.check_cutout()
                image = device.screenshot()
                if png_size(image) != (2400, 1080) or device.size() != (2400, 1080):
                    raise CaptureError("Screenshot dimensions differ from D-014")
                with Image.open(io.BytesIO(image)) as decoded:
                    decoded.load()
                unciv_in_foreground(device)
                device.check_cutout()
                if (
                    settings(device) != template
                    or device.build() != plan["version_code"]
                ):
                    raise CaptureError("Settings/build changed during capture")
                name = filename(
                    screen,
                    language,
                    "2400x1080",
                    "probe-" + plan["variant"],
                    plan["version_code"],
                )
                target = folder / name
                with target.open("xb") as stream:
                    stream.write(image)
                record.update(
                    status="captured", png=name, sha256=digest(image), bytes=len(image)
                )
                flush()
        audit["status"] = "captured"
    except BaseException as exc:
        audit["status"] = "failed"
        audit["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        try:
            write_settings(original, "restore_original_settings")
            if settings_stat(device) != plan["original_settings_stat"]:
                raise CaptureError("Original settings metadata not restored")
            if saves(device) != backup["archives"]["external"]["files"]:
                raise CaptureError("Saves differ from pre-task backup")
            audit["settings_restored_byte_identical"] = True
            audit["all_saves_unchanged"] = True
            audit["app_left_stopped"] = True
        finally:
            flush()
    print(folder / "capture-audit.json")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare-plan", action="store_true")
    mode.add_argument("--approved-plan-sha256")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    plan = make_plan(args.variant)
    path = EVIDENCE / "device-plans" / f"{args.variant}.json"
    if args.prepare_plan:
        write_json(path, plan)
        print(f"{path}\nSHA-256 {digest(path.read_bytes())}")
        return
    if not path.exists() or digest(path.read_bytes()) != args.approved_plan_sha256:
        raise CaptureError("Missing or changed separately approved device plan")
    if json.loads(path.read_text()) != plan:
        raise CaptureError("Device plan no longer matches inputs/build/backup")
    if args.output is None or not args.output.resolve().is_relative_to(
        (REPO / "data/issue-45").resolve()
    ):
        raise CaptureError("Output must be a fresh issue-45 data folder")
    device = Device(
        Path("/Users/antonborodin/Library/Android/sdk/platform-tools/adb"),
        "emulator-5554",
    )
    capture(device, plan, args.output)


if __name__ == "__main__":
    main()
