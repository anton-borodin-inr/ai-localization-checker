"""Selection/output safety at the CLI and real filesystem boundary, fake devices only."""

import builtins
import io
import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image
from test_screen_capture import FIXTURES, FakeDevice
from test_text_dump import DumpDevice

from l10n_checker import capture as legacy
from l10n_checker import cli
from l10n_checker.capture import CaptureError
from l10n_checker.screen_capture import (
    capture_manifest,
    manifest_output_directory,
    prepare_device,
)
from l10n_checker.screen_manifest import Inputs


def selected_inputs(protocol=1):
    inputs = Inputs(FIXTURES / "screens.json").select_screens(split="dev")
    inputs.manifest = inputs.manifest.model_copy(
        update={"resolution": [4, 2], "protocol_version": protocol}
    )
    return inputs


@pytest.mark.parametrize("manifest", ["screens.json", "screens-v2.json"])
@pytest.mark.parametrize("prepare", [False, True])
@pytest.mark.parametrize("selector", ["split", "ids"])
def test_cli_holdout_output_in_repository_is_rejected_before_device_access(
    tmp_path, monkeypatch, capsys, manifest, prepare, selector
):
    repo = tmp_path / "repo"
    monkeypatch.setattr(legacy, "REPO_ROOT", repo)
    holdout_id = json.loads((FIXTURES / "split.json").read_bytes())["holdout"][0]
    argv = [
        "l10n-capture",
        "--manifest",
        str(FIXTURES / manifest),
        "--output-dir",
        str(repo / "data/run"),
    ]
    argv += (
        ["--split", "holdout"]
        if selector == "split"
        else ["--screen-id", "tech-picker", "--screen-id", holdout_id]
    )
    if prepare:
        argv.append("--prepare-only")
    monkeypatch.setattr(sys, "argv", argv)
    monkeypatch.setattr(
        cli.Device,
        "connect",
        lambda *_: pytest.fail("device access for forbidden output"),
    )
    assert cli.main() == 1
    assert (
        "Holdout screens require an external output folder" in capsys.readouterr().err
    )
    assert not repo.exists()


@pytest.mark.parametrize("prepare", [False, True])
def test_unselected_library_inputs_cannot_access_device(tmp_path, monkeypatch, prepare):
    monkeypatch.setattr(legacy, "REPO_ROOT", tmp_path)
    inputs = Inputs(FIXTURES / "screens.json")
    device = FakeDevice(inputs)
    with pytest.raises(CaptureError, match="requires --split or --screen-id"):
        if prepare:
            prepare_device(device, inputs, tmp_path / "data/run")
        else:
            capture_manifest(
                device, inputs, tmp_path / "data/run", request=device.request
            )
    assert device.calls == []
    assert not (tmp_path / "data").exists()


@contextmanager
def forbid_repository_writes(monkeypatch, repo):
    """Catch even create-then-delete writes, not merely final tree differences."""

    def check(path):
        if not isinstance(path, int) and Path(
            os.fsdecode(path)
        ).resolve().is_relative_to(repo):
            raise AssertionError(f"Capture attempted a repository write: {path}")

    with monkeypatch.context() as guarded:
        for module, name in ((builtins, "open"), (io, "open"), (os, "open")):
            original = getattr(module, name)

            def opened(path, mode="r", *args, _original=original, **kwargs):
                writes = (
                    bool(
                        mode
                        & (
                            os.O_WRONLY
                            | os.O_RDWR
                            | os.O_CREAT
                            | os.O_TRUNC
                            | os.O_APPEND
                        )
                    )
                    if isinstance(mode, int)
                    else any(c in mode for c in "wax+")
                )
                if writes:
                    check(path)
                return _original(path, mode, *args, **kwargs)

            guarded.setattr(module, name, opened)
        for name in (
            "mkdir",
            "chmod",
            "unlink",
            "remove",
            "rmdir",
            "rename",
            "replace",
        ):
            original = getattr(os, name)

            def changed(path, *args, _original=original, _name=name, **kwargs):
                check(path)
                if _name in {"rename", "replace"}:
                    check(args[0])
                return _original(path, *args, **kwargs)

            guarded.setattr(os, name, changed)
        yield


def snapshot(root):
    return {
        str(p.relative_to(root)): p.read_bytes() if p.is_file() else None
        for p in root.rglob("*")
    }


@pytest.mark.parametrize("protocol", [1, 2])
@pytest.mark.parametrize("failure", [False, True])
def test_external_prepare_and_capture_never_write_repository(
    tmp_path, monkeypatch, protocol, failure
):
    repo = tmp_path / "repo"
    (repo / "data").mkdir(parents=True)
    (repo / "sentinel.txt").write_bytes(b"source unchanged")
    (repo / "data/existing.bin").write_bytes(b"old data unchanged")
    monkeypatch.setattr(legacy, "REPO_ROOT", repo)
    monkeypatch.chdir(repo)
    before = snapshot(repo)
    inputs = selected_inputs(protocol)
    device = (DumpDevice if protocol == 2 else FakeDevice)(inputs)
    external = tmp_path / "external"
    with forbid_repository_writes(monkeypatch, repo):
        plan = prepare_device(device, inputs, external / "prepare")
        if failure:
            device.fault = "dump" if protocol == 2 else "png"
        result = capture_manifest(
            device,
            inputs,
            external / "capture",
            request=device.request,
            device_plan=external / "prepare/device-plan.json",
        )
    assert snapshot(repo) == before
    assert (
        plan["selection"]
        == result["selection"]
        == inputs.capture_selection(["en", "de"])
    )
    assert result["status"] == ("failed" if failure else "complete")
    assert result["settings_restored"] and result["saves_unchanged"]
    assert (external / "prepare/private/GameSettings.json").is_file()
    assert (external / "prepare/private/SaveFiles.tar").is_file()
    for name in (
        "private/GameSettings.json",
        "private/SaveFiles.tar",
        "summary.json",
        "gallery.html",
        "contact-sheet.png",
    ):
        assert (external / "capture" / name).is_file()
    expected_ids = {s.id for s in inputs.screens()}
    assert {r["screen"] for r in result["records"]} == expected_ids
    assert {c["screen"] for c in result["comparisons"]} == expected_ids
    assert (
        all(c["status"] == "identical" for c in result["comparisons"])
        if not failure
        else any(c["status"] == "unavailable" for c in result["comparisons"])
    )
    if not failure:
        assert len(list((external / "capture").glob("pass-*/*.png"))) == 20
        if protocol == 2:
            assert len(list((external / "capture").glob("pass-*/*.pair.json"))) == 20
            assert len(list((external / "capture").glob("pass-*/*.texts.json"))) == 20
    assert not list(external.rglob("*.tmp"))


@pytest.mark.parametrize("kind", ["root", "ancestor", "repository-source"])
def test_output_redirects_and_repository_source_paths_rejected(
    tmp_path, monkeypatch, kind
):
    repo = tmp_path / "repo"
    (repo / "data").mkdir(parents=True)
    monkeypatch.setattr(legacy, "REPO_ROOT", repo)
    if kind == "root":
        folder = tmp_path / "link"
        folder.symlink_to(repo / "data", target_is_directory=True)
    elif kind == "ancestor":
        link = tmp_path / "link"
        link.symlink_to(repo, target_is_directory=True)
        folder = link / "data/run"
    else:
        folder = repo / "source"
    inputs = selected_inputs()
    device = FakeDevice(inputs)
    with pytest.raises(CaptureError, match="symbolic-link|data/"):
        prepare_device(device, inputs, folder)
    assert device.calls == []


def test_external_overwrite_preserves_previous_run_outside_repository(
    tmp_path, monkeypatch
):
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setattr(legacy, "REPO_ROOT", repo)
    folder = tmp_path / "external/capture"
    folder.mkdir(parents=True)
    (folder / "old.png").write_bytes(b"preserve old evidence")
    inputs = selected_inputs()
    device = FakeDevice(inputs)
    with forbid_repository_writes(monkeypatch, repo):
        result = capture_manifest(
            device, inputs, folder, overwrite=True, request=device.request
        )
    assert result["status"] == "complete"
    previous = list(folder.parent.glob("capture.previous-*"))
    assert len(previous) == 1
    assert (previous[0] / "old.png").read_bytes() == b"preserve old evidence"
    assert not (folder / "old.png").exists()
    assert snapshot(repo) == {}


@pytest.mark.parametrize("prepare", [False, True])
def test_output_ancestor_cannot_move_repository_before_device_access(
    tmp_path, monkeypatch, prepare
):
    folder = tmp_path / "chosen-output"
    repo = folder / "repo"
    repo.mkdir(parents=True)
    sentinel = repo / "source.txt"
    sentinel.write_bytes(b"repository stays here")
    (folder / "unrelated.txt").write_bytes(b"unrelated data stays here")
    monkeypatch.setattr(legacy, "REPO_ROOT", repo)
    inputs = selected_inputs()
    device = FakeDevice(inputs)
    with pytest.raises(CaptureError, match="contains the repository"):
        if prepare:
            prepare_device(device, inputs, folder)
        else:
            capture_manifest(
                device, inputs, folder, overwrite=True, request=device.request
            )
    assert sentinel.read_bytes() == b"repository stays here"
    assert (folder / "unrelated.txt").read_bytes() == b"unrelated data stays here"
    assert not list(tmp_path.glob("chosen-output.previous-*"))
    assert device.calls == []


def case_alias(path):
    alias = path.with_name(path.name.upper())
    if not alias.exists() or not alias.samefile(path):
        pytest.skip("Case aliases require a case-insensitive test filesystem")
    return alias


@pytest.mark.parametrize("prepare", [False, True])
def test_case_alias_ancestor_preserves_repository_and_unrelated_files(
    tmp_path, monkeypatch, prepare
):
    folder = tmp_path / "chosen-output"
    repo = folder / "repo"
    repo.mkdir(parents=True)
    sentinel = repo / "source.txt"
    sentinel.write_bytes(b"repository stays here")
    unrelated = folder / "unrelated.txt"
    unrelated.write_bytes(b"unrelated data stays here")
    alias = case_alias(folder)
    monkeypatch.setattr(legacy, "REPO_ROOT", repo)
    inputs = selected_inputs()
    device = FakeDevice(inputs)
    with pytest.raises(CaptureError, match="contains the repository"):
        if prepare:
            prepare_device(device, inputs, alias)
        else:
            capture_manifest(
                device, inputs, alias, overwrite=True, request=device.request
            )
    assert sentinel.read_bytes() == b"repository stays here"
    assert unrelated.read_bytes() == b"unrelated data stays here"
    assert not list(tmp_path.glob("*.previous-*"))
    assert device.calls == []


@pytest.mark.parametrize("selector", ["split", "ids"])
@pytest.mark.parametrize("prepare", [False, True])
@pytest.mark.parametrize("destination", ["root", "new-nested"])
def test_case_alias_holdout_output_rejected_for_both_selectors(
    tmp_path, monkeypatch, capsys, selector, prepare, destination
):
    repo = tmp_path / "repo"
    repo.mkdir()
    alias = case_alias(repo)
    sentinel = repo / "source.txt"
    sentinel.write_bytes(b"unchanged")
    monkeypatch.setattr(legacy, "REPO_ROOT", repo)
    folder = alias if destination == "root" else alias / "data/new/run"
    held_id = json.loads((FIXTURES / "split.json").read_bytes())["holdout"][0]
    argv = [
        "l10n-capture",
        "--manifest",
        str(FIXTURES / "screens.json"),
        "--output-dir",
        str(folder),
        "--overwrite",
    ]
    argv += ["--split", "holdout"] if selector == "split" else ["--screen-id", held_id]
    if prepare:
        argv.remove("--overwrite")
        argv.append("--prepare-only")
    monkeypatch.setattr(sys, "argv", argv)
    monkeypatch.setattr(
        cli.Device,
        "connect",
        lambda *_: pytest.fail("device access through a repository case alias"),
    )
    assert cli.main() == 1
    assert (
        "Holdout screens require an external output folder" in capsys.readouterr().err
    )
    assert sentinel.read_bytes() == b"unchanged"
    assert not (repo / "data").exists()
    assert not list(tmp_path.glob("*.previous-*"))


@pytest.mark.parametrize("existing_data", [False, True])
def test_dev_data_through_repository_case_alias_is_allowed(
    tmp_path, monkeypatch, existing_data
):
    repo = tmp_path / "repo"
    repo.mkdir()
    if existing_data:
        (repo / "data").mkdir()
    alias = case_alias(repo)
    monkeypatch.setattr(legacy, "REPO_ROOT", repo)
    folder = alias / ("DATA" if existing_data else "data") / "new/run"
    assert manifest_output_directory(folder, False) == folder.resolve()
    assert not (repo / "data/new").exists()


def test_data_symlink_cannot_authorize_writes_to_repository_source(
    tmp_path, monkeypatch
):
    repo = tmp_path / "repo"
    source = repo / "source"
    source.mkdir(parents=True)
    (repo / "data").symlink_to(source, target_is_directory=True)
    monkeypatch.setattr(legacy, "REPO_ROOT", repo)
    with pytest.raises(CaptureError, match="data/|symbolic-link"):
        manifest_output_directory(source / "run", False)
    assert not (source / "run").exists()


def test_device_verification_cannot_prepare_or_capture_without_approved_arguments(
    request, monkeypatch
):
    from test_screen_capture_device import test_real_dev_manifest_capture

    monkeypatch.setattr(
        cli, "main", lambda: pytest.fail("capture without approved arguments")
    )
    assert hasattr(request.config.option, "capture_device_plan")
    assert hasattr(request.config.option, "capture_output_dir")
    request = SimpleNamespace(config=SimpleNamespace(getoption=lambda _: None))
    with pytest.raises(pytest.fail.Exception, match="separate write approval first"):
        test_real_dev_manifest_capture(request, monkeypatch)


@pytest.mark.parametrize("alias", [False, True])
def test_device_verification_rejects_repository_output_before_reading_plan(
    tmp_path, monkeypatch, alias
):
    import test_screen_capture_device as device_test

    repo = tmp_path / "repo"
    repo.mkdir()
    folder = (case_alias(repo) if alias else repo) / "data/new-capture"
    inputs = selected_inputs(2)
    monkeypatch.setattr(legacy, "REPO_ROOT", repo)
    monkeypatch.setattr(device_test, "Inputs", lambda _, **selection: inputs)
    monkeypatch.setattr(
        cli, "main", lambda: pytest.fail("device access before external-output check")
    )
    options = {
        "--capture-device-plan": str(tmp_path / "missing-plan.json"),
        "--capture-output-dir": str(folder),
    }
    request = SimpleNamespace(config=SimpleNamespace(getoption=options.__getitem__))
    with pytest.raises(AssertionError, match="requires external output"):
        device_test.test_real_dev_manifest_capture(request, monkeypatch)
    assert not (repo / "data").exists()


@pytest.mark.parametrize("protocol", [1, 2])
@pytest.mark.parametrize("selector", ["split", "ids"])
def test_selected_batch_keeps_both_passes_checks_and_gallery_scoped(
    tmp_path, monkeypatch, protocol, selector
):
    monkeypatch.setattr(legacy, "REPO_ROOT", tmp_path / "repo")
    inputs = selected_inputs(protocol)
    if selector == "ids":
        inputs = inputs.select_screens(
            screen_ids=[s.id for s in inputs.screens()][::-1]
        )
    device = (DumpDevice if protocol == 2 else FakeDevice)(inputs)
    plan = prepare_device(device, inputs, tmp_path / "prepare")
    folder = tmp_path / "capture"
    result = capture_manifest(
        device,
        inputs,
        folder,
        request=device.request,
        device_plan=tmp_path / "prepare/device-plan.json",
    )
    ids = [s.id for s in inputs.screens()]
    expected = [
        (n, code, sid)
        for n, order in ((1, ids), (2, ids[::-1]))
        for code in ("en", "de")
        for sid in order
    ]
    assert [
        (r["pass"], r["language"], r["screen"]) for r in result["records"]
    ] == expected
    assert [v["screen_order"] for v in plan["planned_app_data_operations"][:-1]] == [
        ids,
        ids,
        ids[::-1],
        ids[::-1],
    ]
    assert result["status"] == "complete"
    assert device.starts == 4 and device.writes == 5
    assert len(result["records"]) == 20 and len(result["comparisons"]) == 10
    assert result["settings_restored"] and result["saves_unchanged"]
    page = (folder / "gallery.html").read_text()
    assert page.count("<figure>") == 10
    unselected = {s.id for s in inputs.manifest.screens} - set(ids)
    assert all(sid not in page for sid in unselected)
    with Image.open(folder / "contact-sheet.png") as sheet:
        assert sheet.size == (960, 250 * len(ids))
    if protocol == 2:
        assert [
            (r["pass"], r["language"], r["screen"])
            for r in plan["planned_hook_output_operations"]
        ] == expected
        assert all(c["dump_status"] == "identical" for c in result["comparisons"])


@pytest.mark.parametrize("protocol", [1, 2])
@pytest.mark.parametrize("change", ["ids", "selector", "hash", "missing"])
def test_changed_prepared_selection_rejected_before_device_access(
    tmp_path, monkeypatch, protocol, change
):
    monkeypatch.setattr(legacy, "REPO_ROOT", tmp_path / "repo")
    inputs = selected_inputs(protocol)
    device = (DumpDevice if protocol == 2 else FakeDevice)(inputs)
    plan = prepare_device(device, inputs, tmp_path / "prepare")
    if change == "ids":
        plan["selection"]["screen_ids"] = plan["selection"]["screen_ids"][:-1]
    elif change == "selector":
        plan["selection"]["split"] = None
    elif change == "hash":
        plan["selection"]["split_sha256"] = "0" * 64
    else:
        del plan["selection"]
    path = tmp_path / "prepare/device-plan.json"
    path.write_text(json.dumps(plan))
    device.calls.clear()
    with pytest.raises(CaptureError, match="selection changed; no device access"):
        capture_manifest(
            device,
            inputs,
            tmp_path / "capture",
            request=device.request,
            device_plan=path,
        )
    assert device.calls == []
    assert not (tmp_path / "capture").exists()


@pytest.mark.parametrize("protocol", [1, 2])
@pytest.mark.parametrize(
    "raw", [b"not JSON", b"[]", b"null", b'{"selection":{},"selection":{}}']
)
def test_malformed_device_plan_fails_cleanly_before_device_access(
    tmp_path, monkeypatch, protocol, raw
):
    monkeypatch.setattr(legacy, "REPO_ROOT", tmp_path / "repo")
    inputs = selected_inputs(protocol)
    device = (DumpDevice if protocol == 2 else FakeDevice)(inputs)
    path = tmp_path / "plan.json"
    path.write_bytes(raw)
    with pytest.raises(CaptureError, match="Invalid device plan"):
        capture_manifest(
            device,
            inputs,
            tmp_path / "capture",
            request=device.request,
            device_plan=path,
        )
    assert device.calls == []
    assert not (tmp_path / "capture").exists()
