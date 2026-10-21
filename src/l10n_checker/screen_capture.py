"""Manifest-driven capture, device-write journal and decoded-pixel evidence."""

import html
import io
import json
import re
import shlex
import tarfile
import uuid
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

from l10n_checker.capture import (
    PACKAGE,
    SETTINGS_PATH,
    CaptureError,
    Device,
    filename,
    output_directory,
    owner_and_mode,
    png_size,
    unciv_in_foreground,
)
from l10n_checker.hook import HookFailure, request_screen
from l10n_checker.screen_manifest import Inputs, digest
from l10n_checker.text_dump import canonical_bytes, read_dump, rgba_digest

SAVES_PATH = f"/sdcard/Android/data/{PACKAGE}/files/SaveFiles"


def write_json(path: Path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def new_folder(folder: Path, overwrite: bool) -> Path:
    if folder.is_symlink():
        raise CaptureError("Refusing a symbolic-link run folder")
    folder = output_directory(folder)
    if folder.exists() and any(folder.iterdir()):
        if not overwrite:
            raise CaptureError(
                "Capture run folder already exists; use a fresh folder or --overwrite"
            )
        # Preserve the previous run, including PNGs that could otherwise be
        # mistaken for new successes after a failed overwrite attempt.
        folder.rename(folder.with_name(folder.name + ".previous-" + uuid.uuid4().hex))
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def save_inventory(data: bytes) -> dict[str, str]:
    try:
        with tarfile.open(fileobj=io.BytesIO(data)) as archive:
            return {
                item.name: digest(archive.extractfile(item).read())
                for item in archive.getmembers()
                if item.isfile()
            }
    except tarfile.TarError as exc:
        raise CaptureError("SaveFiles backup is not a valid tar archive") from exc


def read_saves(device: Device) -> bytes:
    return device.run("exec-out", "tar", "-cf", "-", "-C", SAVES_PATH, ".")


def check_build(device: Device, inputs: Inputs) -> dict:
    device.connect()
    device.check_cutout()
    manifest = inputs.manifest
    if device.build() != manifest.build.version_code:
        raise CaptureError("Installed Unciv versionCode differs from the manifest")
    paths = device.shell("pm", "path", PACKAGE).strip().splitlines()
    if len(paths) != 1 or not paths[0].startswith("package:"):
        raise CaptureError("Expected one installed Unciv APK")
    apk_path = paths[0].removeprefix("package:")
    checksum = device.shell("sha256sum " + shlex.quote(apk_path)).split()
    apk_sha = checksum[0] if checksum else None
    if apk_sha != manifest.build.apk_sha256:
        raise CaptureError("Installed APK SHA-256 differs from the clean hook build")
    density = re.findall(
        r"(?:Physical|Override) density: (\d+)", device.shell("wm", "density")
    )
    if not density or int(density[-1]) != manifest.density_dpi:
        raise CaptureError("Emulator density differs from the manifest")
    if sorted(device.size()) != sorted(manifest.resolution):
        raise CaptureError("Emulator dimensions differ from the manifest")
    return {
        "version_code": device.build(),
        "apk_sha256": apk_sha,
        "density_dpi": int(density[-1]),
    }


def backup_device(device: Device, inputs: Inputs, folder: Path) -> dict:
    """Call with adbd already root. No app-data writes or save provisioning."""
    device.force_stop()
    if device.pid():
        raise CaptureError("Unciv is still running after force-stop")
    private = folder / "private"
    private.mkdir(mode=0o700)
    stat = device.stat(SETTINGS_PATH)
    if stat is None:
        raise CaptureError("GameSettings.json is absent; no device data was written")
    original = device.read_file(SETTINGS_PATH)
    if len(original) != int(stat.split()[3]):
        raise CaptureError("Incomplete GameSettings.json backup")
    try:
        if not isinstance(json.loads(original), dict):
            raise TypeError("not an object")
    except (ValueError, TypeError) as exc:
        raise CaptureError(
            "Existing GameSettings.json is not a valid JSON object; no app data written"
        ) from exc
    backup = private / "GameSettings.json"
    backup.write_bytes(original)
    backup.chmod(0o600)
    if backup.read_bytes() != original or device.read_file(SETTINGS_PATH) != original:
        raise CaptureError("Settings backup/readback mismatch")
    saves = read_saves(device)
    archive = private / "SaveFiles.tar"
    archive.write_bytes(saves)
    archive.chmod(0o600)
    inventory = save_inventory(saves)
    if (
        save_inventory(archive.read_bytes()) != inventory
        or save_inventory(read_saves(device)) != inventory
    ):
        raise CaptureError("Save backup/readback mismatch")
    for fixture in inputs.manifest.fixtures:
        # Registry names contain no spaces or shell metacharacters.
        current = inventory.get("./" + fixture.name)
        if current != fixture.sha256:
            raise CaptureError(
                f"Device fixture missing or changed: {fixture.name}; no save was copied"
            )
    return {
        "original": original,
        "stat": stat,
        "saves": inventory,
        "public": {
            "settings_sha256": digest(original),
            "settings_stat": stat,
            "settings_backup": str(backup.relative_to(folder)),
            "saves_backup": str(archive.relative_to(folder)),
            "saves": inventory,
            "save_copies_needed": [],
        },
    }


def planned_operations(
    inputs: Inputs, languages: list[str], original_sha: str
) -> list[dict]:
    operations = []
    for pass_number in (1, 2):
        for language in languages:
            operations.append(
                {
                    "operation": "replace_settings",
                    "pass": pass_number,
                    "language": language,
                    "path": SETTINGS_PATH,
                    "sha256": digest(inputs.settings[language]),
                    "screen_order": [
                        s.id for s in inputs.screens(language, pass_number == 2)
                    ],
                }
            )
    operations.append(
        {
            "operation": "restore_original_settings",
            "path": SETTINGS_PATH,
            "sha256": original_sha,
        }
    )
    return operations


def planned_hook_outputs(
    inputs: Inputs, languages: list[str], namespace: str
) -> list[dict]:
    """Preallocate every v2 request/output so device approval names exact paths."""
    if re.fullmatch(r"[a-f0-9]{32}", namespace) is None:
        raise CaptureError("Invalid hook-output namespace")
    return [
        {
            "pass": n,
            "language": language,
            "screen": screen.id,
            "request": f"i47-{namespace}-{n}-{li}-{si}",
            "temporary": f"files/l10n-hook/i47-{namespace}-{n}-{li}-{si}.json.tmp",
            "file": f"files/l10n-hook/i47-{namespace}-{n}-{li}-{si}.json",
        }
        for n in (1, 2)
        for li, language in enumerate(languages)
        for si, screen in enumerate(inputs.screens(language, n == 2))
    ]


def prepare_device(
    device: Device, inputs: Inputs, folder: Path, languages=None
) -> dict:
    """Create verified private backups and an exact plan; never write app data."""
    languages = inputs.languages(languages)
    folder = new_folder(folder, False)
    observed = check_build(device, inputs)
    try:
        device.root()
        snapshot = backup_device(device, inputs, folder)
    finally:
        device.unroot()
    result = {
        "mode": "prepare_only",
        "app_data_writes": 0,
        "manifest_sha256": inputs.sha256,
        "observed_build": observed,
        "backup": snapshot["public"],
        "planned_app_data_operations": planned_operations(
            inputs, languages, digest(snapshot["original"])
        ),
        "other_device_operations": [
            "adb root/unroot and force-stop; app left stopped",
            "one cold hook launch per language per pass; pass 2 reverses screen order",
            "after a client timeout or uncertain launch, force-stop before another request",
            "unique Android logcat barrier per request (Android logs only)",
        ],
    }
    if inputs.manifest.protocol_version == 2:
        namespace = uuid.uuid4().hex
        result.update(
            serial=device.serial,
            request_namespace=namespace,
            planned_hook_output_operations=planned_hook_outputs(
                inputs, languages, namespace
            ),
        )
    write_json(folder / "device-plan.json", result)
    return result


def compare_pixels(first: Path, second: Path) -> dict:
    with Image.open(first) as image:
        a = image.convert("RGBA")
    with Image.open(second) as image:
        b = image.convert("RGBA")
    if a.size != b.size:
        return {"status": "size_mismatch", "first_size": a.size, "second_size": b.size}
    channels = ImageChops.difference(a, b).split()
    mask = channels[0]
    for channel in channels[1:]:
        mask = ImageChops.lighter(mask, channel)
    total = a.width * a.height
    count = total - mask.histogram()[0]
    return {
        "status": "identical" if count == 0 else "different",
        "total_pixels": total,
        "different_pixels": count,
        "different_share": count / total,
        "bounding_box": mask.getbbox(),
        "bounding_box_convention": "[left, top, right-exclusive, bottom-exclusive] or null",
    }


def gallery(folder: Path, inputs: Inputs, languages: list[str], records: list[dict]):
    selected = {(r["screen"], r["language"]): r for r in records if r["pass"] == 1}
    figures = []
    width, height = 480, 250
    sheet = Image.new(
        "RGB",
        (width * len(languages), height * len(inputs.manifest.screens)),
        "#20242a",
    )
    draw = ImageDraw.Draw(sheet)
    for row, screen in enumerate(inputs.manifest.screens):
        for column, language in enumerate(languages):
            record = selected.get((screen.id, language))
            if record is None:
                continue
            title = f"{screen.id} / {language}: {record['status']}"
            x, y = column * width, row * height
            draw.text((x + 8, y + 5), title, fill="white")
            content = html.escape(record.get("reason", ""))
            if record["status"] == "captured":
                relative = record["png"]
                content = f'<a href="{html.escape(relative)}"><img src="{html.escape(relative)}" alt="{html.escape(title)}"></a>'
                with Image.open(folder / relative) as image:
                    image = image.convert("RGB")
                    image.thumbnail((width - 8, height - 30))
                    sheet.paste(image, (x + 4, y + 26))
            figures.append(
                f"<figure><figcaption>{html.escape(title)}</figcaption>{content}</figure>"
            )
    sheet.save(folder / "contact-sheet.png")
    (folder / "gallery.html").write_text(
        '<!doctype html><html lang="en"><meta charset="utf-8"><title>Stage 2 capture review</title>'
        "<style>body{background:#20242a;color:white;font:16px sans-serif}main{display:grid;grid-template-columns:repeat(2,minmax(0,1fr))}figure{margin:12px}img{width:100%}</style>"
        "<h1>Stage 2 capture review</h1><p>Primary pass only. Capture evidence; no defect check or labels.</p><main>"
        + "\n".join(figures)
        + "</main></html>\n"
    )


def capture_manifest(
    device: Device,
    inputs: Inputs,
    folder: Path,
    languages=None,
    overwrite=False,
    timeout_s=90.0,
    request=request_screen,
    device_plan: Path | None = None,
) -> dict:
    languages = inputs.languages(languages)
    v2 = inputs.manifest.protocol_version == 2
    approved = None
    if v2:
        if device_plan is None:
            raise CaptureError("Protocol v2 requires a prepared exact device plan")
        approved = json.loads(device_plan.read_bytes())
        outputs = planned_hook_outputs(
            inputs, languages, approved.get("request_namespace", "")
        )
        if approved.get("planned_hook_output_operations") != outputs:
            raise CaptureError(
                "Prepared hook output operations changed; no device access"
            )
    if timeout_s <= 60 or not timeout_s < float("inf"):
        raise CaptureError("Hook deadline must be finite and greater than 60 seconds")
    folder = new_folder(folder, overwrite)
    summary = {
        "schema_version": 1,
        "status": "running",
        "manifest_sha256": inputs.sha256,
        "languages": languages,
        "passes": ["forward", "reverse"],
        "records": [],
        "comparisons": [],
        "app_data_operations": [],
        "live_provider_requests": 0,
        "api_spend_usd": 0,
    }
    summary_path = folder / "summary.json"

    def checkpoint():
        write_json(summary_path, summary)

    checkpoint()
    snapshot = None
    output_map = (
        {(r["screen"], r["language"], r["pass"]): r for r in outputs} if v2 else {}
    )

    def write_settings(data: bytes, operation: str, **details):
        entry = {
            "operation": operation,
            "path": SETTINGS_PATH,
            "sha256": digest(data),
            "status": "attempted",
            **details,
        }
        summary["app_data_operations"].append(entry)
        checkpoint()
        device.force_stop()
        if device.pid():
            raise CaptureError("Unciv is still running before settings write")
        device.write_file(SETTINGS_PATH, data)
        if device.read_file(SETTINGS_PATH) != data or owner_and_mode(
            device.stat(SETTINGS_PATH)
        ) != owner_and_mode(snapshot["stat"]):
            raise CaptureError(
                "Settings write/readback or ownership verification failed"
            )
        entry["status"] = "verified"
        checkpoint()

    try:
        summary["observed_build"] = check_build(device, inputs)
        try:
            device.root()
            snapshot = backup_device(device, inputs, folder)
            summary["backup"] = snapshot["public"]
            summary["planned_app_data_operations"] = planned_operations(
                inputs, languages, digest(snapshot["original"])
            )
            if device_plan is not None:
                approved = json.loads(device_plan.read_bytes())
                if (
                    approved.get("manifest_sha256") != inputs.sha256
                    or approved.get("observed_build") != summary["observed_build"]
                    or approved.get("planned_app_data_operations")
                    != summary["planned_app_data_operations"]
                    or approved.get("backup", {}).get("saves") != snapshot["saves"]
                    or (v2 and approved.get("serial") != device.serial)
                ):
                    raise CaptureError(
                        "Device inputs changed since the prepared plan; no app data written"
                    )
                summary["device_plan_sha256"] = digest(device_plan.read_bytes())
            checkpoint()
            try:
                for pass_number in (1, 2):
                    for language in languages:
                        payload = inputs.settings[language]
                        write_settings(
                            payload,
                            "replace_settings",
                            language=language,
                            pass_number=pass_number,
                        )
                        for screen in inputs.screens(language, pass_number == 2):
                            output = output_map.get((screen.id, language, pass_number))
                            token = (
                                output["request"] if v2 else "i41-" + uuid.uuid4().hex
                            )
                            state = inputs.states[screen.id, language]
                            record = {
                                "pass": pass_number,
                                "language": language,
                                "screen": screen.id,
                                "request": token,
                                "state": state,
                                "status": "pending",
                            }
                            summary["records"].append(record)
                            checkpoint()
                            try:
                                if v2:
                                    operation = {
                                        "operation": "hook_output",
                                        **output,
                                        "status": "attempted",
                                    }
                                    summary["app_data_operations"].append(operation)
                                    checkpoint()
                                record["readiness"] = request(
                                    device,
                                    screen.id,
                                    token,
                                    state,
                                    timeout_s,
                                    **({"protocol_version": 2} if v2 else {}),
                                )
                                unciv_in_foreground(device)
                                device.check_cutout()
                                size = tuple(inputs.manifest.resolution)
                                if (
                                    device.size() != size
                                    or device.build()
                                    != inputs.manifest.build.version_code
                                ):
                                    raise CaptureError(
                                        "Device resolution/build changed before screencap"
                                    )
                                png = device.screenshot()
                                device.check_cutout()
                                unciv_in_foreground(device)
                                if png_size(png) != size or device.size() != size:
                                    raise CaptureError(
                                        "Invalid PNG size or changed orientation; no PNG saved"
                                    )
                                with Image.open(io.BytesIO(png)) as image:
                                    image.load()
                                if v2:
                                    game_language = next(
                                        l.game_language
                                        for l in inputs.manifest.languages
                                        if l.code == language
                                    )
                                    dump_event = record["readiness"].get("dump")
                                    if (
                                        not dump_event
                                        or dump_event["file"] != output["file"]
                                    ):
                                        raise CaptureError(
                                            "Missing or mismatched prepared dump output"
                                        )
                                    dump = read_dump(
                                        device,
                                        dump_event,
                                        {
                                            "screen": screen.id,
                                            "language": game_language,
                                            "build_version_code": int(
                                                inputs.manifest.build.version_code
                                            ),
                                            "state_sha256": digest(
                                                canonical_bytes(state)
                                            ),
                                            "image_size": list(size),
                                        },
                                    )
                                    operation.update(
                                        status="verified", sha256=digest(dump)
                                    )
                                if device.read_file(SETTINGS_PATH) != payload:
                                    raise CaptureError(
                                        "Settings changed while capturing; no PNG saved"
                                    )
                                target = Path(f"pass-{pass_number}") / filename(
                                    screen.id,
                                    language,
                                    "x".join(map(str, size)),
                                    "clean",
                                    device.build(),
                                )
                                (folder / target).parent.mkdir(exist_ok=True)
                                temporary = (folder / target).with_suffix(".tmp")
                                with temporary.open("xb") as stream:
                                    stream.write(png)
                                temporary.rename(folder / target)
                                if v2:
                                    dump_target = target.with_suffix(".texts.json")
                                    pair_target = target.with_suffix(".pair.json")
                                    dump_temporary = (folder / dump_target).with_suffix(
                                        ".tmp"
                                    )
                                    with dump_temporary.open("xb") as stream:
                                        stream.write(dump)
                                    dump_temporary.rename(folder / dump_target)
                                    pair = {
                                        "pair_version": 1,
                                        "protocol_version": 2,
                                        "screen": screen.id,
                                        "language": game_language,
                                        "build": inputs.manifest.build.model_dump(),
                                        "state_sha256": digest(canonical_bytes(state)),
                                        "png": target.name,
                                        "png_sha256": digest(png),
                                        "rgba_sha256": rgba_digest(png),
                                        "dump": dump_target.name,
                                        "dump_sha256": digest(dump),
                                    }
                                    # The sidecar is the final commit marker. A PNG alone
                                    # never establishes a successful v2 pair.
                                    write_json(folder / pair_target, pair)
                                    record.update(
                                        dump=str(dump_target),
                                        dump_sha256=digest(dump),
                                        pair=str(pair_target),
                                        rgba_sha256=pair["rgba_sha256"],
                                    )
                                record.update(
                                    status="captured",
                                    png=str(target),
                                    png_sha256=digest(png),
                                )
                            except (CaptureError, OSError) as exc:
                                record.update(status="failed", reason=str(exc))
                                if isinstance(exc, HookFailure):
                                    record["events"] = exc.events
                                    record["terminal_received"] = exc.terminal
                                if not isinstance(exc, HookFailure) or not exc.terminal:
                                    # Mandatory after timeout/uncertain launch. No request
                                    # can supersede an unfinished one on build 1271045.
                                    device.force_stop()
                                    record["recovery"] = (
                                        "force_stopped_before_next_request"
                                    )
                            checkpoint()
                        device.force_stop()
                        if device.read_file(SETTINGS_PATH) != payload:
                            raise CaptureError(
                                "Settings changed during the language pass"
                            )
                current_saves = save_inventory(read_saves(device))
                summary["saves_unchanged"] = current_saves == snapshot["saves"]
                if not summary["saves_unchanged"]:
                    raise CaptureError(
                        "Device saves changed; backups retained, no automatic save overwrite"
                    )
            finally:
                write_settings(snapshot["original"], "restore_original_settings")
                if device.stat(SETTINGS_PATH) != snapshot["stat"]:
                    raise CaptureError("Original settings metadata was not restored")
                summary["settings_restored"] = True
        finally:
            device.unroot()
    except (CaptureError, OSError, ValueError) as exc:
        summary["fatal_error"] = str(exc)
    finally:
        by_key = {
            (r["screen"], r["language"], r["pass"]): r for r in summary["records"]
        }
        for language in languages:
            for screen in inputs.screens(language):
                pair = [by_key.get((screen.id, language, n), {}) for n in (1, 2)]
                comparison = {
                    "screen": screen.id,
                    "language": language,
                    "status": "unavailable",
                }
                if all(r.get("status") == "captured" for r in pair):
                    comparison.update(
                        compare_pixels(*(folder / r["png"] for r in pair))
                    )
                    if v2:
                        equal = (folder / pair[0]["dump"]).read_bytes() == (
                            folder / pair[1]["dump"]
                        ).read_bytes()
                        comparison["dump_status"] = (
                            "identical" if equal else "different"
                        )
                summary["comparisons"].append(comparison)
        success = not summary.get("fatal_error") and all(
            c["status"] == "identical"
            and (not v2 or c.get("dump_status") == "identical")
            for c in summary["comparisons"]
        )
        summary["status"] = "complete" if success else "failed"
        checkpoint()
    gallery(folder, inputs, languages, summary["records"])
    return summary
