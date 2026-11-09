"""Device transaction safety; all APK bytes and device responses here are synthetic."""

import importlib
import importlib.util
import io
import tarfile

import pytest

from l10n_checker.capture import CaptureError
from l10n_checker.screen_manifest import digest


@pytest.fixture(autouse=True)
def forbid_unstubbed_native_commands(monkeypatch):
    import subprocess

    def forbidden(*args, **kwargs):
        pytest.fail("Unstubbed native command forbidden in host-only mutation tests")

    monkeypatch.setattr(subprocess, "run", forbidden)


def api():
    assert importlib.util.find_spec("l10n_checker.mutation_device") is not None, (
        "Safe install orchestration missing"
    )
    return importlib.import_module("l10n_checker.mutation_device")


def archive(value=b"save", mode=0o600):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w") as tar:
        item = tarfile.TarInfo("./save")
        item.size = len(value)
        item.mode = mode
        item.uid = item.gid = 10001
        tar.addfile(item, io.BytesIO(value))
    return stream.getvalue()


def test_backup_inventory_binds_bytes_ownership_and_modes():
    before = api().data_inventory({"private": archive()})
    assert before != api().data_inventory({"private": archive(b"changed")})
    assert before != api().data_inventory({"private": archive(mode=0o644)})
    assert before == api().data_inventory({"private": archive()})


class Device:
    def __init__(self):
        self.calls = []

    def run(self, *args):
        self.calls.append(args)
        assert args[:3] == ("install", "-r", "-d")
        return b"Performing Streamed Install\nSuccess\n"

    def force_stop(self):
        self.calls.append(("stop",))

    def pid(self):
        return ""


def transaction(tmp_path, monkeypatch):
    device = Device()
    path = tmp_path / "artifact.apk"
    path.write_bytes(b"synthetic APK")
    build = {"version_code": "1800000001", "apk_sha256": digest(path.read_bytes())}
    monkeypatch.setattr(
        api(),
        "read_app_data",
        lambda device, *, evidence_dir, purpose: {"private": archive()},
    )
    monkeypatch.setattr(
        api(),
        "installed_identity",
        lambda *args, **kwargs: {**build, "certificate_sha256": "a" * 64},
    )
    checks = []
    return device, path, build, checks


def test_d055_install_supplies_durable_scope_for_all_reads(tmp_path, monkeypatch):
    reader = api().read_app_data
    device, path, build, _checks = transaction(tmp_path, monkeypatch)
    monkeypatch.setattr(api(), "read_app_data", reader)
    device.root = device.unroot = lambda: None
    device.shell = lambda *args: "present"
    calls = []

    def native(*args, timeout_s=30):
        if args[:2] == ("exec-out", "tar"):
            calls.append(timeout_s)
            return archive()
        assert args[:3] == ("install", "-r", "-d")
        return b"Success\n"

    device.run = native
    error = None
    try:
        result = api().install_verified(
            device,
            path,
            build,
            "a" * 64,
            tools=None,
            folder=tmp_path / "tx",
            environment=lambda build: None,
        )
    except CaptureError as exc:
        error = str(exc)
    assert error is None, f"Install lost required per-read evidence scope: {error}"
    assert result["status"] == "verified"
    from l10n_checker.screen_manifest import json_bytes

    receipts = [
        json_bytes(p.read_bytes()) for p in (tmp_path / "tx/reads").glob("*.json")
    ]
    assert len(receipts) == len(calls) == 9
    assert calls == [300] * 9
    assert {r["purpose"] for r in receipts} == {
        "install-before",
        "install-readback",
        "install-after",
    }


def test_install_always_uses_r_d_and_environment_check(tmp_path, monkeypatch):
    device, path, build, checks = transaction(tmp_path, monkeypatch)
    result = api().install_verified(
        device,
        path,
        build,
        "a" * 64,
        tools=None,
        folder=tmp_path / "tx",
        environment=lambda build: checks.append(build["version_code"]),
    )
    assert ("install", "-r", "-d", str(path)) in device.calls
    assert checks == ["1800000001"]
    assert result["app_data_preserved"] is True


def test_incomplete_backup_prevents_install(tmp_path, monkeypatch):
    device, path, build, _checks = transaction(tmp_path, monkeypatch)
    monkeypatch.setattr(
        api(),
        "read_app_data",
        lambda device, *, evidence_dir, purpose: (_ for _ in ()).throw(
            CaptureError("backup failed")
        ),
    )
    with pytest.raises(CaptureError, match="backup"):
        api().install_verified(
            device,
            path,
            build,
            "a" * 64,
            tools=None,
            folder=tmp_path / "tx",
            environment=lambda build: None,
        )
    assert not any(call[0] == "install" for call in device.calls)


def test_data_loss_stops_without_repair_or_uninstall(tmp_path, monkeypatch):
    device, path, build, _checks = transaction(tmp_path, monkeypatch)
    snapshots = iter(
        [{"private": archive()}, {"private": archive()}, {"private": archive(b"LOST")}]
    )
    monkeypatch.setattr(
        api(), "read_app_data", lambda device, *, evidence_dir, purpose: next(snapshots)
    )
    with pytest.raises(CaptureError, match="preserv"):
        api().install_verified(
            device,
            path,
            build,
            "a" * 64,
            tools=None,
            folder=tmp_path / "tx",
            environment=lambda build: None,
        )
    assert not any(call[0] in {"uninstall", "clear"} for call in device.calls)


def test_certificate_mismatch_stops_before_install(tmp_path, monkeypatch):
    device, path, build, _checks = transaction(tmp_path, monkeypatch)
    monkeypatch.setattr(
        api(),
        "installed_identity",
        lambda *args, **kwargs: {**build, "certificate_sha256": "b" * 64},
    )
    with pytest.raises(CaptureError, match="certificate"):
        api().install_verified(
            device,
            path,
            build,
            "a" * 64,
            tools=None,
            folder=tmp_path / "tx",
            environment=lambda build: None,
        )
    assert not any(call[0] == "install" for call in device.calls)


def test_environment_failure_is_not_ignored(tmp_path, monkeypatch):
    device, path, build, _checks = transaction(tmp_path, monkeypatch)

    def fail(build):
        raise CaptureError("environment check failed")

    with pytest.raises(CaptureError, match="environment"):
        api().install_verified(
            device,
            path,
            build,
            "a" * 64,
            tools=None,
            folder=tmp_path / "tx",
            environment=fail,
        )


def test_calibration_failure_never_starts_production_and_always_restores():
    assert hasattr(api(), "execute_stages"), "Calibration sequencing missing"
    events = []

    def capture(role):
        events.append(role)
        return {"passed": role != "calibration"}

    with pytest.raises(CaptureError, match="calibration"):
        api().execute_stages(
            lambda: capture("control"),
            lambda: capture("calibration"),
            [lambda: capture("production")],
            lambda: events.append("restore"),
        )
    assert events == ["control", "calibration", "restore"]


def test_all_three_production_stages_follow_successful_calibration():
    assert hasattr(api(), "execute_stages"), "Production sequencing missing"
    events = []

    def capture(role):
        events.append(role)
        return {"passed": True}

    api().execute_stages(
        lambda: capture("control"),
        lambda: capture("calibration"),
        [lambda r=r: capture(r) for r in ("one", "two", "three")],
        lambda: events.append("restore"),
    )
    assert events == ["control", "calibration", "one", "two", "three", "restore"]


def test_restoration_error_does_not_replace_original_failure():
    def control():
        raise CaptureError("unexpected capture app-data drift")

    def restore():
        raise CaptureError("strict restoration data mismatch")

    with pytest.raises(
        CaptureError, match="unexpected capture app-data drift"
    ) as error:
        api().execute_stages(control, lambda: None, [], restore)
    assert any("restoration" in note for note in error.value.__notes__)


def test_failed_final_verification_does_not_reinstall_reference_twice(
    tmp_path, monkeypatch
):
    import l10n_checker.mutation_run as runtime
    from l10n_checker.mutation_run import MutationRun

    run = object.__new__(MutationRun)
    run.restored = False
    run.restore_error = None
    run.restore_attempted = False
    run.needs_restore = True
    run.folder = tmp_path
    run.device = run.tools = None
    run.reference = dict
    calls = []
    run.install = lambda record: calls.append(record)

    def failed_readback(*args):
        raise CaptureError("final app-data readback failed")

    monkeypatch.setattr(runtime, "installed_identity", failed_readback)
    for _ in range(2):
        with pytest.raises(CaptureError):
            run.restore()
    assert len(calls) == 1


def test_runtime_bookkeeping_is_not_silently_exempted_from_preservation():
    assert hasattr(api(), "inventory_changes"), (
        "Explicit capture drift diagnostics missing"
    )
    before = {
        "private:files/profileInstalled": {"sha256": "a"},
        "private:files/l10n-hook/old.json": {"sha256": "a"},
    }
    after = {
        "private:files/profileInstalled": {"sha256": "b"},
        "private:files/l10n-hook/old.json": {"sha256": "b"},
        "private:files/l10n-hook/new.json": {"sha256": "c"},
    }
    changes = api().inventory_changes(
        before, after, set(after) - {"private:files/profileInstalled"}
    )
    assert [item["path"] for item in changes] == [
        "private:files/l10n-hook/old.json",
        "private:files/profileInstalled",
    ]


BOOKKEEPING = (
    "files/profileInstalled",
    "no_backup/androidx.work.workdb",
    "no_backup/androidx.work.workdb-shm",
    "no_backup/androidx.work.workdb-wal",
)


def file_entry(raw=b"before", **metadata):
    return {
        "type": "file",
        "uid": 10001,
        "gid": 10001,
        "mode": 0o600,
        "bytes": len(raw),
        "sha256": digest(raw),
        **metadata,
    }


@pytest.mark.parametrize(
    "change",
    [
        {"uid": 10002},
        {"gid": 10002},
        {"mode": 0o644},
        {"type": "directory"},
        {"type": "symlink", "target": "elsewhere"},
    ],
)
def test_d051_never_exempts_metadata_or_nonregular_files(change):
    name = "private:" + BOOKKEEPING[0]
    before = {name: file_entry()}
    after = {name: file_entry(b"changed", **change)}
    raw = api().inventory_changes(before, after)
    assert api().preservation_report(before, after)["unexpected_changes"] == raw
    assert api().preservation_report(before, after)["exempt_changes"] == []
    if change.get("type") in {"directory", "symlink"}:
        assert api().preservation_report({}, after)["unexpected_changes"]
        assert api().preservation_report(after, {})["unexpected_changes"]


def bookkeeping_archive(value, mode=0o600, present=True):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w") as tar:
        for name, raw in {
            "files/GameSettings.json": b"exact settings",
            **{path: value for path in BOOKKEEPING if present},
        }.items():
            item = tarfile.TarInfo("./" + name)
            item.size, item.uid, item.gid = len(raw), 10001, 10001
            item.mode = mode if name in BOOKKEEPING else 0o600
            tar.addfile(item, io.BytesIO(raw))
    return stream.getvalue()


def test_d051_install_records_backup_readback_and_install_exemptions(
    tmp_path, monkeypatch
):
    from l10n_checker.screen_manifest import json_bytes

    device, path, build, _ = transaction(tmp_path, monkeypatch)
    snapshots = [
        {"private": bookkeeping_archive(raw)}
        for raw in (b"before", b"readback", b"installed")
    ]
    reads = iter(snapshots)
    monkeypatch.setattr(
        api(), "read_app_data", lambda device, *, evidence_dir, purpose: next(reads)
    )
    caught = None
    try:
        api().install_verified(
            device,
            path,
            build,
            "a" * 64,
            tools=None,
            folder=tmp_path / "tx",
            environment=lambda build: None,
        )
    except CaptureError as exc:
        caught = exc
    assert caught is None, f"Authorized bookkeeping drift stopped install: {caught}"
    result = json_bytes((tmp_path / "tx/install.json").read_bytes())
    before, readback, after = [api().data_inventory(s) for s in snapshots]
    assert result["preservation_policy"] == api().preservation_policy()
    assert result["backup_readback_preservation"] == api().preservation_report(
        before, readback
    )
    assert result["preservation"] == api().preservation_report(before, after)
    assert result["data_changes"] == api().inventory_changes(before, after)
    assert len(result["data_changes"]) == 4 and result["app_data_preserved"] is True
    assert device.calls == [("stop",), ("install", "-r", "-d", str(path))]


def test_d051_reports_all_four_files_without_hiding_raw_deltas():
    assert hasattr(api(), "preservation_report"), "D-051 comparison ledger missing"
    before = {"private:" + path: file_entry() for path in BOOKKEEPING[:3]}
    after = {"private:" + path: file_entry(b"after") for path in BOOKKEEPING[:2]}
    after["private:" + BOOKKEEPING[3]] = file_entry(b"new WAL")
    report = api().preservation_report(before, after)
    raw = api().inventory_changes(before, after)
    assert report["unexpected_changes"] == []
    assert report["exempt_changes"] == raw and len(raw) == 4
    assert report["bookkeeping"] == [
        {
            "path": "private:" + path,
            "before": before.get("private:" + path),
            "after": after.get("private:" + path),
        }
        for path in BOOKKEEPING
    ]
    assert report["policy"]["decision"] == "D-051"
    empty = api().preservation_report({}, {})
    assert all(r["before"] is None and r["after"] is None for r in empty["bookkeeping"])
    assert empty["exempt_changes"] == empty["unexpected_changes"] == []


def test_d051_metadata_of_file_created_at_readback_stays_strict(tmp_path, monkeypatch):
    from l10n_checker.screen_manifest import json_bytes

    device, path, build, _ = transaction(tmp_path, monkeypatch)
    snapshots = iter(
        [
            {"private": raw}
            for raw in (
                bookkeeping_archive(b"before", present=False),
                bookkeeping_archive(b"readback"),
                bookkeeping_archive(b"after", mode=0o644),
            )
        ]
    )
    monkeypatch.setattr(
        api(), "read_app_data", lambda device, *, evidence_dir, purpose: next(snapshots)
    )
    rejected = False
    try:
        api().install_verified(
            device,
            path,
            build,
            "a" * 64,
            tools=None,
            folder=tmp_path / "tx",
            environment=lambda build: None,
        )
    except CaptureError:
        rejected = True
    assert rejected, "Creation must not conceal metadata drift after the readback"
    receipt = json_bytes((tmp_path / "tx/install.json").read_bytes())
    assert receipt["post_readback_preservation"]["unexpected_changes"]


@pytest.mark.parametrize("path", BOOKKEEPING)
@pytest.mark.parametrize(
    "alias",
    [
        "external:{}",
        "device_encrypted:{}",
        "private:{}.tmp",
        "private:{}/child",
        "private:prefix/{}",
    ],
)
def test_d051_path_exception_is_exact_and_private_only(path, alias):
    name = alias.format(path)
    before, after = {name: file_entry()}, {name: file_entry(b"changed")}
    report = api().preservation_report(before, after)
    assert report["unexpected_changes"] == api().inventory_changes(before, after)
    assert report["exempt_changes"] == []


def test_d051_keeps_declared_new_hook_output_semantics():
    old, new = "private:files/l10n-hook/old.json", "private:files/l10n-hook/new.json"
    before = {old: file_entry()}
    after = {old: file_entry(b"changed"), new: file_entry(b"new")}
    report = api().preservation_report(before, after, {old, new})
    assert report["unexpected_changes"] == api().inventory_changes(
        before, after, {old, new}
    )
    assert [c["path"] for c in report["unexpected_changes"]] == [old]
    assert report["exempt_changes"] == []


@pytest.mark.parametrize("phase", ["preparing", "install", "environment"])
def test_native_install_timeout_is_journaled_with_available_output(
    tmp_path, monkeypatch, phase
):
    import subprocess

    from l10n_checker.screen_manifest import json_bytes

    device, path, build, _ = transaction(tmp_path, monkeypatch)
    error = subprocess.TimeoutExpired(
        "synthetic-native-command",
        1,
        output=b"partial stdout",
        stderr=b"partial stderr",
    )

    def timeout(*args, **kwargs):
        raise error

    environment = timeout if phase == "environment" else lambda build: None
    if phase == "preparing":
        device.force_stop = timeout
    elif phase == "install":
        device.run = timeout
    with pytest.raises(subprocess.TimeoutExpired) as caught:
        api().install_verified(
            device,
            path,
            build,
            "a" * 64,
            tools=None,
            folder=tmp_path / "tx",
            environment=environment,
        )
    assert caught.value is error
    receipt = json_bytes((tmp_path / "tx/install.json").read_bytes())
    assert receipt["status"] == "failed"
    assert receipt["error_details"]["type"] == "TimeoutExpired"
    assert receipt["error_details"]["stdout"] == "partial stdout"
    assert receipt["error_details"]["stderr"] == "partial stderr"


def test_native_environment_timeout_retains_receipt_and_output(tmp_path, monkeypatch):
    import subprocess

    from l10n_checker.screen_manifest import json_bytes

    error = subprocess.TimeoutExpired("synthetic-check-env", 180, b"out", b"err")

    def timeout(*args, **kwargs):
        raise error

    monkeypatch.setattr(api().subprocess, "run", timeout)
    with pytest.raises(subprocess.TimeoutExpired) as caught:
        api().environment_check({"version_code": "1271048"}, tmp_path / "env")
    assert caught.value is error
    receipt = json_bytes((tmp_path / "env/receipt.json").read_bytes())
    assert (
        receipt["exit_code"] is None
        and receipt["error_details"]["type"] == "TimeoutExpired"
    )
    assert (tmp_path / "env/stdout.txt").read_bytes() == b"out"
    assert (tmp_path / "env/stderr.txt").read_bytes() == b"err"


@pytest.mark.parametrize("cleanup_type", ["timeout", "subprocess"])
def test_native_cleanup_failure_preserves_original_exception(cleanup_type):
    import subprocess

    original = CaptureError("strict four-file app-data drift")
    cleanup = (
        subprocess.TimeoutExpired(
            "synthetic-restore", 1, b"cleanup output", b"cleanup err"
        )
        if cleanup_type == "timeout"
        else subprocess.SubprocessError("synthetic cleanup")
    )

    def control():
        raise original

    def restore():
        raise cleanup

    with pytest.raises(CaptureError, match="strict four-file") as caught:
        api().execute_stages(control, lambda: None, [], restore)
    assert caught.value is original
    assert original.cleanup_errors[0]["type"] == type(cleanup).__name__
    assert "restoration" in original.__notes__[0]


def test_runtime_timeout_and_cleanup_timeout_are_separately_journaled(tmp_path):
    import subprocess

    import l10n_checker.mutation_run as runtime

    run = object.__new__(runtime.MutationRun)
    run.folder = tmp_path.resolve()
    run.content = {"status": "not_run", "capture_set_qualified": False}
    run.journal = {}
    run.checkpoint = lambda: None
    original = subprocess.TimeoutExpired(
        "synthetic-probe", 1, b"probe out", b"probe err"
    )
    cleanup = subprocess.TimeoutExpired(
        "synthetic-restore", 1, b"restore out", b"restore err"
    )

    def probe():
        raise original

    def restore():
        raise cleanup

    run.probe, run.restore = probe, restore
    result = run.run(probe_only=True)
    assert result["status"] == "restoration_failed"
    assert result["capture_set_qualified"] is False
    assert run.journal["error_details"]["stdout"] == "probe out"
    assert run.journal["restoration_error_details"]["stdout"] == "restore out"
    assert "dynamic_tests" not in result, (
        "Operational failure was classified as interference"
    )


def test_d055_normal_cancellation_and_final_cleanup_preserve_both(tmp_path):
    import l10n_checker.mutation_run as runtime

    run = object.__new__(runtime.MutationRun)
    run.folder = tmp_path
    run.content = {"status": "not_run", "capture_set_qualified": False}
    run.journal = {}
    run.checkpoint = lambda: None
    original = KeyboardInterrupt("primary cancellation")
    cleanup = KeyboardInterrupt("cleanup cancellation")

    def probe():
        raise original

    def restore():
        raise cleanup

    run.probe, run.restore = probe, restore
    with pytest.raises(KeyboardInterrupt) as caught:
        run.run(probe_only=True)
    assert caught.value is original, "Final cleanup replaced the primary cancellation"
    assert run.journal["error_details"]["type"] == "KeyboardInterrupt"
    assert run.journal["restoration_error_details"]["message"] == "cleanup cancellation"
    assert (tmp_path / "evidence-index.json").is_file()


def test_preflight_refuses_multiple_emulators_before_environment_root_check(
    monkeypatch,
):
    from types import SimpleNamespace

    monkeypatch.setattr(
        api().subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout=b""),
    )
    device = SimpleNamespace(
        serial="emulator-5554",
        connect=lambda: None,
        pid=lambda: "",
        run=lambda *args: (
            b"List of devices attached\nemulator-5554\tdevice\nemulator-5556\tdevice\n"
        ),
    )
    with pytest.raises(CaptureError, match="one emulator"):
        api().assert_idle(device)


@pytest.mark.parametrize("phase", ["root", "archive"])
@pytest.mark.parametrize("wrapped", [False, True])
def test_backup_unroot_double_failure_retains_primary_and_install_receipt(
    tmp_path, monkeypatch, phase, wrapped
):
    import subprocess
    from types import SimpleNamespace

    from l10n_checker.screen_manifest import json_bytes

    native = subprocess.TimeoutExpired(
        "synthetic-backup", 1, b"backup stdout", b"backup stderr"
    )
    original = CaptureError("backup transport failed") if wrapped else native
    if wrapped:
        original.__cause__ = native
    cleanup_native = subprocess.TimeoutExpired(
        "synthetic-unroot", 1, b"unroot stdout", b"unroot stderr"
    )
    cleanup = CaptureError("unroot transport failed")
    calls = []

    def root():
        calls.append("root")
        if phase == "root":
            raise original

    def backup(*args, timeout_s):
        assert timeout_s == 300
        calls.append("backup")
        assert args[:3] == ("exec-out", "tar", "-cf"), "Install must not start"
        raise original

    def unroot():
        calls.append("unroot")
        raise cleanup from cleanup_native

    device = SimpleNamespace(
        pid=lambda: "",
        force_stop=lambda: None,
        root=root,
        shell=lambda *args: "present",
        run=backup,
        unroot=unroot,
    )
    path = tmp_path / "synthetic.apk"
    path.write_bytes(b"synthetic APK")
    build = {"version_code": "1800000001", "apk_sha256": digest(path.read_bytes())}
    monkeypatch.setattr(
        api(),
        "installed_identity",
        lambda *args: {**build, "certificate_sha256": "a" * 64},
    )
    with pytest.raises(type(original)) as caught:
        api().install_verified(
            device,
            path,
            build,
            "a" * 64,
            tools=None,
            folder=tmp_path / "tx",
            environment=lambda build: pytest.fail("Environment must not start"),
        )
    assert caught.value is original
    assert calls == (
        ["root", "unroot"] if phase == "root" else ["root", "backup", "unroot"]
    )
    receipt = json_bytes((tmp_path / "tx/install.json").read_bytes())
    assert receipt["status"] == "failed"
    details = receipt["error_details"]
    primary = details["cause"] if wrapped else details
    assert primary["type"] == "TimeoutExpired"
    if phase == "archive":
        assert primary["stdout_bytes"] == len(b"backup stdout")
    else:
        assert primary["stdout"] == "backup stdout"
    assert primary["stderr"] == "backup stderr"
    cleanup_details = details["cleanup_errors"]
    assert len(cleanup_details) == 1
    assert cleanup_details[0]["cause"]["stdout"] == "unroot stdout"
    assert cleanup_details[0]["cause"]["stderr"] == "unroot stderr"
