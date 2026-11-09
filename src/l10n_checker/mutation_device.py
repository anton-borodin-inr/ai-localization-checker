"""Approved install/capture transactions; never uninstall, provision saves or build."""

import shlex
import subprocess
import tarfile

from l10n_checker import app_data

# Shared app-data readers are also used by standalone capture.
from l10n_checker.app_data import (
    DATA_ROOTS,
    data_inventory,
    inventory_changes,
    preservation_policy,
    preservation_report,
    read_tar,
)
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

# Preserve the public compatibility constant without a cyclic dependency.
ANDROIDX_BOOKKEEPING = app_data.ANDROIDX_BOOKKEEPING


def read_app_data(device, *, evidence_dir=None, purpose="app-data"):
    require(
        evidence_dir is not None, "Durable app-data read evidence directory required"
    )
    require(not device.pid(), "App running during data backup")
    archives = {}
    with preserve_cleanup(device.unroot, "Unroot"):
        device.root()
        for name, path in DATA_ROOTS.items():
            present = device.shell(
                "if [ -d " + shlex.quote(path) + " ]; then printf present; fi"
            ).strip()
            if present == "present":
                archives[name] = read_tar(device, path, name, purpose, evidence_dir)
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
        before = read_app_data(
            device, evidence_dir=folder / "reads", purpose="install-before"
        )
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
        readback = data_inventory(
            read_app_data(
                device, evidence_dir=folder / "reads", purpose="install-readback"
            )
        )
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
        after = read_app_data(
            device, evidence_dir=folder / "reads", purpose="install-after"
        )
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
