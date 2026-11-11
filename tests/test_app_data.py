"""D055 host-only native-seam tests; no device or network operations."""

import importlib.util
import io
import json
import subprocess
import tarfile
from pathlib import Path

import pytest

from l10n_checker.capture import CaptureError, Device, failure_details


@pytest.fixture(autouse=True)
def forbid_native(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Native I/O must be explicitly stubbed in D055 host tests")

    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)


def api():
    assert importlib.util.find_spec("l10n_checker.app_data"), (
        "D055 durable read implementation missing"
    )
    from l10n_checker import app_data

    return app_data


def test_d055_telemetry_failure_does_not_replace_native_failure(tmp_path, monkeypatch):
    module = api()
    original = CaptureError("primary native failure")

    def native(*args, **kwargs):
        raise original

    monkeypatch.setattr(subprocess, "run", native)
    write = module.write_receipt

    def broken(path, receipt):
        if receipt.get("outcome") != "attempted":
            raise OSError("telemetry disk full")
        return write(path, receipt)

    monkeypatch.setattr(module, "write_receipt", broken)
    with pytest.raises(CaptureError) as caught:
        module.read_tar(
            Device(Path("never-real-adb")), "/synthetic", "private", "failure", tmp_path
        )
    assert caught.value is original
    assert original.cleanup_errors[0]["message"] == "telemetry disk full"


def tar_bytes():
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w") as tar:
        info = tarfile.TarInfo("./save")
        info.size = 4
        tar.addfile(info, io.BytesIO(b"save"))
    return stream.getvalue()


@pytest.mark.parametrize("wrapped", [False, True])
def test_d055_failed_read_keeps_partial_bytes_not_binary_logs(
    tmp_path, monkeypatch, wrapped
):
    module = api()
    partial = b"\x00\xffPRIVATE-TAR\x00"
    native = subprocess.TimeoutExpired("synthetic", 300, partial, b"closed")
    original = CaptureError("wrapped") if wrapped else native
    if wrapped:
        original.__cause__ = native

    def fail(*args, **kwargs):
        raise original

    monkeypatch.setattr(subprocess, "run", fail)
    with pytest.raises(CaptureError):
        module.read_tar(
            Device(Path("never-real-adb")), "/synthetic", "private", "failed", tmp_path
        )
    receipt = json.loads((tmp_path / "000001.json").read_bytes())
    assert receipt["bytes"] == len(partial)
    assert receipt["outcome"] == "failed" and receipt["validated"] is False
    assert (tmp_path / receipt["raw"]).read_bytes() == partial
    assert "PRIVATE-TAR" not in json.dumps(receipt)
    assert "PRIVATE-TAR" not in json.dumps(failure_details(original))


@pytest.mark.parametrize(
    "raw",
    [b"", b"garbage", b"\0" * 10240, tar_bytes()[:1024]],
    ids=["empty", "garbage", "empty-tar", "missing-eof"],
)
def test_d055_successful_native_exit_does_not_validate_bad_tar(
    tmp_path, monkeypatch, raw
):
    module = api()
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda command, **kw: subprocess.CompletedProcess(command, 0, stdout=raw),
    )
    with pytest.raises((CaptureError, tarfile.TarError)):
        module.read_tar(
            Device(Path("never-real-adb")), "/synthetic", "private", "bad", tmp_path
        )
    receipt = json.loads((tmp_path / "000001.json").read_bytes())
    assert receipt["outcome"] == "failed" and not receipt["validated"]


def test_d055_replayed_inventory_rejects_missing_tar_eof():
    with pytest.raises(CaptureError, match="incomplete|malformed"):
        api().data_inventory({"private": tar_bytes()[:1024]})


def test_d055_package_inventory_reads_are_all_durable(tmp_path, monkeypatch):
    from l10n_checker.mutation_device import read_app_data

    module = api()
    device = Device(Path("never-real-adb"))
    monkeypatch.setattr(device, "pid", lambda: "")
    monkeypatch.setattr(device, "root", lambda: None)
    monkeypatch.setattr(device, "unroot", lambda: None)
    monkeypatch.setattr(device, "shell", lambda *a: "present")
    calls = []

    def native(command, **kwargs):
        calls.append(kwargs["timeout"])
        return subprocess.CompletedProcess(command, 0, stdout=tar_bytes())

    monkeypatch.setattr(subprocess, "run", native)
    archives = read_app_data(device, evidence_dir=tmp_path, purpose="final-inventory")
    receipts = [json.loads(p.read_bytes()) for p in sorted(tmp_path.glob("*.json"))]
    assert len(receipts) == len(archives) == 3
    assert {r["root"] for r in receipts} == set(archives)
    assert all(r["purpose"] == "final-inventory" for r in receipts)
    assert calls == [module.READ_LIMIT_S] * 3


@pytest.mark.parametrize("elapsed", [0, 60_000_000_000, 60_000_000_001])
def test_d055_sixty_second_flag_and_zero_duration_are_exact(
    tmp_path, monkeypatch, elapsed
):
    module = api()
    ticks = iter((0, elapsed))
    monkeypatch.setattr(module.time, "monotonic_ns", lambda: next(ticks))
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda command, **kw: subprocess.CompletedProcess(
            command, 0, stdout=tar_bytes()
        ),
    )
    module.read_tar(
        Device(Path("never-real-adb")), "/synthetic", "private", "boundary", tmp_path
    )
    receipt = json.loads((tmp_path / "000001.json").read_bytes())
    assert receipt["over_60s"] is (elapsed > 60_000_000_000)
    assert receipt["duration_s"] == elapsed / 1_000_000_000
    assert receipt["bytes_per_second"] == (
        len(tar_bytes()) / receipt["duration_s"] if elapsed else None
    )


def test_d055_read_attempt_is_durable_before_native_io(tmp_path, monkeypatch):
    module = api()
    reads = tmp_path / "reads"

    def native(*args, **kwargs):
        attempts = json.loads((tmp_path / "reads-attempts.json").read_bytes())
        assert attempts["attempts"][0]["receipt"] == "000001.json"
        assert (
            json.loads((reads / "000001.json").read_bytes())["outcome"] == "attempted"
        )
        raise CaptureError("synthetic native read failed")

    monkeypatch.setattr(subprocess, "run", native)
    with pytest.raises(CaptureError) as caught:
        module.read_tar(
            Device(Path("never-real-adb")), "/synthetic", "private", "initial", reads
        )
    assert failure_details(caught.value)["app_data_read"]["purpose"] == "initial"


def test_d055_read_has_durable_metrics_and_raw_binding(tmp_path, monkeypatch):
    module = api()
    ticks = iter([10_000_000_000, 71_000_000_000])
    monkeypatch.setattr(module.time, "monotonic_ns", lambda: next(ticks))
    raw = tar_bytes()
    calls = []

    def native(command, **kwargs):
        calls.append((command, kwargs["timeout"]))
        return subprocess.CompletedProcess(command, 0, stdout=raw)

    monkeypatch.setattr(subprocess, "run", native)
    device = Device(Path("never-real-adb"))
    result = module.read_tar(
        device, "/synthetic/package", "private", "inventory-only", tmp_path
    )
    assert result == raw
    receipt = json.loads((tmp_path / "000001.json").read_bytes())
    assert receipt["purpose"] == "inventory-only" and receipt["root"] == "private"
    assert receipt["path"] == "/synthetic/package"
    assert receipt["bytes"] == len(raw) and receipt["duration_s"] == 61
    assert receipt["bytes_per_second"] == len(raw) / 61
    assert receipt["limit_s"] == 300 and receipt["over_60s"] is True
    assert receipt["outcome"] == "complete" and receipt["validated"] is True
    assert (tmp_path / receipt["raw"]).read_bytes() == raw
    assert calls[0][1] == 300
