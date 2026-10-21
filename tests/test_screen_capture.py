"""Stage 2 transport and run contracts; no real adb, detectors or providers."""

import base64
import io
import json
import shutil
import sys
import tarfile
import threading
import time
from pathlib import Path

import pytest
from conftest import make_png
from PIL import Image

from l10n_checker import capture as legacy
from l10n_checker import cli
from l10n_checker.capture import ACTIVITY, SETTINGS_PATH, CaptureError
from l10n_checker.hook import HookFailure, Logcat, request_screen, wait_terminal
from l10n_checker.screen_capture import capture_manifest, compare_pixels, prepare_device
from l10n_checker.screen_manifest import Inputs, digest

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures/stage2"
ORIGINAL = b'{"language":"German","personal_setting":true}'


@pytest.fixture
def inputs():
    result = Inputs(FIXTURES / "screens.json")
    result.manifest = result.manifest.model_copy(update={"resolution": [4, 2]})
    return result


class FakeDevice:
    def __init__(self, inputs, fault=None):
        self.inputs = inputs
        self.settings = ORIGINAL
        self.running = False
        self.rooted = False
        self.calls = []
        self.fault = fault
        self.writes = 0
        self.starts = 0
        self.current = None
        self.saves = {"./" + name: data for name, data in inputs.fixtures.items()}
        self.saves["./unrelated-save"] = b"preserve me"

    def connect(self):
        self.calls.append("connect")

    def check_cutout(self):
        if self.fault == "cutout":
            raise CaptureError("cutout active")

    def size(self):
        return tuple(self.inputs.manifest.resolution)

    def build(self):
        return "1271045"

    def shell(self, *args):
        if args == ("pm", "path", legacy.PACKAGE):
            return "package:/data/app/base.apk\n"
        if args[0].startswith("sha256sum "):
            return (
                "bad" if self.fault == "apk" else self.inputs.manifest.build.apk_sha256
            ) + " base.apk\n"
        if args == ("wm", "density"):
            return "Physical density: 420\n"
        raise AssertionError(args)

    def root(self):
        self.calls.append("root")
        self.rooted = True
        if self.fault == "root":
            raise CaptureError("root failed halfway")

    def unroot(self):
        self.calls.append("unroot")
        self.rooted = False

    def force_stop(self):
        self.calls.append("stop")
        self.running = False

    def pid(self):
        return "123" if self.running else ""

    def stat(self, path):
        assert path == SETTINGS_PATH
        return f"10001 10001 600 {len(self.settings)}"

    def read_file(self, path):
        assert self.rooted and path == SETTINGS_PATH
        return self.settings

    def write_file(self, path, data):
        assert self.rooted and not self.running and path == SETTINGS_PATH
        self.writes += 1
        self.calls.append(("write", digest(data)))
        if self.fault == "restore" and data == ORIGINAL:
            raise CaptureError("restore failed")
        if self.fault == "write" and self.writes == 1:
            self.settings = data[:-1]
            raise CaptureError("partial write")
        self.settings = data

    def run(self, *args):
        assert args[:3] == ("exec-out", "tar", "-cf")
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w") as archive:
            for name, data in self.saves.items():
                info = tarfile.TarInfo(name)
                info.size = len(data)
                archive.addfile(info, io.BytesIO(data))
        return stream.getvalue()

    def foreground(self):
        assert self.running
        return ACTIVITY

    def screenshot(self):
        if self.fault == "png" and self.current == "tech-picker":
            return b"not PNG"
        return make_png(4, 2)

    def request(self, device, screen, token, state, timeout):
        assert device is self
        self.calls.append(
            ("request", json.loads(self.settings)["language"], screen, token)
        )
        if not self.running:
            self.starts += 1
        self.running = True
        self.current = screen
        return {"panes": list(state["scroll_to"]), "events": [], "frames": 2}


@pytest.fixture
def run_env(tmp_path, monkeypatch, inputs):
    monkeypatch.setattr(legacy, "REPO_ROOT", tmp_path)
    return FakeDevice(inputs), tmp_path / "data/run", inputs


def test_real_fixture_manifest_contract():
    inputs = Inputs(FIXTURES / "screens.json")
    assert len(inputs.manifest.screens) == 10
    assert inputs.languages(None) == ["en", "de"]
    for language in inputs.languages(None):
        for screen in inputs.screens(language):
            state = inputs.states[screen.id, language]
            expected = (
                "issue-40-belgrade-metissue-8-pair"
                if screen.id == "city-state-diplomacy"
                else "issue-8-pair"
            )
            if state["save"] is not None:
                assert state["save"] == expected
    world = next(s for s in inputs.manifest.screens if s.id == "world")
    assert "empty on turn 1" in " ".join(world.notes)
    en, de = (json.loads(inputs.settings[c]) for c in ("en", "de"))
    assert en.pop("language") == "English"
    assert de.pop("language") == "German"
    assert en == de


def edited_manifest(tmp_path):
    root = tmp_path / "fixtures"
    shutil.copytree(FIXTURES, root)
    path = root / "screens.json"
    return path, json.loads(path.read_bytes())


def test_adding_language_needs_configuration_only(tmp_path):
    path, data = edited_manifest(tmp_path)
    settings = dict(
        json.loads((path.parent / "settings/en.json").read_bytes()), language="French"
    )
    payload = json.dumps(settings).encode()
    (path.parent / "settings/fr.json").write_bytes(payload)
    data["languages"].append(
        {
            "code": "fr",
            "game_language": "French",
            "settings": "settings/fr.json",
            "sha256": digest(payload),
        }
    )
    path.write_text(json.dumps(data))
    loaded = Inputs(path)
    assert len(loaded.screens("fr")) == 10


@pytest.mark.parametrize(
    "change", ["hash", "escape", "duplicate", "unknown", "language"]
)
def test_bad_manifest_rejected_before_device_access(tmp_path, change):
    path, data = edited_manifest(tmp_path)
    if change == "hash":
        data["languages"][0]["sha256"] = "0" * 64
    elif change == "escape":
        data["languages"][0]["settings"] = "../../outside.json"
    elif change == "duplicate":
        data["screens"].append(data["screens"][0])
    elif change == "unknown":
        data["silent_override"] = True
    else:
        data["languages"][0]["game_language"] = "French"
    path.write_text(json.dumps(data))
    with pytest.raises(CaptureError):
        Inputs(path)


@pytest.mark.parametrize(
    "change",
    ["two_instructions", "missing_field", "invalid_anchor", "duplicate_json", "nan"],
)
def test_invalid_state_rejected(tmp_path, change):
    path, data = edited_manifest(tmp_path)
    entry = data["screens"][0]
    state_path = path.parent / entry["state"]
    state = json.loads(state_path.read_bytes())
    if change == "two_instructions":
        state["scroll"]["menu-map"] = {"x": 0.0, "y": 0.0}
    elif change == "missing_field":
        del state["camera"]
    elif change == "invalid_anchor":
        state["scroll_to"]["menu-map"]["technology"] = "Mining"
    elif change == "nan":
        state["scroll"]["unexpected"] = {"x": float("nan"), "y": 0}
    payload = json.dumps(state).encode()
    if change == "duplicate_json":
        payload = payload.replace(
            b'"schema_version": 1', b'"schema_version": 1, "schema_version": 1'
        )
    state_path.write_bytes(payload)
    entry["sha256"] = digest(payload)
    path.write_text(json.dumps(data))
    with pytest.raises(CaptureError):
        Inputs(path)


class FakeLog:
    def __init__(self, lines):
        self.lines = iter(lines)

    def next_line(self, deadline):
        try:
            return next(self.lines)
        except StopIteration:
            raise TimeoutError from None


def test_ready_requires_both_ids_and_complete_panes():
    log = FakeLog(
        [
            "L10N_SCREEN_READY world request=new frames=2",
            "L10N_SCREEN_ERROR tech-picker request=old reason=bad",
            "L10N_SCREEN_READY tech-picker request=old frames=2",
            "L10N_SCREEN_PANES tech-picker request=new panes=tech-tree,description",
            "L10N_SCREEN_READY tech-picker request=new frames=2",
        ]
    )
    result = wait_terminal(
        log, "tech-picker", "new", {"tech-tree", "description"}, time.monotonic() + 1
    )
    assert len(result["events"]) == 2


@pytest.mark.parametrize(
    "lines,terminal,reason",
    [
        ([], False, "client_timeout"),
        (
            ["L10N_SCREEN_ERROR world request=r reason=readiness_timeout"],
            True,
            "reason=readiness_timeout",
        ),
        (
            [
                "L10N_SCREEN_PANES world request=r panes=wrong",
                "L10N_SCREEN_READY world request=r frames=2",
            ],
            True,
            "pane_set_mismatch",
        ),
        (["L10N_SCREEN_READY world request=r frames=2"], True, "pane_set_mismatch"),
        (
            [
                "L10N_SCREEN_PANES world request=r panes=description",
                "L10N_SCREEN_READY world request=r frames=1",
            ],
            True,
            "invalid_ready_frames",
        ),
    ],
)
def test_terminal_failure_semantics(lines, terminal, reason):
    with pytest.raises(HookFailure, match=reason) as error:
        wait_terminal(
            FakeLog(lines), "world", "r", {"description"}, time.monotonic() + 1
        )
    assert error.value.terminal is terminal


def test_request_encodes_exact_three_extras(inputs):
    state = dict(
        inputs.states["tech-picker", "de"],
        selection={"technology": "Unicode Ü and spaces"},
    )
    calls = []

    class Device:
        def shell(self, *args):
            calls.append(args)
            return "Status: ok\n"

    class Log(FakeLog):
        def __init__(self, device):
            super().__init__(
                [
                    "L10N_SCREEN_PANES tech-picker request=r panes=tech-tree,description",
                    "L10N_SCREEN_READY tech-picker request=r frames=2",
                ]
            )

        def __enter__(self):
            calls.append("fresh_log")
            return self

        def __exit__(self, *_):
            pass

    request_screen(Device(), "tech-picker", "r", state, 90, log_factory=Log)
    assert calls[0] == "fresh_log"
    args = calls[1]
    extras = {args[n + 1]: args[n + 2] for n, v in enumerate(args) if v == "--es"}
    assert set(extras) == {"l10n_screen", "l10n_request", "l10n_state_b64"}
    assert (
        json.loads(base64.b64decode(extras["l10n_state_b64"], validate=True)) == state
    )


def test_logcat_barrier_discards_buffered_events_and_closes_process(monkeypatch):
    import queue

    from l10n_checker import hook

    lines = queue.Queue()
    lines.put("L10N_SCREEN_READY tech-picker request=old frames=2\n")
    stopped = threading.Event()

    class Stream:
        def __iter__(self):
            while (line := lines.get()) is not None:
                yield line

        def close(self):
            stopped.set()

    class Process:
        stdout = Stream()

        def poll(self):
            return None

        def terminate(self):
            lines.put(None)

        def wait(self, timeout):
            return 0

    process = Process()
    commands = []

    def popen(command, **kwargs):
        commands.append(command)
        return process

    monkeypatch.setattr(hook.subprocess, "Popen", popen)

    class Device:
        adb, serial = Path("sdk/adb"), "emulator-5554"

        def shell(self, *args):
            assert args[:5] == ("log", "-p", "i", "-t", "L10nCapture")
            lines.put(args[5] + "\n")

    with Logcat(Device()) as log:
        lines.put("L10N_SCREEN_READY tech-picker request=new frames=2\n")
        assert "request=new" in log.next_line(time.monotonic() + 1)
    assert stopped.is_set()
    assert commands == [["sdk/adb", "-s", "emulator-5554", "logcat", "-v", "raw"]]


def test_two_passes_reverse_all_screens_and_restore(run_env, monkeypatch):
    monkeypatch.setattr(
        legacy.time,
        "sleep",
        lambda *_: pytest.fail("fixed settle delay in manifest path"),
    )
    device, folder, inputs = run_env
    summary = capture_manifest(device, inputs, folder, request=device.request)
    assert summary["status"] == "complete"
    ids = [s.id for s in inputs.manifest.screens]
    requests = [v for v in device.calls if isinstance(v, tuple) and v[0] == "request"]
    assert [(v[1], v[2]) for v in requests] == [
        (lang, sid)
        for order in (ids, ids[::-1])
        for lang in ("English", "German")
        for sid in order
    ]
    assert len({v[3] for v in requests}) == 40
    assert device.starts == 4
    assert device.writes == 5
    assert len(list(folder.glob("pass-*/*.png"))) == 40
    assert all(c["different_pixels"] == 0 for c in summary["comparisons"])
    assert len(summary["comparisons"]) == 20
    assert device.settings == ORIGINAL and not device.rooted and not device.running
    assert summary["saves_unchanged"] and summary["settings_restored"]
    assert (folder / "private/GameSettings.json").read_bytes() == ORIGINAL
    assert len(list(folder.glob("gallery.html"))) == 1


def test_timeout_stops_before_next_request_but_keeps_other_captures(run_env):
    device, folder, inputs = run_env
    count = 0

    def request(*args):
        nonlocal count
        count += 1
        if count == 1:
            device.running = True
            raise HookFailure("client_timeout", terminal=False, events=[])
        if count == 2:
            assert not device.running
        return device.request(*args)

    summary = capture_manifest(device, inputs, folder, request=request)
    assert summary["status"] == "failed"
    assert len(summary["records"]) == 40
    assert summary["records"][0]["recovery"] == "force_stopped_before_next_request"
    assert "png" not in summary["records"][0]
    assert len(list(folder.glob("pass-*/*.png"))) == 39
    assert sum(c["status"] == "unavailable" for c in summary["comparisons"]) == 1
    assert device.settings == ORIGINAL and not device.rooted


def test_terminal_error_continues_without_png(run_env):
    device, folder, inputs = run_env

    def request(*args):
        if args[1] == "city-production":
            raise HookFailure(
                "reason=readiness_timeout", terminal=True, events=["diagnostic"]
            )
        return device.request(*args)

    summary = capture_manifest(device, inputs, folder, request=request)
    errors = [r for r in summary["records"] if r["status"] == "failed"]
    assert len(errors) == 4
    assert all(r["terminal_received"] and "png" not in r for r in errors)
    assert len(list(folder.glob("pass-*/*.png"))) == 36


@pytest.mark.parametrize("fault", ["root", "write", "restore", "png", "apk", "cutout"])
def test_faults_are_reported_and_backups_retained(run_env, fault):
    device, folder, inputs = run_env
    device.fault = fault
    summary = capture_manifest(device, inputs, folder, request=device.request)
    assert summary["status"] == "failed"
    assert not device.rooted
    if fault != "restore":
        assert device.settings == ORIGINAL
    else:
        assert (folder / "private/GameSettings.json").read_bytes() == ORIGINAL
        assert not summary.get("settings_restored")
    if fault in {"root", "write", "apk", "cutout"}:
        assert not list(folder.glob("pass-*/*.png"))


def test_prepare_only_never_writes_app_data(run_env):
    device, folder, inputs = run_env
    plan = prepare_device(device, inputs, folder)
    assert device.writes == 0 and not device.rooted and not device.running
    assert plan["app_data_writes"] == 0
    assert len(plan["planned_app_data_operations"]) == 5
    assert plan["backup"]["save_copies_needed"] == []
    assert (
        plan["planned_app_data_operations"][2]["screen_order"]
        == [s.id for s in inputs.manifest.screens][::-1]
    )


def test_missing_fixture_never_replaced(run_env):
    device, folder, inputs = run_env
    del device.saves["./issue-8-pair"]
    with pytest.raises(CaptureError, match="no save was copied"):
        prepare_device(device, inputs, folder)
    assert device.writes == 0 and not device.rooted


def test_device_plan_detects_changed_settings_before_writes(run_env):
    device, folder, inputs = run_env
    prepare_device(device, inputs, folder / "preflight")
    device.settings = b'{"language":"German","changed_after_approval":true}'
    summary = capture_manifest(
        device,
        inputs,
        folder / "capture",
        request=device.request,
        device_plan=folder / "preflight/device-plan.json",
    )
    assert summary["status"] == "failed"
    assert "changed since" in summary["fatal_error"]
    assert device.writes == 0 and not device.rooted


def test_device_plan_matches_actual_batch(run_env):
    device, folder, inputs = run_env
    prepare_device(device, inputs, folder / "preflight")
    summary = capture_manifest(
        device,
        inputs,
        folder / "capture",
        request=device.request,
        device_plan=folder / "preflight/device-plan.json",
    )
    assert summary["status"] == "complete"
    assert "device_plan_sha256" in summary


def test_existing_run_refused_and_explicit_overwrite_preserves_it(run_env):
    device, folder, inputs = run_env
    folder.mkdir(parents=True)
    (folder / "old.png").write_bytes(b"old evidence")
    with pytest.raises(CaptureError, match="already exists"):
        capture_manifest(device, inputs, folder, request=device.request)
    assert device.calls == []
    summary = capture_manifest(
        device, inputs, folder, overwrite=True, request=device.request
    )
    assert summary["status"] == "complete"
    previous = next(folder.parent.glob("run.previous-*"))
    assert (previous / "old.png").read_bytes() == b"old evidence"
    assert not (folder / "old.png").exists()


def test_pixel_comparison_counts_channels_once_and_handles_alpha(tmp_path):
    a, b = (tmp_path / name for name in ("a.png", "b.png"))
    image = Image.new("RGBA", (4, 2), (10, 20, 30, 255))
    image.save(a)
    image.putpixel((1, 0), (11, 21, 31, 255))
    image.putpixel((3, 1), (10, 20, 30, 254))
    image.save(b)
    comparison = compare_pixels(a, b)
    assert comparison["different_pixels"] == 2
    assert comparison["different_share"] == 0.25
    assert comparison["bounding_box"] == (1, 0, 4, 2)


def test_pane_mismatch_waits_for_terminal_instead_of_superseding():
    log = FakeLog(
        [
            "L10N_SCREEN_PANES world request=r panes=unexpected",
            "L10N_SCREEN_READY world request=r frames=2",
        ]
    )
    with pytest.raises(HookFailure, match="pane_set_mismatch") as error:
        wait_terminal(log, "world", "r", {"description"}, time.monotonic() + 1)
    assert error.value.terminal
    assert next(log.lines, None) is None


def test_invalid_existing_settings_prepare_fails_without_writes(run_env):
    device, folder, inputs = run_env
    device.settings = b"not JSON"
    with pytest.raises(CaptureError, match="no app data written"):
        prepare_device(device, inputs, folder)
    assert device.settings == b"not JSON"
    assert device.writes == 0 and not device.rooted


def test_nonidentical_results_not_hidden(run_env):
    device, folder, inputs = run_env
    calls = 0

    def screenshot():
        nonlocal calls
        calls += 1
        image = Image.new("RGB", (4, 2), "red" if calls <= 20 else "blue")
        output = io.BytesIO()
        image.save(output, format="PNG")
        return output.getvalue()

    device.screenshot = screenshot
    summary = capture_manifest(device, inputs, folder, request=device.request)
    assert summary["status"] == "failed"
    assert all(
        c["status"] == "different" and c["different_share"] == 1
        for c in summary["comparisons"]
    )
    assert len(list(folder.glob("pass-*/*.png"))) == 40


def test_cli_manifest_language_is_not_hardcoded(monkeypatch, capsys):
    from l10n_checker import screen_capture

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "l10n-capture",
            "--manifest",
            str(FIXTURES / "screens.json"),
            "--output-dir",
            "data/new",
            "--lang",
            "fr",
        ],
    )

    def capture(device, inputs, folder, languages, **kwargs):
        assert languages == ["fr"]
        raise CaptureError("Languages must be unique entries from the manifest")

    monkeypatch.setattr(screen_capture, "capture_manifest", capture)
    assert cli.main() == 1
    assert "manifest" in capsys.readouterr().err


@pytest.mark.parametrize("option", ["--settle", "--variant"])
def test_cli_rejects_legacy_options_with_manifest(monkeypatch, option):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "l10n-capture",
            "--manifest",
            "x.json",
            "--output-dir",
            "data/new",
            option,
            "1",
        ],
    )
    with pytest.raises(SystemExit):
        cli.main()
