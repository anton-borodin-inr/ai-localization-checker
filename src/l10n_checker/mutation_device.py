"""Approved install/capture transactions; never uninstall, provision saves or build."""

import io
import shlex
import subprocess
import tarfile
from pathlib import Path

from l10n_checker.capture import (
    PACKAGE,
    REPO_ROOT,
    CaptureError,
    failure_details,
    preserve_cleanup,
    retain_cleanup,
)
from l10n_checker.mutation_catalog import no_symlinks, require
from l10n_checker.screen_capture import write_json
from l10n_checker.screen_manifest import digest
from l10n_checker.text_dump import canonical_bytes

DATA_ROOTS = {
    "private": f"/data/user/0/{PACKAGE}",
    "device_encrypted": f"/data/user_de/0/{PACKAGE}",
    "external": f"/sdcard/Android/data/{PACKAGE}",
}


ANDROIDX_BOOKKEEPING = (
    "private:files/profileInstalled",
    "private:no_backup/androidx.work.workdb",
    "private:no_backup/androidx.work.workdb-shm",
    "private:no_backup/androidx.work.workdb-wal",
)


def preservation_policy():
    """Task-specific owner authorization, not a general cache/database ignore."""
    return {
        "decision": "D-051",
        "version": 1,
        "regular_file_paths": list(ANDROIDX_BOOKKEEPING),
        "allowed_changes": ["bytes", "sha256", "presence"],
        "app_data_writes": 0,
    }


def preservation_report(before, after, allowed_new=()):
    """Compare only; retain all four observations, including explicit absence."""
    changes = inventory_changes(before, after, allowed_new)

    def exempt(change):
        old, new = change["before"], change["after"]
        return (
            change["path"] in ANDROIDX_BOOKKEEPING
            and all(v is None or v.get("type") == "file" for v in (old, new))
            and (
                old is None
                or new is None
                or {k: v for k, v in old.items() if k not in {"bytes", "sha256"}}
                == {k: v for k, v in new.items() if k not in {"bytes", "sha256"}}
            )
        )

    return {
        "policy": preservation_policy(),
        "bookkeeping": [
            {"path": name, "before": before.get(name), "after": after.get(name)}
            for name in ANDROIDX_BOOKKEEPING
        ],
        "exempt_changes": [c for c in changes if exempt(c)],
        "unexpected_changes": [c for c in changes if not exempt(c)],
    }


def data_inventory(archives):
    result = {}
    for root, raw in archives.items():
        with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
            for member in archive.getmembers():
                require(
                    not Path(member.name).is_absolute()
                    and ".." not in Path(member.name).parts,
                    "Unsafe app-data backup member",
                )
                name = root + ":" + str(Path(member.name))
                require(name not in result, "Duplicate app-data backup member")
                require(
                    member.isfile() or member.isdir() or member.issym(),
                    "Unsupported app-data backup member",
                )
                value = {
                    "uid": member.uid,
                    "gid": member.gid,
                    "mode": member.mode,
                    "type": "file"
                    if member.isfile()
                    else "directory"
                    if member.isdir()
                    else "symlink",
                }
                if member.isfile():
                    payload = archive.extractfile(member).read()
                    require(len(payload) == member.size, "Incomplete app-data backup")
                    value.update(bytes=len(payload), sha256=digest(payload))
                elif member.issym():
                    value["target"] = member.linkname
                result[name] = value
    require(bool(result), "Empty app-data backup")
    return result


def inventory_changes(before, after, allowed_new=()):
    """Only declared new hook outputs are exempt; existing data stays exact."""
    excluded = set(allowed_new) - set(before)
    return [
        {"path": name, "before": before.get(name), "after": after.get(name)}
        for name in sorted(set(before) | set(after))
        if name not in excluded and before.get(name) != after.get(name)
    ]


def read_app_data(device):
    require(not device.pid(), "App running during data backup")
    archives = {}
    with preserve_cleanup(device.unroot, "Unroot"):
        device.root()
        for name, path in DATA_ROOTS.items():
            present = device.shell(
                "if [ -d " + shlex.quote(path) + " ]; then printf present; fi"
            ).strip()
            if present == "present":
                archives[name] = device.run(
                    "exec-out", "tar", "-cf", "-", "-C", path, "."
                )
        require(
            "private" in archives and "external" in archives,
            "Required package app-data roots absent",
        )
        data_inventory(archives)
    return archives


def save_backup(folder, archives):
    folder = no_symlinks(folder)
    folder.mkdir(mode=0o700, parents=True, exist_ok=False)
    refs = {}
    for name, raw in archives.items():
        target = folder / (name + ".tar")
        with target.open("xb") as stream:
            stream.write(raw)
        target.chmod(0o600)
        require(target.read_bytes() == raw, "Backup host readback mismatch")
        refs[name] = {"path": target.name, "sha256": digest(raw), "bytes": len(raw)}
    inventory = data_inventory(archives)
    write_json(folder / "inventory.json", inventory)
    return {"archives": refs, "inventory_sha256": digest(canonical_bytes(inventory))}


def installed_identity(device, tools, folder):
    paths = device.shell("pm", "path", PACKAGE).strip().splitlines()
    require(
        len(paths) == 1 and paths[0].startswith("package:"),
        "Expected one installed APK",
    )
    remote = paths[0].removeprefix("package:")
    require(
        remote.startswith("/data/app/") and "\n" not in remote,
        "Unexpected installed APK path",
    )
    raw = device.run("exec-out", "cat", remote)
    folder = no_symlinks(folder)
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = folder / "installed.apk"
    path.write_bytes(raw)
    path.chmod(0o600)
    identity = tools.inspect(path)
    require(
        device.build() == identity["version_code"],
        "Installed version changed while inspecting",
    )
    return {
        "apk_sha256": digest(raw),
        "version_code": identity["version_code"],
        "certificate_sha256": identity["certificate_sha256"],
    }


def install_verified(
    device,
    apk,
    build,
    certificate_sha256,
    *,
    tools,
    folder,
    environment,
    previous_inventory=None,
):
    folder = no_symlinks(folder)
    folder.mkdir(mode=0o700, parents=True, exist_ok=False)
    journal = {
        "command": ["install", "-r", "-d", str(apk)],
        "build": build,
        "status": "preparing",
        "app_data_preserved": False,
        "preservation_policy": preservation_policy(),
    }

    def checkpoint():
        write_json(folder / "install.json", journal)

    checkpoint()
    try:
        device.force_stop()
        require(not device.pid(), "App still running before install")
        previous = installed_identity(device, tools, folder / "before-apk")
        require(
            previous["certificate_sha256"] == certificate_sha256,
            "Installed certificate mismatch; never uninstall",
        )
        journal["previous_build"] = previous
        before = read_app_data(device)
        journal["backup"] = save_backup(folder / "before", before)
        inventory = data_inventory(before)
        if previous_inventory is not None:
            journal["input_preservation"] = preservation_report(
                previous_inventory, inventory
            )
            checkpoint()
            require(
                not journal["input_preservation"]["unexpected_changes"],
                "Unexpected app-data change before install",
            )
        readback = data_inventory(read_app_data(device))
        write_json(folder / "before-readback.json", readback)
        journal["backup_readback_preservation"] = preservation_report(
            inventory, readback
        )
        checkpoint()
        require(
            not journal["backup_readback_preservation"]["unexpected_changes"],
            "App data changed while verifying backup",
        )
        require(
            digest(no_symlinks(apk).read_bytes()) == build["apk_sha256"],
            "APK changed before install",
        )
        journal["status"] = "install_attempted"
        journal["install_attempted"] = True
        checkpoint()
        output = device.run("install", "-r", "-d", str(apk)).decode("utf-8")
        journal["stdout"] = output
        require(
            output.strip().splitlines()[-1:] == ["Success"],
            "Install did not report Success",
        )
        observed = installed_identity(device, tools, folder / "after-apk")
        require(
            all(observed[key] == build[key] for key in ("version_code", "apk_sha256"))
            and observed["certificate_sha256"] == certificate_sha256,
            "Installed APK identity mismatch",
        )
        journal["observed_build"] = observed
        journal["environment"] = environment(build)
        after = read_app_data(device)
        journal["post_install"] = save_backup(folder / "after", after)
        after_inventory = data_inventory(after)
        journal["data_changes"] = inventory_changes(inventory, after_inventory)
        journal["preservation"] = preservation_report(inventory, after_inventory)
        journal["post_readback_preservation"] = preservation_report(
            readback, after_inventory
        )
        checkpoint()
        require(
            not journal["preservation"]["unexpected_changes"]
            and not journal["post_readback_preservation"]["unexpected_changes"],
            "App data preservation failed; no automatic repair",
        )
        journal.update(status="verified", app_data_preserved=True)
        return journal
    except (
        CaptureError,
        OSError,
        ValueError,
        tarfile.TarError,
        subprocess.SubprocessError,
    ) as exc:
        journal.update(
            status="failed", error=str(exc), error_details=failure_details(exc)
        )
        raise
    finally:
        checkpoint()


def environment_check(build, folder):
    folder.mkdir(parents=True, exist_ok=False)
    command = [str(REPO_ROOT / "scripts/check_env.sh")]
    if build["version_code"] != "1271048":
        command += ["--version-code", build["version_code"]]
    receipt = {"command": command, "build": build, "exit_code": None}
    stdout = stderr = b""
    try:
        result = subprocess.run(
            command, cwd=REPO_ROOT, capture_output=True, timeout=180, check=False
        )
        stdout, stderr = result.stdout, result.stderr
        receipt["exit_code"] = result.returncode
    except (OSError, subprocess.SubprocessError) as exc:
        receipt["error_details"] = failure_details(exc)
        stdout = getattr(exc, "stdout", None) or b""
        stderr = getattr(exc, "stderr", None) or b""
        raise
    finally:
        if isinstance(stdout, str):
            stdout = stdout.encode("utf-8")
        if isinstance(stderr, str):
            stderr = stderr.encode("utf-8")
        (folder / "stdout.txt").write_bytes(stdout)
        (folder / "stderr.txt").write_bytes(stderr)
        receipt.update(stdout_sha256=digest(stdout), stderr_sha256=digest(stderr))
        write_json(folder / "receipt.json", receipt)
    require(result.returncode == 0, "Mandatory environment check failed")
    return receipt


def assert_idle(device):
    result = subprocess.run(
        ["pgrep", "-fl", "l10n-capture"], capture_output=True, timeout=10, check=False
    )
    require(
        result.returncode == 1 and not result.stdout.strip(),
        "Another l10n-capture process is active or process check failed",
    )
    device.connect()
    online = [
        line.split()[0]
        for line in device.run("devices").decode().splitlines()
        if len(line.split()) == 2
        and line.split()[0].startswith("emulator-")
        and line.split()[1] == "device"
    ]
    require(
        online == [device.serial],
        "Exactly one emulator is required by the environment checker",
    )
    require(
        not device.pid(), "Unciv is already running; emulator has not been released"
    )


def execute_stages(control, calibration, production, restore):
    """The restore boundary encloses every capture, including a failed calibration."""
    try:
        require(control()["passed"], "Control capture failed")
        require(calibration()["passed"], "Strict calibration gate failed")
        for capture in production:
            require(capture()["passed"], "Production qualification failed")
    except BaseException as original:
        try:
            restore()
        except BaseException as cleanup:  # noqa: BLE001
            # Cleanup must not replace the original error or cancellation.
            retain_cleanup(original, cleanup)
        raise
    else:
        restore()
