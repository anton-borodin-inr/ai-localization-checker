"""D055 durable app-data reads. Raw bytes stay private, including failed reads."""

import hashlib
import io
import json
import re
import shlex
import stat
import tarfile
import time
from pathlib import Path

from l10n_checker.capture import (
    PACKAGE,
    CaptureError,
    failure_details,
    preserve_cleanup,
    retain_cleanup,
)
from l10n_checker.screen_manifest import digest


def require(condition, message):
    if not condition:
        raise CaptureError(message)


READ_LIMIT_S = 300


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def write_receipt(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.chmod(0o600)
    temporary.replace(path)


def validate_tar(raw):
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as archive:
        members = archive.getmembers()
        if (
            not members
            or len(raw) % 512
            or len(raw) < archive.offset + 1024
            or any(raw[archive.offset :])
        ):
            raise CaptureError("Empty, incomplete or malformed app-data archive")
        seen = set()
        for member in members:
            name = str(Path(member.name))
            if Path(name).is_absolute() or ".." in Path(name).parts or name in seen:
                raise CaptureError("Unsafe or duplicate app-data member")
            seen.add(name)
            if not (member.isfile() or member.isdir() or member.issym()):
                raise CaptureError("Unsupported app-data member type")
            if member.isfile():
                stream = archive.extractfile(member)
                if stream is None or len(stream.read()) != member.size:
                    raise CaptureError("Incomplete app-data archive")


def binary_failure(exc):
    raw = b""
    current = exc
    while current is not None:
        current.app_data_binary_stdout = True
        output = getattr(current, "stdout", None)
        if isinstance(output, bytes) and len(output) > len(raw):
            raw = output
        current = current.__cause__
    return raw


def observed_read(
    device,
    command,
    root,
    path,
    purpose,
    folder,
    *,
    kind="tar",
    expected_bytes=None,
    file_metadata=None,
    validate=None,
):
    try:
        return _observed_read(
            device,
            command,
            root,
            path,
            purpose,
            folder,
            kind=kind,
            expected_bytes=expected_bytes,
            file_metadata=file_metadata,
            validate=validate,
        )
    except BaseException as exc:
        exc.app_data_read_failure = True
        receipts = sorted(Path(folder).glob("[0-9][0-9][0-9][0-9][0-9][0-9].json"))
        if receipts:
            exc.app_data_read_receipt = str(receipts[-1])
        raise


def _observed_read(
    device,
    command,
    root,
    path,
    purpose,
    folder,
    *,
    kind="tar",
    expected_bytes=None,
    file_metadata=None,
    validate=None,
):
    folder = Path(folder)
    if any(p.is_symlink() for p in (folder, *folder.parents)):
        raise CaptureError("Symlink read evidence path")
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    number = 1
    while (folder / f"{number:06d}.json").exists():
        number += 1
    target = folder / f"{number:06d}.json"
    receipt = {
        "version": 1,
        "decision": "D055",
        "root": root,
        "path": path,
        "purpose": purpose,
        "kind": kind,
        "command": list(command),
        "limit_s": READ_LIMIT_S,
        "outcome": "attempted",
        "validated": False,
        "expected_bytes": expected_bytes,
    }
    write_receipt(target, receipt)
    attempts_path = folder.with_name(folder.name + "-attempts.json")
    attempts = (
        json.loads(host_bytes(attempts_path))
        if attempts_path.exists()
        else {
            "version": 1,
            "decision": "D055",
            "outcome": "attempted",
            "attempts": [],
        }
    )
    require(
        len(attempts["attempts"]) == number - 1,
        "Read attempt journal sequence mismatch",
    )
    attempts["attempts"].append(
        {
            "receipt": target.name,
            **{
                key: receipt[key]
                for key in ("root", "path", "purpose", "kind", "command", "limit_s")
            },
        }
    )
    write_receipt(attempts_path, attempts)
    raw = b""
    start = time.monotonic_ns()
    end = start

    def finish():
        duration = (end - start) / 1_000_000_000
        require(duration >= 0, "Invalid monotonic read duration")
        raw_path = target.with_suffix(".bin")
        with raw_path.open("xb") as stream:
            stream.write(raw)
        raw_path.chmod(0o600)
        require(
            host_bytes(raw_path) == raw, "Read telemetry raw host retention mismatch"
        )
        receipt.update(
            start_monotonic_ns=start,
            end_monotonic_ns=end,
            bytes=len(raw),
            duration_s=duration,
            bytes_per_second=len(raw) / duration if duration else None,
            over_60s=duration > 60,
            raw=raw_path.name,
            sha256=sha256(raw),
        )
        write_receipt(target, receipt)

    with preserve_cleanup(finish, "Read telemetry persistence"):
        try:
            if file_metadata is not None:
                metadata = file_metadata()
                receipt["metadata"] = metadata
                require(
                    isinstance(metadata, str)
                    and re.fullmatch(r"[0-9]+ [0-9]+ [0-7]+ [0-9]+", metadata)
                    is not None,
                    "Settings metadata unavailable or invalid before readback",
                )
                expected_bytes = int(metadata.split()[-1])
                receipt["expected_bytes"] = expected_bytes
            raw = device.run(*command, timeout_s=READ_LIMIT_S)
            end = time.monotonic_ns()
            if kind == "tar":
                validate_tar(raw)
            if expected_bytes is not None:
                require(len(raw) == expected_bytes, "Incomplete app-data file read")
            if validate is not None:
                validate(raw)
            receipt.update(outcome="complete", validated=True)
            return raw
        except BaseException as exc:
            end = time.monotonic_ns()
            exc.app_data_read = {
                "receipt": str(target),
                "root": root,
                "path": path,
                "purpose": purpose,
            }
            partial = binary_failure(exc)
            if partial:
                raw = partial
            receipt.update(outcome="failed", error_details=failure_details(exc))
            raise


def read_tar(device, path, root, purpose, folder):
    return observed_read(
        device,
        ("exec-out", "tar", "-cf", "-", "-C", path, "."),
        root,
        path,
        purpose,
        folder,
    )


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
        "decision": "D-056",
        "version": 2,
        "regular_file_paths": list(ANDROIDX_BOOKKEEPING),
        "allowed_changes": ["bytes", "sha256", "presence", "uid", "gid", "mode"],
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
                or {
                    k: v
                    for k, v in old.items()
                    if k not in {"bytes", "sha256", "uid", "gid", "mode"}
                }
                == {
                    k: v
                    for k, v in new.items()
                    if k not in {"bytes", "sha256", "uid", "gid", "mode"}
                }
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
        validate_tar(raw)
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


def package_data(device, folder, purpose):
    """Complete rooted inventory read; caller owns root/unroot and writer stop."""
    require(not device.pid(), "App running during data backup")
    archives = {}
    for root, path in DATA_ROOTS.items():
        present = device.shell(
            "if [ -d " + shlex.quote(path) + " ]; then printf present; fi"
        ).strip()
        if present == "present":
            archives[root] = read_tar(
                device, path, root, purpose, Path(folder) / "reads"
            )
    require(
        {"private", "external"} <= set(archives),
        "Required package app-data roots absent",
    )
    return archives


def snapshot(device, folder, purpose):
    archives = package_data(device, folder, purpose)
    inventory = data_inventory(archives)
    write_receipt(Path(folder) / (purpose + "-inventory.json"), inventory)
    return inventory


def cleanup_policy():
    return {
        "decision": "D055",
        "version": 1,
        "read_limit_s": 300,
        "strict_post_cleanup": "D-051-only",
        "authority": "exact-plan-new-host-rehashed",
        "writer_boundary": "force-stopped-package-and-exclusive-device-operator",
    }


def hook_paths(outputs):
    paths = [o[key] for o in outputs for key in ("file", "temporary")]
    require(len(paths) == len(set(paths)), "Duplicate hook cleanup path")
    for path in paths:
        require(
            type(path) is str
            and re.fullmatch(
                r"files/l10n-hook/i47-[a-f0-9]{32}-[12]-[0-9]+-[0-9]+\.json(?:\.tmp)?",
                path,
            ),
            "Unsafe hook cleanup path",
        )
    return paths


def identity_script(relative=None):
    paths = [
        DATA_ROOTS["private"],
        DATA_ROOTS["private"] + "/files",
        DATA_ROOTS["private"] + "/files/l10n-hook",
    ]
    if relative is not None:
        hook_paths(
            [
                {
                    "file": relative.removesuffix(".tmp"),
                    "temporary": relative.removesuffix(".tmp") + ".tmp",
                }
            ]
        )
        paths.append(DATA_ROOTS["private"] + "/" + relative)
    script = "set -eu\n# D055 identity\n"
    for path in paths:
        size = "%s" if relative is not None and path == paths[-1] else "0"
        script += f"test ! -L {shlex.quote(path)}\nstat -c '%d %i %h %f %u %g {size}' {shlex.quote(path)}\n"
    return script


def device_identity(device, relative=None):
    lines = device.shell(identity_script(relative)).strip().splitlines()
    require(len(lines) == (4 if relative else 3), "Missing private path identity")
    values = []
    for i, line in enumerate(lines):
        parts = line.split()
        require(
            len(parts) == 7 and all(re.fullmatch(r"[0-9a-fA-F]+", p) for p in parts),
            "Invalid private path identity",
        )
        values.append(line)
        mode = int(parts[3], 16)
        require(
            stat.S_ISDIR(mode) if i < 3 else stat.S_ISREG(mode),
            "Unsafe private path type",
        )
        if i == 3:
            require(int(parts[2]) == 1, "Hard-linked hook output")
    return values


def preflight_outputs(device, outputs, inventory):
    paths = hook_paths(outputs)
    require(
        all("private:" + p not in inventory for p in paths),
        "Prepared hook output already exists",
    )
    require(
        all(
            inventory.get("private:" + p, {}).get("type") == "directory"
            for p in (".", "files", "files/l10n-hook")
        ),
        "Existing regular hook directory required; no directory creation authorized",
    )
    return device_identity(device)


def quiesce(device):
    device.force_stop()
    require(not device.pid(), "Hook writer still running")
    stopped = device.shell("dumpsys", "package", PACKAGE)
    require(
        re.search(r"User 0:.*\bstopped=true\b", stopped) is not None,
        "Cannot prove force-stopped package writer boundary",
    )
    return {"force_stopped": True, "pid": "", "package_stopped": True}


def unlink_command(path, identity, checksum):
    """One guarded shell operation inside the force-stopped writer boundary.

    The operator must exclusively own the device (the mutation runner also holds
    its device lock). Hostile concurrent root/ADB operators are outside this
    boundary; no separate unguarded rm is ever issued.
    """
    hook_paths(
        [
            {
                "file": path.removesuffix(".tmp"),
                "temporary": path.removesuffix(".tmp") + ".tmp",
            }
        ]
    )
    absolute = DATA_ROOTS["private"] + "/" + path
    script = "set -eu\n# D055 guarded unlink\n"
    script += f'test -z "$(pidof {PACKAGE} || true)"\n'
    script += f"dumpsys package {PACKAGE} | grep -q 'User 0:.*stopped=true'\n"
    # Read and compare the whole ancestor/leaf identity in this same operation.
    script += "observed=$(\n" + identity_script(path) + ")\n"
    script += 'test "$observed" = ' + shlex.quote("\n".join(identity)) + "\n"
    script += f'test "$(sha256sum {shlex.quote(absolute)})" = {shlex.quote(checksum + "  " + absolute)}\n'
    script += f"rm -- {shlex.quote(absolute)}\ntest ! -e {shlex.quote(absolute)}\ntest ! -L {shlex.quote(absolute)}\nprintf 'D055-deleted\\n'\n"
    return script


def unlink_verified(device, path, identity, checksum):
    script = unlink_command(path, identity, checksum)
    require(
        device.shell(script).strip() == "D055-deleted",
        "Guarded hook unlink did not verify",
    )
    return script


def host_bytes(path):
    path = Path(path)
    require(
        not any(p.is_symlink() for p in (path, *path.parents)),
        "Aliased cleanup host proof",
    )
    before = path.stat()
    require(
        stat.S_ISREG(before.st_mode) and before.st_nlink == 1,
        "Unsafe cleanup host proof type/link",
    )
    raw = path.read_bytes()
    after = path.stat()
    require(
        (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
        )
        == (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        ),
        "Cleanup host proof changed during read",
    )
    return raw


def cleanup_outputs(device, outputs, starting, directory_identity, folder, records):
    folder = Path(folder)
    proof = {
        "policy": cleanup_policy(),
        "status": "attempted",
        "starting": starting,
        "directory_identity": directory_identity,
        "paths": [
            {"path": path, "status": "unavailable"} for path in hook_paths(outputs)
        ],
    }
    target = folder / "hook-cleanup.json"
    write_receipt(target, proof)
    post_attempted = False
    try:
        proof["quiescence"] = quiesce(device)
        require(
            device_identity(device) == directory_identity,
            "Hook directory identity changed",
        )
        before = snapshot(device, folder, "before-cleanup")
        proof["before"] = before
        mapped = {
            r["readiness"]["dump"]["file"]: r["dump"] for r in records if r.get("dump")
        }
        # Authenticate the ENTIRE present set before the first unlink.
        for entry in proof["paths"]:
            path = entry["path"]
            require(
                "private:" + path not in starting,
                "Existing hook output cannot be cleanup authority",
            )
            value = before.get("private:" + path)
            if value is None:
                entry["status"] = "absent"
                continue
            require(value["type"] == "file", "Nonregular hook output")
            identity = device_identity(device, path)
            require(
                identity[:3] == directory_identity, "Hook ancestor identity changed"
            )
            if path in mapped:
                host = folder / mapped[path]
                raw = host_bytes(host)
            else:
                read_folder = folder / "cleanup-pulls"
                observed_read(
                    device,
                    ("exec-out", "cat", DATA_ROOTS["private"] + "/" + path),
                    "private",
                    path,
                    "hook-output-cleanup-pull",
                    read_folder,
                    kind="file",
                    expected_bytes=value["bytes"],
                )
                host = max(read_folder.glob("*.bin"))
                raw = host_bytes(host)
            require(
                len(raw) == value["bytes"] and sha256(raw) == value["sha256"],
                "Cleanup host hash readback mismatch",
            )
            require(
                device_identity(device, path) == identity,
                "Hook output identity changed during pull",
            )
            entry.update(
                status="verified",
                identity=identity,
                host=str(host.relative_to(folder)),
                bytes=len(raw),
                sha256=sha256(raw),
            )
        write_receipt(target, proof)
        for entry in proof["paths"]:
            if entry["status"] != "verified":
                continue
            # Actual host re-read barrier also catches replacement after proof publication.
            raw = host_bytes(folder / entry["host"])
            require(
                len(raw) == entry["bytes"] and sha256(raw) == entry["sha256"],
                "Cleanup host proof changed",
            )
        for entry in proof["paths"]:
            if entry["status"] != "verified":
                continue
            entry["status"] = "attempted"
            entry["command"] = unlink_command(
                entry["path"], entry["identity"], entry["sha256"]
            )
            write_receipt(target, proof)
            try:
                unlink_verified(
                    device, entry["path"], entry["identity"], entry["sha256"]
                )
            except BaseException as exc:
                entry["status"] = "failed"
                entry["error_details"] = failure_details(exc)
                with preserve_cleanup(
                    lambda: write_receipt(target, proof), "Failed path evidence"
                ):
                    raise
            entry["status"] = "deleted"
            write_receipt(target, proof)
        post_attempted = True
        proof["after"] = snapshot(device, folder, "post-cleanup")
        proof["preservation"] = preservation_report(starting, proof["after"])
        require(
            not proof["preservation"]["unexpected_changes"],
            "Strict post-cleanup app-data preservation failed",
        )
        proof["status"] = "verified"
        write_receipt(target, proof)
        return proof
    except BaseException as exc:
        proof["status"] = "failed"
        if not post_attempted:
            try:
                proof["after"] = snapshot(device, folder, "post-cleanup")
                proof["preservation"] = preservation_report(starting, proof["after"])
            except BaseException as post_error:  # noqa: BLE001 - retain cancellation with primary
                retain_cleanup(exc, post_error, "Post-cleanup inventory")
        proof["error_details"] = failure_details(exc)
        try:
            write_receipt(target, proof)
        except BaseException as persistence_error:  # noqa: BLE001 - preserve primary
            retain_cleanup(exc, persistence_error, "Cleanup receipt persistence")
        raise


def inventory_changes(before, after, allowed_new=()):
    """Only declared new hook outputs are exempt; existing data stays exact."""
    excluded = set(allowed_new) - set(before)
    return [
        {"path": name, "before": before.get(name), "after": after.get(name)}
        for name in sorted(set(before) | set(after))
        if name not in excluded and before.get(name) != after.get(name)
    ]
