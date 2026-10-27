"""Synthetic engine draws and fake transports; never device/provider evidence."""

import base64
import json
import shutil
import subprocess
import time
from pathlib import Path

import pytest
from conftest import make_png
from test_screen_capture import FIXTURES, FakeDevice, FakeLog

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
        return result

    def run(self, *args):
        if args[:4] == ("exec-out", "run-as", legacy.PACKAGE, "cat"):
            return b"broken" if self.fault == "dump" else self.raw_dump
        return super().run(*args)


def test_complete_fake_v2_capture_and_changed_dump_failures(tmp_path, monkeypatch):
    monkeypatch.setattr(legacy, "REPO_ROOT", tmp_path)
    inputs = Inputs(FIXTURES / "screens.json")
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
    monkeypatch.setattr(legacy, "REPO_ROOT", tmp_path)
    inputs = Inputs(FIXTURES / "screens.json")
    inputs.manifest = inputs.manifest.model_copy(update={"protocol_version": 2})
    device = DumpDevice(inputs)
    with pytest.raises(CaptureError, match="exact device plan"):
        capture_manifest(device, inputs, tmp_path / "data/run")
    assert device.calls == []


@pytest.mark.parametrize("change", ["missing_directory", "directory", "temporary"])
def test_v2_changed_output_write_plan_is_rejected_before_device_access(
    tmp_path, monkeypatch, change
):
    monkeypatch.setattr(legacy, "REPO_ROOT", tmp_path)
    inputs = Inputs(FIXTURES / "screens.json")
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
    monkeypatch.setattr(legacy, "REPO_ROOT", tmp_path)
    inputs = Inputs(FIXTURES / "screens.json")
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
