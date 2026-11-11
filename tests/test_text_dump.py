"""Synthetic engine draws and fake transports; never device/provider evidence."""

import base64
import io
import json
import os
import re
import shlex
import shutil
import subprocess
import tarfile
import time
from pathlib import Path

import pytest
from conftest import make_png
from test_screen_capture import FIXTURES, FakeDevice, FakeLog, all_screen_inputs

from l10n_checker import capture as legacy
from l10n_checker.capture import CaptureError
from l10n_checker.hook import HookFailure, request_screen, wait_terminal
from l10n_checker.screen_capture import capture_manifest, prepare_device
from l10n_checker.screen_manifest import Inputs, digest
from l10n_checker.text_dump import (
    canonical_bytes,
    grid_region,
    load_dump,
    rgba_digest,
    scene_to_pixels,
)
from l10n_checker.text_reference import (
    candidate_for,
    compare_capture_runs,
    confirm_bundle,
    review_one,
)


def element(text="Übung...", identity="root/0", **changes):
    box = [10, 20, 90, 40]
    value = {
        "id": identity,
        "logical_id": identity,
        "actor_path": identity,
        "source_key": "Practice",
        "source_keys": [],
        "input_text": "Übung und weitere Wörter",
        "display_text": text,
        "bounds": box,
        "glyph_bounds": box,
        "visible_bounds": box,
        "drawn": True,
        "effective_alpha": 1,
        "visibility": "full",
        "clip_bounds": [0, 0, 2400, 1080],
        "clipped_fraction": 0,
        "clip_cause": "none",
        "ellipsis_applied": True,
        "overflow_x": False,
        "overflow_y": False,
        "font_scale": [0.18, 0.18],
        "pixel_scale": [0.324, 0.324],
        "decoration": False,
        "warnings": [],
        "lines": [
            {
                "text": text,
                "bounds": box,
                "glyphs": [
                    {
                        "text": c,
                        "bounds": box,
                        "visible_bounds": box,
                        "visibility": "full",
                    }
                    for c in text
                ],
            }
        ],
    }
    value.update(changes)
    return value


def dump_for(
    *, screen="tech-picker", language="German", state=None, elements=None, size=None
):
    return {
        "dump_version": 1,
        "protocol_version": 2,
        "build_version_code": 1271045,
        "screen": screen,
        "language": language,
        "state_sha256": digest(canonical_bytes(state or {})),
        "image_size": size or [2400, 1080],
        "viewport": [0, 0, *(size or [2400, 1080])],
        "elements": elements if elements is not None else [element()],
    }


def write_pair(root, dump):
    root.mkdir(exist_ok=True)
    png = make_png(*dump["image_size"])
    raw = canonical_bytes(dump)
    (root / "screen.png").write_bytes(png)
    (root / "screen.texts.json").write_bytes(raw)
    pair = {
        "pair_version": 1,
        "protocol_version": 2,
        "screen": dump["screen"],
        "language": dump["language"],
        "build": {"version_code": str(dump["build_version_code"])},
        "state_sha256": dump["state_sha256"],
        "png": "screen.png",
        "png_sha256": digest(png),
        "rgba_sha256": rgba_digest(png),
        "dump": "screen.texts.json",
        "dump_sha256": digest(raw),
    }
    path = root / "screen.pair.json"
    path.write_bytes(canonical_bytes(pair))
    return path


def test_strict_dump_validation_and_original_rendered_text():
    raw = canonical_bytes(dump_for())
    dump = load_dump(raw)
    assert dump.elements[0].display_text == "Übung..."
    assert "weitere" in dump.elements[0].input_text
    for change in ({"protocol_version": 1}, {"screen": "wrong"}, {"unknown": True}):
        value = dump_for()
        value.update(change)
        with pytest.raises(CaptureError):
            load_dump(canonical_bytes(value), expected={"screen": "tech-picker"})
    with pytest.raises(CaptureError):
        load_dump(
            raw.replace(b'"dump_version":1', b'"dump_version":1,"dump_version":1')
        )


@pytest.mark.parametrize(
    ("sample", "display", "hidden_input", "expected_build"),
    [
        ("fork-synthetic-sample.texts.json", "ü", "ü hidden suffix", 1271047),
        (
            "fork-host-draw-sample.texts.json",
            "üЖ...",
            "[RED]üЖ[] long suffix",
            1271047,
        ),
        (
            "fork-fixed-host-draw-sample.texts.json",
            "üЖ...",
            "[RED]üЖ[] long suffix",
            1271048,
        ),
    ],
)
def test_kotlin_generated_dump_is_consumed_verbatim_without_hidden_input(
    tmp_path, sample, display, hidden_input, expected_build
):
    source = Path(__file__).resolve().parents[1] / "docs/evidence/47" / sample
    raw = source.read_bytes()
    dump = load_dump(raw, expected={"build_version_code": expected_build})
    with pytest.raises(CaptureError, match="build_version_code mismatch"):
        load_dump(raw, expected={"build_version_code": 1271045})
    pair = write_pair(tmp_path, json.loads(raw))
    (tmp_path / "screen.texts.json").write_bytes(raw)
    metadata = json.loads(pair.read_bytes())
    metadata["dump_sha256"] = digest(raw)
    pair.write_bytes(canonical_bytes(metadata))
    candidate = candidate_for(pair)
    assert candidate["dump"]["sha256"] == digest(raw)
    assert candidate["rows"][0]["text_seen"] == dump.elements[0].display_text == display
    assert candidate["rows"][0]["input_text"] == hidden_input
    assert "suffix" not in candidate["rows"][0]["text_seen"]


def test_build_pinned_v2_manifest_reuses_all_v1_screen_inputs():
    v1 = Inputs(FIXTURES / "screens.json")
    v2 = Inputs(FIXTURES / "screens-v2.json")
    assert v1.manifest.protocol_version == 1
    assert v2.manifest.protocol_version == 2
    assert v2.manifest.build.version_code == "1271048"
    assert v2.manifest.model_dump(exclude={"build", "protocol_version"}) == (
        v1.manifest.model_dump(exclude={"build", "protocol_version"})
    )
    assert v2.states == v1.states
    assert v2.settings == v1.settings
    assert v2.fixtures == v1.fixtures


def test_projection_coordinates_and_grid_edges():
    assert scene_to_pixels(
        [100, 100, 200, 200], [1200, 540], [0, 0, 2400, 1080], 1080
    ) == [200, 680, 400, 880]
    assert scene_to_pixels([0, 0, 100, 100], [100, 100], [10, 20, 200, 200], 300) == [
        10,
        80,
        210,
        280,
    ]
    assert grid_region([800, 360, 800, 360], [2400, 1080]) == "center"
    assert grid_region([-10, -10, 0, 0], [2400, 1080]) == "top-left"
    assert grid_region([2400, 1080, 2400, 1080], [2400, 1080]) == "bottom-right"


def test_candidates_preserve_occurrences_and_group_only_explicit_decorations(tmp_path):
    first = element()
    repeat = element(identity="root/1")
    shadow = element(identity="root/0-shadow", logical_id="root/0", decoration=True)
    path = write_pair(
        tmp_path, dump_for(elements=[first, repeat, shadow, element("123", "root/2")])
    )
    candidate = candidate_for(path)
    assert [r["text_seen"] for r in candidate["rows"]] == [
        "Übung...",
        "Übung...",
        "123",
    ]
    assert candidate["rows"][0]["element_ids"] == ["root/0", "root/0-shadow"]
    assert candidate["rows"][2]["primary_denominator"] is False
    assert canonical_bytes(candidate_for(path)) == canonical_bytes(candidate)


def test_wrapping_composition_and_partial_clip_never_complete_hidden_input(tmp_path):
    wrapped = element(
        "Two\nlines", lines=[element("Two")["lines"][0], element("lines")["lines"][0]]
    )
    clipped = element(
        "Visible HIDDEN",
        "root/1",
        visibility="partial",
        clipped_fraction=0.4,
        clip_cause="ancestor_scissor",
    )
    for glyph in clipped["lines"][0]["glyphs"][8:]:
        glyph.update(visibility="hidden", visible_bounds=None)
    clipped["lines"][0]["glyphs"][7].update(visibility="partial")
    path = write_pair(tmp_path, dump_for(elements=[wrapped, clipped]))
    rows = candidate_for(path)["rows"]
    assert rows[0]["text_seen"] == "Two\nlines"  # One logical wrapped unit.
    assert rows[1]["text_seen"] == "Visible"
    assert rows[1]["primary_denominator"] is False
    assert all("HIDDEN" not in r["text_seen"] for r in rows)


def test_zero_alpha_unmapped_and_composed_text(tmp_path):
    invisible = element(
        "Never", visibility="hidden", visible_bounds=None, effective_alpha=0
    )
    composed = element(
        "4 turns", "root/1", source_key=None, source_keys=["[amount] turns"]
    )
    unmapped = element(
        "Review", "root/2", bounds=None, actor_path=None, warnings=["unknown_owner"]
    )
    no_key = element(
        "Drawn text", "root/3", source_key=None, warnings=["source_unavailable"]
    )
    rows = candidate_for(
        write_pair(tmp_path, dump_for(elements=[invisible, composed, unmapped, no_key]))
    )["rows"]
    assert [r["text_seen"] for r in rows] == ["4 turns", "Review", "Drawn text"]
    assert rows[0]["source_keys"] == ["[amount] turns"]
    assert rows[1]["primary_denominator"] is False
    assert rows[2]["primary_denominator"] is True
    assert rows[2]["source_keys"] == []


@pytest.mark.parametrize(
    "text,warnings,expected,primary",
    [
        ("Kaufen 160¤", ["icon_glyph:a4"], "Kaufen 160", True),
        (
            "Arbeiter\n31⚙ 8⏳",
            ["icon_glyph:2699", "icon_glyph:23f3", "source_unavailable"],
            "Arbeiter\n31 8",
            True,
        ),
        (
            "Requires at least 2 population",
            ["markup_input"],
            "Requires at least 2 population",
            True,
        ),
        ("Cost ¤ • ⚙ \ue115", [], "Cost ¤ • ⚙ \ue115", True),
        ("Work ⚙  now", ["icon_glyph:2699"], "Work now", True),
        ("160¤", ["icon_glyph:a4"], "160", False),
        ("Drawn text", ["unmapped_font_draw"], "Drawn text", False),
        ("Drawn ¤", ["icon_glyph:a4", "unmapped_font_draw"], "Drawn", False),
    ],
)
def test_candidate_icon_provenance_and_primary_rules(
    tmp_path, text, warnings, expected, primary
):
    row = candidate_for(
        write_pair(tmp_path, dump_for(elements=[element(text, warnings=warnings)]))
    )["rows"][0]
    assert row["text_seen"] == expected
    assert row["primary_denominator"] is primary
    assert row["warnings"] == warnings


@pytest.mark.parametrize(
    "event",
    [
        "",
        "file=../../settings sha256=" + "a" * 64,
        "file=files/l10n-hook/old.json sha256=" + "a" * 64,
    ],
)
def test_v2_missing_or_unsafe_dump_waits_for_terminal_then_fails(event):
    lines = ["L10N_SCREEN_PANES tech-picker request=r panes="]
    if event:
        lines.append("L10N_SCREEN_DUMP tech-picker request=r " + event)
    lines.append("L10N_SCREEN_READY tech-picker request=r frames=2")
    with pytest.raises(HookFailure) as error:
        wait_terminal(
            FakeLog(lines), "tech-picker", "r", set(), time.monotonic() + 1, 2
        )
    assert error.value.terminal


class DumpDevice(FakeDevice):
    serial = "emulator-9999"

    def request(self, device, screen, token, state, timeout, **kwargs):
        assert kwargs == {"protocol_version": 2}
        result = super().request(device, screen, token, state, timeout)
        value = dump_for(
            screen=screen,
            language=json.loads(self.settings)["language"],
            state=state,
            elements=[],
            size=[4, 2],
        )
        self.raw_dump = canonical_bytes(value)
        result["dump"] = {
            "file": f"files/l10n-hook/{token}.json",
            "sha256": digest(self.raw_dump),
        }
        self.hook_files[result["dump"]["file"]] = self.raw_dump
        return result

    def __init__(self, inputs, fault=None):
        super().__init__(inputs, fault)
        self.hook_files = {"files/l10n-hook/pre-existing-near-name.json": b"keep"}
        self.unlinked = []
        self.hook_directory = True

    def identity(self, relative=None):
        result = [f"1 {i} 1 41c0 10001 10001 0" for i in (1, 2, 3)]
        if relative:
            assert relative in self.hook_files

            # Identity belongs to the persistent path, not its sorted position.
            inode = int(digest(relative.encode())[:8], 16)
            result.append(
                f"1 {inode} 1 8180 10001 10001 {len(self.hook_files[relative])}"
            )
        return result

    def shell(self, *args):
        from l10n_checker.app_data import DATA_ROOTS

        if len(args) == 1 and args[0].startswith("if [ -d "):
            return "present"
        if args == ("dumpsys", "package", legacy.PACKAGE):
            return "User 0: stopped=" + ("false" if self.running else "true")
        if len(args) == 1 and args[0].startswith("set -eu\n# D055"):
            script = args[0]
            if "# D055 guarded unlink" in script:
                absolute = shlex.split(
                    next(s for s in script.splitlines() if s.startswith("rm -- "))
                )[2]
                relative = absolute.removeprefix(DATA_ROOTS["private"] + "/")
                expected = shlex.split(
                    re.search(
                        r'test "\$observed" = (.*?)\ntest "\$\(sha256sum',
                        script,
                        re.DOTALL,
                    )[1]
                )[0]
                assert not self.running
                if "\n".join(self.identity(relative)) != expected:
                    raise CaptureError("Synthetic guarded identity mismatch")
                if digest(self.hook_files[relative]) + "  " + absolute not in script:
                    raise CaptureError("Synthetic guarded content mismatch")
                del self.hook_files[relative]
                self.unlinked.append(relative)
                return "D055-deleted"
            absolute = shlex.split(script.splitlines()[-1])[-1]
            relative = absolute.removeprefix(DATA_ROOTS["private"] + "/")
            return "\n".join(
                self.identity(None if relative == "files/l10n-hook" else relative)
            )
        return super().shell(*args)

    def run(self, *args, timeout_s=30):
        from l10n_checker.app_data import DATA_ROOTS

        if args[:4] == ("exec-out", "run-as", legacy.PACKAGE, "cat"):
            return b"broken" if self.fault == "dump" else self.raw_dump
        if args[:2] == ("exec-out", "cat") and args[-1] != legacy.SETTINGS_PATH:
            return self.hook_files[args[-1].removeprefix(DATA_ROOTS["private"] + "/")]
        if args[:2] == ("exec-out", "tar") and args[-2] in DATA_ROOTS.values():
            assert timeout_s == 300
            root = next(k for k, v in DATA_ROOTS.items() if v == args[-2])
            files = (
                {"files/GameSettings.json": self.settings, **self.hook_files}
                if root == "private"
                else {
                    "files/SaveFiles/" + k.removeprefix("./"): v
                    for k, v in self.saves.items()
                }
                if root == "external"
                else {"synthetic": b"keep"}
            )
            output = io.BytesIO()
            with tarfile.open(fileobj=output, mode="w") as tar:
                for name in [
                    ".",
                    "files",
                    *(
                        ["files/l10n-hook"]
                        if root == "private" and self.hook_directory
                        else []
                    ),
                ]:
                    info = tarfile.TarInfo(name)
                    info.type, info.uid, info.gid, info.mode = (
                        tarfile.DIRTYPE,
                        10001,
                        10001,
                        0o700,
                    )
                    tar.addfile(info)
                for name, raw in files.items():
                    info = tarfile.TarInfo("./" + name)
                    info.size, info.uid, info.gid, info.mode = (
                        len(raw),
                        10001,
                        10001,
                        0o600,
                    )
                    tar.addfile(info, io.BytesIO(raw))
            return output.getvalue()
        return super().run(*args, timeout_s=timeout_s)


@pytest.fixture
def d055_env(tmp_path, monkeypatch):
    monkeypatch.setattr(legacy, "REPO_ROOT", tmp_path / "repo")
    inputs = all_screen_inputs().select_screens(screen_ids=["tech-picker"])
    inputs.manifest = inputs.manifest.model_copy(
        update={"resolution": [4, 2], "protocol_version": 2}
    )
    device = DumpDevice(inputs)
    prepare_device(device, inputs, tmp_path / "prepare")

    def capture(**kwargs):
        return capture_manifest(
            device,
            inputs,
            tmp_path / "capture",
            request=kwargs.pop("request", device.request),
            device_plan=tmp_path / "prepare/device-plan.json",
            **kwargs,
        )

    return device, inputs, tmp_path, capture


@pytest.mark.parametrize(
    "collision", ["file", "temporary", "missing-directory", "forged-start"]
)
def test_d055_preflight_is_before_any_device_write(d055_env, collision):
    device, _inputs, folder, capture = d055_env
    plan = json.loads((folder / "prepare/device-plan.json").read_bytes())
    if collision == "missing-directory":
        device.hook_directory = False
    else:
        path = plan["planned_hook_output_operations"][0][
            "temporary" if collision == "temporary" else "file"
        ]
        device.hook_files[path] = b"pre-existing"
        if collision == "forged-start":
            plan["starting_inventory"].pop("private:" + path, None)
            (folder / "prepare/device-plan.json").write_bytes(canonical_bytes(plan))
    result = capture()
    assert result["status"] == "failed"
    assert device.writes == 0 and device.unlinked == []
    assert not any(isinstance(c, tuple) and c[0] == "request" for c in device.calls)


def test_d055_missing_hook_directory_prepare_stops_without_writes(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(legacy, "REPO_ROOT", tmp_path / "repo")
    inputs = all_screen_inputs().select_screens(screen_ids=["tech-picker"])
    inputs.manifest = inputs.manifest.model_copy(update={"protocol_version": 2})
    device = DumpDevice(inputs)
    device.hook_directory = False
    with pytest.raises(CaptureError, match="directory"):
        prepare_device(device, inputs, tmp_path / "prepare")
    assert device.writes == 0 and device.unlinked == []


def test_d055_all_host_outputs_verified_before_first_unlink(d055_env):
    device, _inputs, folder, capture = d055_env
    published = []

    def tamper(record):
        published.append(record)
        if len(published) == 4:
            target = folder / "capture" / published[1]["dump"]
            target.write_bytes(b"tampered second host proof")

    result = capture(on_pair=tamper)
    assert result["status"] == "failed"
    assert result["hook_cleanup"]["status"] == "failed"
    assert "hash" in str(result["hook_cleanup"]["error_details"])
    assert device.unlinked == []


def test_d055_host_proof_ctime_only_change_allows_cleanup(d055_env, monkeypatch):
    from l10n_checker import app_data

    device, _inputs, _folder, capture = d055_env
    host_bytes = app_data.host_bytes
    read_bytes = Path.read_bytes
    changed = []

    def metadata_only(path):
        raw = read_bytes(path)
        before = path.stat()
        os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
        after = path.stat()
        assert before.st_ctime_ns != after.st_ctime_ns
        assert (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) == (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        )
        changed.append(path)
        return raw

    def annotated_read(path):
        with monkeypatch.context() as context:
            context.setattr(Path, "read_bytes", metadata_only)
            return host_bytes(path)

    monkeypatch.setattr(app_data, "host_bytes", annotated_read)
    result = capture()
    assert changed
    assert result["status"] == "complete"
    assert result["hook_cleanup"]["status"] == "verified"
    assert len(device.unlinked) == 4
    assert device.hook_files == {"files/l10n-hook/pre-existing-near-name.json": b"keep"}


def test_d055_host_proof_content_change_still_fails_recorded_hash(
    d055_env, monkeypatch
):
    from l10n_checker import app_data

    device, _inputs, folder, capture = d055_env
    host_bytes = app_data.host_bytes
    read_bytes = Path.read_bytes
    target = None
    changed = False

    def remember(record):
        nonlocal target
        if target is None:
            target = folder / "capture" / record["dump"]

    def change_content(path):
        nonlocal changed
        raw = read_bytes(path)
        if path == target and not changed:
            before = path.stat()
            raw = bytes([raw[0] ^ 1]) + raw[1:]
            path.write_bytes(raw)
            os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
            changed = True
        return raw

    def checked_read(path):
        with monkeypatch.context() as context:
            context.setattr(Path, "read_bytes", change_content)
            return host_bytes(path)

    monkeypatch.setattr(app_data, "host_bytes", checked_read)
    result = capture(on_pair=remember)
    assert changed
    assert result["status"] == "failed"
    assert result["hook_cleanup"]["status"] == "failed"
    assert "hash" in result["hook_cleanup"]["error_details"]["message"]
    assert device.unlinked == []


@pytest.mark.parametrize("temporary", [False, True])
def test_d055_partial_hook_output_is_pulled_without_promoting_capture(
    d055_env, temporary
):
    device, _inputs, folder, capture = d055_env

    def timeout(device, screen, token, state, timeout, **kwargs):
        path = f"files/l10n-hook/{token}.json" + (".tmp" if temporary else "")
        device.hook_files[path] = b"partial raw diagnostic output"
        raise HookFailure("client_timeout", terminal=False, events=[])

    result = capture(request=timeout, fail_fast=True)
    assert result["status"] == "failed" and result["records"][0]["status"] == "failed"
    proof = result["hook_cleanup"]
    assert proof["status"] == "verified"
    entry = next(r for r in proof["paths"] if r["status"] == "deleted")
    assert (
        folder / "capture" / entry["host"]
    ).read_bytes() == b"partial raw diagnostic output"
    assert device.hook_files == {"files/l10n-hook/pre-existing-near-name.json": b"keep"}


@pytest.mark.parametrize("after_unlink", [False, True])
def test_d055_partial_unlink_failure_still_keeps_actual_post_inventory(
    d055_env, after_unlink
):
    device, _inputs, folder, capture = d055_env
    shell = device.shell
    count = 0

    def native(*args):
        nonlocal count
        if len(args) == 1 and "# D055 guarded unlink" in args[0]:
            count += 1
            if count == 2:
                if after_unlink:
                    shell(*args)
                raise CaptureError("second guarded unlink failed")
        return shell(*args)

    device.shell = native
    result = capture()
    assert result["status"] == "failed" and len(device.unlinked) == 1 + after_unlink
    proof = result["hook_cleanup"]
    assert proof["status"] == "failed"
    assert proof.get("after"), (
        "Partial cleanup omitted fresh actual post-cleanup inventory"
    )
    assert (folder / "capture/post-cleanup-inventory.json").is_file()
    assert sum(r["status"] == "deleted" for r in proof["paths"]) == 1
    failures = [r for r in proof["paths"] if r["status"] == "failed"]
    assert len(failures) == 1, "The actual failed deletion attempt must remain explicit"
    assert failures[0]["error_details"]["message"] == "second guarded unlink failed"
    assert "# D055 guarded unlink" in failures[0]["command"]
    assert ("private:" + failures[0]["path"] in proof["after"]) is not after_unlink
    assert count == 2, "Partial deletion must not retry"


@pytest.mark.parametrize(
    "error_type", [KeyboardInterrupt, SystemExit, ValueError, CaptureError, OSError]
)
def test_d055_empty_error_after_last_pair_never_persists_success(d055_env, error_type):
    device, _inputs, folder, capture = d055_env
    original = error_type()
    count = 0

    def stop(record):
        nonlocal count
        count += 1
        if count == 4:
            raise original

    if not isinstance(original, Exception):
        with pytest.raises(error_type) as caught:
            capture(on_pair=stop, fail_fast=True)
        assert caught.value is original
    else:
        capture(on_pair=stop, fail_fast=True)
    summary = json.loads((folder / "capture/summary.json").read_bytes())
    assert summary["status"] == "failed"
    assert summary["fatal_error_details"]["type"] == error_type.__name__
    assert summary["hook_cleanup"]["status"] == "verified"
    assert len(device.unlinked) == 4


def test_d055_cancellation_after_last_pair_never_persists_success(d055_env):
    device, _inputs, folder, capture = d055_env
    calls = 0
    original = KeyboardInterrupt("cancel at last pair")

    def cancel(record):
        nonlocal calls
        calls += 1
        if calls == 4:
            raise original

    with pytest.raises(KeyboardInterrupt) as caught:
        capture(on_pair=cancel)
    assert caught.value is original
    summary = json.loads((folder / "capture/summary.json").read_bytes())
    assert summary["status"] == "failed", (
        "Cancellation was durably recorded as complete"
    )
    assert summary["hook_cleanup"]["status"] == "verified"
    assert summary["fatal_error_details"]["type"] == "KeyboardInterrupt"
    assert device.hook_files == {"files/l10n-hook/pre-existing-near-name.json": b"keep"}


@pytest.mark.parametrize(
    "alias",
    [
        "hardlink",
        "symlink",
        "ancestor",
        "directory",
        "inode-race",
        "bytes-race",
        "host-symlink",
        "host-hardlink",
    ],
)
def test_d055_alias_and_race_fail_closed_without_unlink(d055_env, alias):
    import os

    device, _inputs, folder, capture = d055_env
    identity = device.identity
    raced = False

    def changed(relative=None):
        result = identity(relative)
        if relative:
            parts = result[-1].split()
            if alias == "hardlink":
                parts[2] = "2"
            if alias in {"symlink", "directory"}:
                parts[3] = "a180" if alias == "symlink" else "4180"
            if alias == "inode-race" and raced:
                parts[1] = str(int(parts[1]) + 1)
            result[-1] = " ".join(parts)
            if alias == "ancestor":
                result[0] = "1 999 1 41c0 10001 10001 0"
        return result

    device.identity = changed
    shell = device.shell

    def native(*args):
        nonlocal raced
        if len(args) == 1 and "# D055 guarded unlink" in args[0]:
            raced = True
            if alias == "bytes-race":
                path = shlex.split(
                    next(s for s in args[0].splitlines() if s.startswith("rm -- "))
                )[2]
                from l10n_checker.app_data import DATA_ROOTS

                relative = path.removeprefix(DATA_ROOTS["private"] + "/")
                raw = device.hook_files[relative]
                device.hook_files[relative] = bytes([raw[0] ^ 1]) + raw[1:]
        return shell(*args)

    device.shell = native
    count = 0

    def host_alias(record):
        nonlocal count
        count += 1
        if count == 4 and alias.startswith("host-"):
            path = folder / "capture" / record["dump"]
            target = path.with_suffix(".retained")
            path.rename(target)
            if alias == "host-symlink":
                path.symlink_to(target)
            else:
                os.link(target, path)

    result = capture(on_pair=host_alias)
    assert result["status"] == "failed" and result["hook_cleanup"]["status"] == "failed"
    assert device.unlinked == []


def test_d055_read_failure_is_fatal_even_without_fail_fast(d055_env):
    device, _inputs, folder, capture = d055_env
    run = device.run
    reads = 0

    def native(*args, timeout_s=30):
        nonlocal reads
        if args == ("exec-out", "cat", legacy.SETTINGS_PATH):
            reads += 1
            if reads == 4:
                raise CaptureError("synthetic app-data read failure")
        return run(*args, timeout_s=timeout_s)

    device.run = native
    result = capture(fail_fast=False)
    requests = [c for c in device.calls if isinstance(c, tuple) and c[0] == "request"]
    assert result["status"] == "failed"
    assert len(requests) == 1, (
        "Operational app-data read failure continued to another request"
    )
    failed = [
        json.loads(p.read_bytes())
        for p in (folder / "capture/reads").glob("*.json")
        if json.loads(p.read_bytes())["outcome"] == "failed"
    ]
    assert len(failed) == 1
    assert result["hook_cleanup"]["status"] == "verified"


@pytest.mark.parametrize(
    "fault",
    [
        "absent",
        "metadata-error",
        "malformed-metadata",
        "wrong-settings",
        "invalid-json",
    ],
)
def test_d055_settings_observation_boundary_is_fatal(d055_env, fault):
    device, _inputs, folder, capture = d055_env
    stat, run = device.stat, device.run
    stats = reads = 0

    def metadata(path):
        nonlocal stats
        stats += 1
        if stats == 6:
            if fault == "absent":
                return None
            if fault == "metadata-error":
                raise OSError("synthetic settings metadata failed")
            if fault == "malformed-metadata":
                return "unavailable"
        return stat(path)

    def native(*args, timeout_s=30):
        nonlocal reads
        raw = run(*args, timeout_s=timeout_s)
        if args == ("exec-out", "cat", legacy.SETTINGS_PATH):
            reads += 1
            if reads == 4:
                if fault == "wrong-settings":
                    assert b"English" in raw
                    return raw.replace(b"English", b"Russian")
                if fault == "invalid-json":
                    return b" " * len(raw)
        return raw

    device.stat, device.run = metadata, native
    result = capture(fail_fast=False)
    requests = [c for c in device.calls if isinstance(c, tuple) and c[0] == "request"]
    assert len(requests) == 1, "Failed settings observation issued another request"
    assert result["status"] == "failed" and "fatal_error_details" in result
    failed = [
        json.loads(p.read_bytes())
        for p in (folder / "capture/reads").glob("*.json")
        if json.loads(p.read_bytes())["outcome"] == "failed"
    ]
    assert len(failed) == 1
    assert failed[0]["purpose"] == "capture-settings-readback"
    assert failed[0]["validated"] is False
    assert result["hook_cleanup"]["status"] == "verified"


@pytest.mark.parametrize("stage", ["prepare", "capture"])
@pytest.mark.parametrize("fault", ["none", "absent", "metadata-error"])
def test_d055_initial_backup_metadata_is_durably_observed(d055_env, stage, fault):
    device, inputs, folder, capture = d055_env
    stat = device.stat
    calls = 0
    original = OSError("synthetic initial backup metadata failed")

    def metadata(path):
        nonlocal calls
        calls += 1
        if calls == 1:
            if fault == "absent":
                return None
            if fault == "metadata-error":
                raise original
        return stat(path)

    device.stat = metadata
    target = folder / ("prepare-again" if stage == "prepare" else "capture")
    result = None
    if stage == "prepare":
        if fault == "none":
            result = prepare_device(device, inputs, target)
        else:
            with pytest.raises(
                CaptureError if fault == "absent" else OSError
            ) as caught:
                prepare_device(device, inputs, target)
            if fault == "metadata-error":
                assert caught.value is original
            assert getattr(caught.value, "app_data_read", {}).get("purpose") == (
                "settings-backup"
            )
            assert getattr(caught.value, "app_data_read_failure", False) is True
    else:
        result = capture(fail_fast=False)
    receipts = [
        json.loads(p.read_bytes()) for p in sorted((target / "reads").glob("*.json"))
    ]
    attempts = json.loads((target / "reads-attempts.json").read_bytes())["attempts"]
    assert len(receipts) == len(attempts)
    if fault == "none":
        assert result is not None
        assert all(r["outcome"] == "complete" for r in receipts)
        assert result["backup"]["settings_stat"] == stat(legacy.SETTINGS_PATH)
        if stage == "capture":
            assert result["status"] == "complete" and device.writes == 5
        return
    assert calls == 1
    assert device.writes == 0 and device.unlinked == []
    assert not any(isinstance(c, tuple) and c[0] == "request" for c in device.calls)
    failed = [r for r in receipts if r["outcome"] == "failed"]
    assert len(failed) == 1
    read = failed[0]
    assert read["purpose"] == attempts[-1]["purpose"] == "settings-backup"
    assert read["bytes"] == 0 and read["validated"] is False
    assert (target / "reads" / read["raw"]).read_bytes() == b""
    assert read["duration_s"] >= 0 and read["limit_s"] == 300
    assert read["bytes_per_second"] == (0 if read["duration_s"] else None)
    if stage == "capture":
        assert result is not None
        assert result["status"] == "failed"
        details = result["fatal_error_details"]
        assert details["type"] == ("CaptureError" if fault == "absent" else "OSError")
        assert details["app_data_read"]["purpose"] == "settings-backup"
        if fault == "metadata-error":
            assert getattr(original, "app_data_read", None) == details["app_data_read"]


def test_d055_short_settings_read_is_durably_incomplete(d055_env):
    device, _inputs, folder, capture = d055_env
    run = device.run

    def native(*args, timeout_s=30):
        raw = run(*args, timeout_s=timeout_s)
        return raw[:-1] if args == ("exec-out", "cat", legacy.SETTINGS_PATH) else raw

    device.run = native
    result = capture()
    assert result["status"] == "failed" and device.writes == 0
    receipts = [
        json.loads(p.read_bytes()) for p in (folder / "capture/reads").glob("*.json")
    ]
    receipt = next(r for r in receipts if r["purpose"] == "settings-backup")
    assert receipt["outcome"] == "failed", (
        "Partial file read falsely claims complete validation"
    )
    assert receipt["validated"] is False


@pytest.mark.parametrize("stage", ["comparison", "checkpoint"])
def test_d055_finalization_failure_does_not_replace_cancellation(
    d055_env, monkeypatch, stage
):
    from l10n_checker import screen_capture

    _device, _inputs, folder, capture = d055_env
    original = KeyboardInterrupt("cancel after all pairs")
    count = 0

    def cancel(record):
        nonlocal count
        count += 1
        if count == 4:
            raise original

    def comparison(*args):
        raise OSError("comparison finalization failed")

    write = screen_capture.write_json
    broken = False

    def checkpoint(path, value):
        nonlocal broken
        if (
            path.name == "summary.json"
            and value.get("fatal_error_details", {}).get("type") == "KeyboardInterrupt"
            and not broken
        ):
            broken = True
            raise OSError("checkpoint finalization failed")
        return write(path, value)

    if stage == "comparison":
        monkeypatch.setattr(screen_capture, "compare_pixels", comparison)
    else:
        monkeypatch.setattr(screen_capture, "write_json", checkpoint)
    with pytest.raises(KeyboardInterrupt) as caught:
        capture(on_pair=cancel)
    assert caught.value is original
    assert any(stage in e["message"] for e in original.cleanup_errors)
    summary = json.loads((folder / "capture/summary.json").read_bytes())
    assert summary["status"] == "failed"
    assert summary["fatal_error_details"]["type"] == "KeyboardInterrupt"
    assert summary["hook_cleanup"]["status"] == "verified"


def test_d055_gallery_error_preserves_primary_capture_error(d055_env, monkeypatch):
    from l10n_checker import screen_capture

    _device, _inputs, folder, capture = d055_env
    original = CaptureError("primary pair callback failure")

    def stop(record):
        raise original

    def gallery(*args):
        raise OSError("gallery finalization failed")

    monkeypatch.setattr(screen_capture, "gallery", gallery)
    with pytest.raises(CaptureError) as caught:
        capture(on_pair=stop, fail_fast=True)
    assert caught.value is original
    assert original.cleanup_errors[-1]["message"] == "gallery finalization failed"
    summary = json.loads((folder / "capture/summary.json").read_bytes())
    assert summary["status"] == "failed" and summary["fatal_error"] == str(original)


def test_d055_standalone_v2_cleans_only_verified_new_outputs(tmp_path, monkeypatch):
    monkeypatch.setattr(legacy, "REPO_ROOT", tmp_path / "repo")
    inputs = all_screen_inputs().select_screens(screen_ids=["tech-picker"])
    inputs.manifest = inputs.manifest.model_copy(
        update={"resolution": [4, 2], "protocol_version": 2}
    )
    device = DumpDevice(inputs)
    prepare_device(device, inputs, tmp_path / "prepare")
    result = capture_manifest(
        device,
        inputs,
        tmp_path / "capture",
        request=device.request,
        device_plan=tmp_path / "prepare/device-plan.json",
    )
    assert result["status"] == "complete"
    assert result.get("hook_cleanup", {}).get("status") == "verified", (
        "Real capture lacks exact host-verified cleanup"
    )
    cleanup = result["hook_cleanup"]
    assert len(cleanup["paths"]) == 8
    assert sum(r["status"] == "deleted" for r in cleanup["paths"]) == 4
    assert sum(r["status"] == "absent" for r in cleanup["paths"]) == 4
    assert cleanup["preservation"]["unexpected_changes"] == []
    assert device.hook_files == {"files/l10n-hook/pre-existing-near-name.json": b"keep"}


def test_complete_fake_v2_capture_and_changed_dump_failures(tmp_path, monkeypatch):
    monkeypatch.setattr(legacy, "REPO_ROOT", tmp_path / "repo")
    inputs = all_screen_inputs()
    inputs.manifest = inputs.manifest.model_copy(
        update={"resolution": [4, 2], "protocol_version": 2}
    )
    device = DumpDevice(inputs)
    prepare = tmp_path / "data/prepare"
    plan = prepare_device(device, inputs, prepare)
    assert len(plan["planned_hook_output_operations"]) == 40
    assert len({r["file"] for r in plan["planned_hook_output_operations"]}) == 40
    result = capture_manifest(
        device,
        inputs,
        tmp_path / "data/capture",
        request=device.request,
        device_plan=prepare / "device-plan.json",
    )
    assert result["status"] == "complete"
    assert len(result["records"]) == 40
    assert all(c["dump_status"] == "identical" for c in result["comparisons"])
    assert all("pair" in r and "rgba_sha256" in r for r in result["records"])
    assert result["settings_restored"] and result["saves_unchanged"]
    device.fault = "dump"
    failed = capture_manifest(
        device,
        inputs,
        tmp_path / "data/broken",
        request=device.request,
        device_plan=prepare / "device-plan.json",
    )
    assert failed["status"] == "failed"
    assert all(r["status"] == "failed" for r in failed["records"])
    assert not list((tmp_path / "data/broken").glob("pass-*/*.png"))


def test_v2_missing_device_plan_has_no_device_access(tmp_path, monkeypatch):
    monkeypatch.setattr(legacy, "REPO_ROOT", tmp_path / "repo")
    inputs = all_screen_inputs()
    inputs.manifest = inputs.manifest.model_copy(update={"protocol_version": 2})
    device = DumpDevice(inputs)
    with pytest.raises(CaptureError, match="exact device plan"):
        capture_manifest(device, inputs, tmp_path / "data/run")
    assert device.calls == []


@pytest.mark.parametrize("change", ["missing_directory", "directory", "temporary"])
def test_v2_changed_output_write_plan_is_rejected_before_device_access(
    tmp_path, monkeypatch, change
):
    monkeypatch.setattr(legacy, "REPO_ROOT", tmp_path / "repo")
    inputs = all_screen_inputs()
    inputs.manifest = inputs.manifest.model_copy(update={"protocol_version": 2})
    device = DumpDevice(inputs)
    prepare = tmp_path / "data/prepare"
    plan = prepare_device(device, inputs, prepare)
    device.calls.clear()
    if change == "missing_directory":
        del plan["planned_hook_directory_operation"]
    elif change == "directory":
        plan["planned_hook_directory_operation"] = {"path": "files/another"}
    else:
        plan["planned_hook_output_operations"][0]["temporary"] += ".changed"
    path = prepare / "device-plan.json"
    path.write_bytes(canonical_bytes(plan))
    with pytest.raises(CaptureError, match="output operations changed"):
        capture_manifest(device, inputs, tmp_path / "data/run", device_plan=path)
    assert device.calls == []


def test_v2_transport_canonical_state_and_stale_events():
    calls = []
    state = {"scroll_to": {}, "scroll": {}, "nested": {"z": 1.0, "a": "Ü"}}

    class Device:
        def shell(self, *args):
            calls.append(args)
            return "Status: ok\n"

    class Log(FakeLog):
        def __init__(self, device):
            super().__init__(
                [
                    "L10N_SCREEN_DUMP tech-picker request=old file=files/l10n-hook/old.json sha256="
                    + "a" * 64,
                    "L10N_SCREEN_PANES tech-picker request=r panes=",
                    "L10N_SCREEN_DUMP tech-picker request=r file=files/l10n-hook/r.json sha256="
                    + "b" * 64,
                    "L10N_SCREEN_READY tech-picker request=r frames=2",
                ]
            )

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

    result = request_screen(
        Device(), "tech-picker", "r", state, 90, log_factory=Log, protocol_version=2
    )
    encoded = calls[0][calls[0].index("l10n_state_b64") + 1]
    assert base64.b64decode(encoded) == canonical_bytes(state)
    assert b'"z":1' in base64.b64decode(encoded)
    assert calls[0][-3:] == ("--es", "l10n_protocol", "2")
    assert result["dump"]["sha256"] == "b" * 64
    assert len(result["events"]) == 3


def test_dump_nondeterminism_fails_run_even_with_identical_pixels(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(legacy, "REPO_ROOT", tmp_path / "repo")
    inputs = all_screen_inputs()
    inputs.manifest = inputs.manifest.model_copy(
        update={"resolution": [4, 2], "protocol_version": 2}
    )

    class Unstable(DumpDevice):
        def request(self, device, screen, token, state, timeout, **kwargs):
            result = super().request(device, screen, token, state, timeout, **kwargs)
            if token.split("-")[-3] == "2":
                data = json.loads(self.raw_dump)
                data["viewport"][0] = 0.1
                self.raw_dump = canonical_bytes(data)
                result["dump"]["sha256"] = digest(self.raw_dump)
                self.hook_files[result["dump"]["file"]] = self.raw_dump
            return result

    device = Unstable(inputs)
    preflight = tmp_path / "data/preflight"
    prepare_device(device, inputs, preflight)
    result = capture_manifest(
        device,
        inputs,
        tmp_path / "data/capture",
        request=device.request,
        device_plan=preflight / "device-plan.json",
    )
    assert result["status"] == "failed"
    assert all(
        c["status"] == "identical" and c["dump_status"] == "different"
        for c in result["comparisons"]
    )


@pytest.mark.skipif(
    shutil.which("node") is None,
    reason="Browser export interoperability needs host Node.js",
)
def test_browser_export_and_hash_bound_confirmation(tmp_path):
    script = (
        Path(__file__).resolve().parents[1] / "src/l10n_checker/reference_review.js"
    )
    pair = write_pair(tmp_path / "capture", dump_for())
    review = tmp_path / "review"
    review_one(pair, review)
    original = (review / "candidate.json").read_text()
    modified = json.loads(original)
    modified["rows"][0].update(text_seen="Human correction", human_edited=True)
    timing = {
        "started_at": "2026-10-21T18:00:00Z",
        "finished_at": "2026-10-21T18:01:00Z",
        "active_seconds": 45,
        "elapsed_seconds": 60,
    }
    code = """require(process.argv[1]); let input='';process.stdin.on('data',x=>input+=x);
process.stdin.on('end',async()=>{let x=JSON.parse(input);process.stdout.write(JSON.stringify(
 await ReferenceReview.exportBundle(x.original,x.modified,x.timing)));});"""
    exported = subprocess.run(
        ["node", "-e", code, str(script)],
        input=json.dumps(
            {"original": original, "modified": modified, "timing": timing}
        ),
        capture_output=True,
        text=True,
        check=True,
    )
    bundle = tmp_path / "confirmation.json"
    bundle.write_text(exported.stdout)
    result = confirm_bundle(review, bundle, tmp_path / "confirmed")
    assert result["screen_texts"] == ["Human correction"]
    assert result["status"] == "confirmed"
    tampered = json.loads(exported.stdout)
    tampered["candidate_json"] = tampered["candidate_json"].replace(
        "Human correction", "Changed later"
    )
    bundle.write_text(json.dumps(tampered))
    with pytest.raises(CaptureError, match="confirmation"):
        confirm_bundle(review, bundle, tmp_path / "bad")
    bundle.write_text(exported.stdout)
    (review / "screen.png").write_bytes(make_png(5, 2))
    with pytest.raises(CaptureError, match="hash mismatch"):
        confirm_bundle(review, bundle, tmp_path / "bad-image")


def test_previous_capture_pixel_comparison_requires_complete_hash_valid_runs(tmp_path):
    current, old = tmp_path / "current", tmp_path / "old"
    for root in (current, old):
        write_pair(root, dump_for(size=[4, 2]))
        summary = {
            "status": "complete",
            "observed_build": {"version_code": "1271045"},
            "records": [
                {
                    "screen": "tech-picker",
                    "language": "de",
                    "pass": 1,
                    "status": "captured",
                    "png": "screen.png",
                    "png_sha256": digest((root / "screen.png").read_bytes()),
                }
            ],
        }
        (root / "summary.json").write_bytes(canonical_bytes(summary))
    assert compare_capture_runs(current, old)["status"] == "identical"
    summary["status"] = "failed"
    (current / "summary.json").write_bytes(canonical_bytes(summary))
    assert compare_capture_runs(current, old)["status"] == "failed"
    (old / "screen.png").write_bytes(make_png(5, 2))
    with pytest.raises(CaptureError, match="PNG changed"):
        compare_capture_runs(current, old)


def test_review_page_escapes_text_and_starts_unconfirmed(tmp_path):
    pair = write_pair(
        tmp_path / "capture",
        dump_for(elements=[element("</script><img onerror=evil>")]),
    )
    page = review_one(pair, tmp_path / "review")
    text = page.read_text()
    assert "</script><img onerror=evil>" not in text
    assert 'id="confirm" disabled' in text
    assert "fetch(" not in text
    assert (
        b"candidate_awaiting_Anton_confirmation"
        in (page.parent / "candidate.json").read_bytes()
    )
