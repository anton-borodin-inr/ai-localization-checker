"""Read-only issue-45 app backup through run-as; no root or app-data writes."""

import argparse
import hashlib
import io
import json
import os
import shlex
import subprocess
import tarfile
from pathlib import Path

PACKAGE = "com.unciv.app"
INTERNAL = f"/data/user/0/{PACKAGE}/files"
EXTERNAL = f"/sdcard/Android/data/{PACKAGE}/files"
EXPECTED_APK = "16b6e07eaa8f7ca35b71f361f0bdcceb7015987b60e796d15d2f3b53bb61af1a"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def inventory(data):
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        return {
            item.name: {
                "sha256": digest(archive.extractfile(item).read()),
                "bytes": item.size,
                "uid": item.uid,
                "gid": item.gid,
                "mode": oct(item.mode),
            }
            for item in archive.getmembers()
            if item.isfile()
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--serial", default="emulator-5554")
    parser.add_argument(
        "--adb",
        type=Path,
        default=Path("/Users/antonborodin/Library/Android/sdk/platform-tools/adb"),
    )
    args = parser.parse_args()
    folder = args.output.resolve()
    folder.mkdir(parents=True, mode=0o700, exist_ok=False)
    folder.chmod(0o700)
    private = folder / "private"
    private.mkdir(mode=0o700)
    commands = []

    def run(*command, save=None):
        result = subprocess.run(
            [str(args.adb), "-s", args.serial, *command],
            check=False,
            capture_output=True,
            timeout=90,
        )
        entry = {
            "command": shlex.join(["adb", "-s", args.serial, *command]),
            "exit_code": result.returncode,
            "stdout_bytes": len(result.stdout),
            "stdout_sha256": digest(result.stdout),
        }
        if save is not None:
            destination = private / save
            destination.write_bytes(result.stdout)
            destination.chmod(0o600)
            entry["private_stdout"] = save
        commands.append(entry)
        if result.returncode:
            raise RuntimeError(
                f"adb command failed: {entry['command']}; {result.stderr.decode(errors='replace')}"
            )
        return result.stdout

    try:
        assert run("emu", "avd", "name").decode().splitlines()[0] == "unciv_api34"
        package = run("shell", "dumpsys", "package", PACKAGE, save="package.txt")
        assert b"versionCode=1271045 " in package
        assert b"DEBUGGABLE" in package
        paths = run("shell", "pm", "path", PACKAGE).decode().splitlines()
        assert len(paths) == 1 and paths[0].startswith("package:/data/app/")
        apk_path = paths[0].removeprefix("package:")
        apk = run("exec-out", "cat", apk_path, save="com.unciv.app_1271045.apk")
        assert digest(apk) == EXPECTED_APK
        assert run("shell", "sha256sum", apk_path).decode().split()[0] == digest(apk)
        run("shell", "run-as", PACKAGE, "id", save="run-as.txt")
        # Runtime stop only: no launch, install, settings/save write or root.
        run("shell", "am", "force-stop", PACKAGE)
        settings = run(
            "exec-out",
            "run-as",
            PACKAGE,
            "cat",
            f"{INTERNAL}/GameSettings.json",
            save="GameSettings.json",
        )
        assert isinstance(json.loads(settings), dict)
        settings_stat = (
            run(
                "shell",
                "run-as",
                PACKAGE,
                "stat",
                "-c",
                "%u:%g:%a:%s",
                f"{INTERNAL}/GameSettings.json",
            )
            .decode()
            .strip()
        )
        assert (
            run("exec-out", "run-as", PACKAGE, "cat", f"{INTERNAL}/GameSettings.json")
            == settings
        )
        archives = {}
        for label, directory, prefix in (
            ("internal", INTERNAL, ("run-as", PACKAGE)),
            ("external", EXTERNAL, ()),
        ):
            data = run(
                "exec-out",
                *prefix,
                "tar",
                "-C",
                directory,
                "-cf",
                "-",
                ".",
                save=f"{label}-files.tar",
            )
            files = inventory(data)
            again = inventory(
                run("exec-out", *prefix, "tar", "-C", directory, "-cf", "-", ".")
            )
            assert again == files, f"{label} backup independent readback differs"
            archives[label] = {"archive_sha256": digest(data), "files": files}
        assert archives["internal"]["files"]["./GameSettings.json"]["sha256"] == digest(
            settings
        )
        save = archives["external"]["files"]["./SaveFiles/issue-8-pair"]["sha256"]
        assert (
            save == "9d2a4cd5e1de2b2ae9102a2e6e6d15210e32ae5188c895f84e8a3a6ce19c3b4e"
        )
        manifest = {
            "apk_sha256": digest(apk),
            "version_code": "1271045",
            "settings_sha256": digest(settings),
            "settings_stat": settings_stat,
            "archives": archives,
            "app_data_writes": 0,
            "installs": 0,
            "root_used": False,
            "app_left_stopped": True,
        }
        (private / "backup-manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n"
        )
        (private / "backup-manifest.json").chmod(0o600)
        public = {
            "status": "verified",
            "version_code": "1271045",
            "apk_sha256": digest(apk),
            "settings_sha256": digest(settings),
            "settings_stat": settings_stat,
            "internal_file_count": len(archives["internal"]["files"]),
            "external_file_count": len(archives["external"]["files"]),
            "app_data_writes": 0,
            "installs": 0,
            "root_used": False,
            "readback": "independent bytes/settings and per-file SHA-256/metadata for both archives",
            "private_backup_retained": True,
            "app_left_stopped": True,
        }
        (folder / "backup-summary.json").write_text(json.dumps(public, indent=2) + "\n")
        print(json.dumps(public, indent=2))
    finally:
        (folder / "backup-commands.json").write_text(
            json.dumps(commands, indent=2) + "\n"
        )
        # Private material remains private even on a failed assertion.
        for path in private.iterdir():
            if path.is_file():
                os.chmod(path, 0o600)


if __name__ == "__main__":
    main()
