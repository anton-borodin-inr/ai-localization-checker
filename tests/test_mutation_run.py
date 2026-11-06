"""Runtime pair authorization and immutable split handoff, without real devices."""

import importlib
import importlib.util
from pathlib import Path

import pytest
from test_mutation_catalog import synthetic_catalog
from test_text_dump import dump_for, write_pair

from l10n_checker.capture import CaptureError
from l10n_checker.screen_manifest import Inputs, digest, json_bytes
from l10n_checker.text_dump import canonical_bytes

MANIFEST = Path(__file__).resolve().parents[1] / "fixtures/stage2/screens-v2.json"


@pytest.fixture(autouse=True)
def forbid_unstubbed_native_commands(monkeypatch):
    import subprocess

    def forbidden(*args, **kwargs):
        pytest.fail("Unstubbed native command forbidden in host-only mutation tests")

    monkeypatch.setattr(subprocess, "run", forbidden)


def api():
    assert importlib.util.find_spec("l10n_checker.mutation_run") is not None, (
        "Mutation runner missing"
    )
    return importlib.import_module("l10n_checker.mutation_run")


@pytest.fixture(scope="module")
def synthetic_completed_runtime(tmp_path_factory):
    """Synthetic unsigned APKs/dumps and in-memory device; never device evidence."""
    import io
    import subprocess
    import tarfile
    import zipfile
    from types import SimpleNamespace

    from test_text_dump import element

    from l10n_checker.capture import SETTINGS_PATH
    from l10n_checker.mutation_catalog import read_catalog
    from l10n_checker.mutation_device import DATA_ROOTS
    from l10n_checker.screen_capture import (
        HOOK_DIRECTORY_OPERATION,
        planned_hook_outputs,
        planned_operations,
    )

    runtime = api()
    root = tmp_path_factory.mktemp("synthetic-runtime").resolve()
    source = root / "source"
    source.mkdir()
    path, kwargs, _, _ = synthetic_catalog(source)
    catalog = read_catalog(path, digest(path.read_bytes()), **kwargs)
    inputs = Inputs(MANIFEST, split="dev").with_build(
        {
            **Inputs(MANIFEST, split="dev").manifest.build.model_dump(),
            "apk_sha256": catalog.data["reference"]["apk"]["sha256"],
        }
    )
    inputs.source_manifest_sha256 = catalog.data["inputs"]["manifest"]["sha256"]

    settings_raw = b'{"language":"English","synthetic":true}\n'
    settings_stat = f"10001 10001 600 {len(settings_raw)}"

    def archive(files):
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w") as tar:
            for name, raw in files.items():
                item = tarfile.TarInfo("./" + name)
                item.size = len(raw)
                item.uid = item.gid = 10001
                item.mode = 0o600
                tar.addfile(item, io.BytesIO(raw))
        return stream.getvalue()

    saves = archive(inputs.fixtures)
    app_files = {
        "private": {"files/GameSettings.json": settings_raw},
        "external": {
            "files/SaveFiles/" + name: raw for name, raw in inputs.fixtures.items()
        },
        "device_encrypted": {"synthetic": b"unchanged"},
    }

    def snapshot(folder):
        private = folder / "private"
        private.mkdir()
        (private / "GameSettings.json").write_bytes(settings_raw)
        (private / "SaveFiles.tar").write_bytes(saves)
        return {
            "settings_sha256": digest(settings_raw),
            "settings_stat": settings_stat,
            "settings_backup": "private/GameSettings.json",
            "saves_backup": "private/SaveFiles.tar",
            "saves": {
                "./" + name: digest(raw) for name, raw in inputs.fixtures.items()
            },
            "save_copies_needed": [],
        }

    class SyntheticDevice:
        serial = "emulator-5554"

        def __init__(self, volatile=False, transform=None):
            self.apk = catalog.apk_path(
                {"apk": catalog.data["reference"]["apk"]}
            ).read_bytes()
            self.calls = []
            self.volatile, self.transform, self.inventory_number = (
                volatile,
                transform,
                0,
            )

        def run(self, *args):
            self.calls.append(args)
            if args == ("devices",):
                return b"List of devices attached\nemulator-5554\tdevice\n"
            if args[:3] == ("install", "-r", "-d"):
                self.apk = Path(args[3]).read_bytes()
                return b"Success\n"
            if args[:2] == ("exec-out", "cat"):
                return self.apk
            if args[:2] == ("exec-out", "tar"):
                from test_mutation_device import BOOKKEEPING

                name = next(
                    name for name, path in DATA_ROOTS.items() if path == args[-2]
                )
                if name == "private":
                    self.inventory_number += 1
                files = dict(app_files[name])
                if self.volatile and name == "private":
                    files.update(
                        {
                            p: f"synthetic bookkeeping {self.inventory_number}".encode()
                            for i, p in enumerate(BOOKKEEPING)
                            if (self.inventory_number + i) % 3 != 0
                        }
                    )
                if self.transform:
                    self.transform(name, self.inventory_number, files)
                return archive(files)
            pytest.fail(f"Unexpected synthetic device command: {args}")

        def shell(self, *args):
            if args[:2] == ("pm", "path"):
                return "package:/data/app/synthetic/base.apk"
            assert len(args) == 1 and args[0].startswith("if [ -d ")
            return "present"

        def build(self):
            import io

            with zipfile.ZipFile(io.BytesIO(self.apk)) as apk:
                return apk.read("AndroidManifest.xml").decode()

        def pid(self):
            return ""

        def connect(self):
            pass

        def force_stop(self):
            pass

        def root(self):
            pass

        def unroot(self):
            pass

    def native(command, **kwargs):
        if command == ["pgrep", "-fl", "l10n-capture"]:
            return SimpleNamespace(returncode=1, stdout=b"", stderr=b"")
        assert Path(command[0]).name == "check_env.sh", "Real native command forbidden"
        return SimpleNamespace(
            returncode=0, stdout=b"synthetic environment check", stderr=b""
        )

    def prepare(device, effective, folder, languages):
        folder.mkdir(parents=True)
        backup = snapshot(folder)
        plan = {
            "mode": "prepare_only",
            "app_data_writes": 0,
            "manifest_sha256": effective.sha256,
            "selection": effective.capture_selection(languages),
            "observed_build": {
                "version_code": effective.manifest.build.version_code,
                "apk_sha256": effective.manifest.build.apk_sha256,
                "density_dpi": effective.manifest.density_dpi,
            },
            "backup": backup,
            "serial": device.serial,
            "request_namespace": "c" * 32,
            "planned_app_data_operations": planned_operations(
                effective, languages, digest(settings_raw)
            ),
            "planned_hook_directory_operation": HOOK_DIRECTORY_OPERATION,
            "planned_hook_output_operations": planned_hook_outputs(
                effective, languages, "c" * 32
            ),
        }
        (folder / "device-plan.json").write_bytes(canonical_bytes(plan))
        return plan

    def capture(
        device, effective, folder, languages, *, on_pair, variant, device_plan, **kwargs
    ):
        folder.mkdir()
        backup = snapshot(folder)
        plan = json_bytes(device_plan.read_bytes())
        output_map = {
            (o["screen"], o["language"], o["pass"]): o
            for o in plan["planned_hook_output_operations"]
        }
        operations = []
        records = []
        for n in (1, 2):
            for language, game_language in (("en", "English"), ("de", "German")):
                operations.append(
                    {
                        "operation": "replace_settings",
                        "path": SETTINGS_PATH,
                        "sha256": digest(effective.settings[language]),
                        "status": "verified",
                        "language": language,
                        "pass_number": n,
                    }
                )
                for screen in effective.screens(reverse=n == 2):
                    elements = []
                    if (screen.id, language) == ("tech-picker", "en"):
                        mutated = variant != "clean"
                        elements = [
                            element(
                                "Mining..." if mutated else "Mining",
                                "root/mining",
                                input_text="Mining and ore extraction"
                                if mutated
                                else "Mining",
                                source_key=None,
                                ellipsis_applied=mutated,
                            )
                        ]
                    dump = dump_for(
                        screen=screen.id,
                        language=game_language,
                        state=effective.states[screen.id, language],
                        elements=elements,
                    )
                    dump["build_version_code"] = int(
                        effective.manifest.build.version_code
                    )
                    pair_path = write_pair(folder / f"{screen.id}-{language}-{n}", dump)
                    pair = json_bytes(pair_path.read_bytes())
                    pair["build"] = effective.manifest.build.model_dump()
                    pair_path.write_bytes(canonical_bytes(pair))
                    output = output_map[screen.id, language, n]
                    record = {
                        "screen": screen.id,
                        "language": language,
                        "pass": n,
                        "pair": str(pair_path.relative_to(folder)),
                        "status": "captured",
                        "request": output["request"],
                        "state": effective.states[screen.id, language],
                        "png": str(
                            (pair_path.parent / pair["png"]).relative_to(folder)
                        ),
                        "dump": str(
                            (pair_path.parent / pair["dump"]).relative_to(folder)
                        ),
                        **{
                            key: pair[key]
                            for key in ("png_sha256", "rgba_sha256", "dump_sha256")
                        },
                    }
                    if not records:
                        operations.append(
                            {**HOOK_DIRECTORY_OPERATION, "status": "verified_present"}
                        )
                    operations.append(
                        {
                            "operation": "hook_output",
                            **output,
                            "status": "verified",
                            "sha256": pair["dump_sha256"],
                        }
                    )
                    records.append(record)
                    on_pair(record)
        operations.append(
            {
                "operation": "restore_original_settings",
                "path": SETTINGS_PATH,
                "sha256": digest(settings_raw),
                "status": "verified",
            }
        )
        summary = {
            "schema_version": 1,
            "status": "complete",
            "settings_restored": True,
            "saves_unchanged": True,
            "records": records,
            "backup": backup,
            "manifest_sha256": effective.sha256,
            "selection": plan["selection"],
            "languages": languages,
            "passes": ["forward", "reverse"],
            "device_plan_sha256": digest(device_plan.read_bytes()),
            "observed_build": plan["observed_build"],
            "planned_app_data_operations": plan["planned_app_data_operations"],
            "app_data_operations": operations,
            "live_provider_requests": 0,
            "api_spend_usd": 0,
            "comparisons": [
                {
                    "screen": s.id,
                    "language": language,
                    "status": "identical",
                    "dump_status": "identical",
                    "different_pixels": 0,
                    "total_pixels": effective.manifest.resolution[0]
                    * effective.manifest.resolution[1],
                    "different_share": 0.0,
                    "bounding_box": None,
                    "bounding_box_convention": "[left, top, right-exclusive, bottom-exclusive] or null",
                }
                for language in languages
                for s in effective.screens(language)
            ],
        }
        (folder / "summary.json").write_bytes(canonical_bytes(summary))
        return summary

    def execute(
        name,
        *,
        volatile=False,
        transform=None,
        probe_only=False,
        measurement_only=False,
        capture_wrapper=None,
        configure=None,
    ):
        device = SyntheticDevice(volatile, transform)
        with pytest.MonkeyPatch.context() as monkeypatch:
            monkeypatch.setattr(subprocess, "run", native)
            monkeypatch.setattr(runtime, "prepare_device", prepare)
            monkeypatch.setattr(
                runtime,
                "capture_manifest",
                capture_wrapper(capture) if capture_wrapper else capture,
            )
            run = runtime.MutationRun(
                catalog,
                inputs,
                root / "outputs" / name,
                approved_root=root / "outputs",
                device=device,
                tools=kwargs["tools"],
                **({"measurement_only": True} if measurement_only else {}),
            )
            if configure:
                configure(run)
            options = {"probe_only": probe_only}
            if measurement_only:
                options["measurement_only"] = True
            result = run.run(**options)
        return run, result

    run, result = execute("synthetic-run")
    probe, probe_result = execute("synthetic-probe", probe_only=True)
    assert result["status"] == "qualified", run.journal
    assert probe_result["status"] == "probe_verified", probe.journal
    assert result["capture_set_qualified"] is True and result["labels_created"] is False
    assert run.device.build() == probe.device.build() == "1271048"
    assert (
        len(result["screenshots"]) == len(runtime.expected_capture_keys(catalog)) == 60
    )
    return {
        "completed": (run.folder, catalog, inputs, result),
        "probe": (probe.folder, catalog, inputs, probe_result),
        "execute": execute,
    }


@pytest.fixture(params=["completed"])
def synthetic_runtime(synthetic_completed_runtime, tmp_path, request):
    import shutil

    folder, catalog, inputs, result = synthetic_completed_runtime[request.param]
    target = tmp_path.resolve() / "synthetic-run"
    shutil.copytree(folder, target)
    return target, catalog, inputs, result


def reindex_synthetic(folder, version=None):
    if version is None:
        manifest = json_bytes((folder / "mutation-manifest.json").read_bytes())
        version = {4: 5, 3: 4}.get(manifest["mutation_run_version"], 3)
    files = {
        str(p.relative_to(folder)): digest(p.read_bytes())
        for p in folder.rglob("*")
        if p.is_file() and p != folder / "evidence-index.json"
    }
    raw = canonical_bytes({"version": version, "files": files})
    (folder / "evidence-index.json").write_bytes(raw)
    return digest(raw)


def d053_capture(
    capture,
    *,
    affected=(("tech-picker", "en"),),
    fault=None,
    roles=("calibration", "mutation"),
    rgb_delta=2,
):
    """Authentic synthetic PNG/dump/pair bytes, with nonzero exact RGBA values."""
    import io

    from PIL import Image
    from test_text_dump import element

    from l10n_checker.text_dump import rgba_digest

    def wrapped(device, effective, folder, languages, *, on_pair, variant, **kwargs):
        def measured(record):
            path = folder / record["pair"]
            pair = json_bytes(path.read_bytes())
            dump_path = path.parent / pair["dump"]
            dump = json_bytes(dump_path.read_bytes())
            box = [200, 100, 220, 120]
            glyph = element(
                "Stable",
                "root/stable",
                input_text="Stable",
                source_key=None,
                bounds=[198, 98, 222, 122],
                glyph_bounds=box,
                visible_bounds=box,
                ellipsis_applied=False,
            )
            for line in glyph["lines"]:
                line["bounds"] = box
                for g in line["glyphs"]:
                    g["bounds"] = g["visible_bounds"] = box
            if fault == "unmutated" and variant in roles:
                glyph["font_scale"] = [0.19, 0.19]
            dump["elements"].append(glyph)
            dump_path.write_bytes(
                canonical_bytes(dump)
                + (b"\n" if fault == "raw_dump_repeat" and record["pass"] == 2 else b"")
            )
            pair["dump_sha256"] = record["dump_sha256"] = digest(dump_path.read_bytes())
            png_path = path.parent / pair["png"]
            with Image.open(io.BytesIO(png_path.read_bytes())) as source:
                image = source.convert("RGBA")
            image.putpixel((201, 101), (40, 50, 60, 255))
            image.putpixel((202, 101), (40, 50, 60, 255))
            selected = (record["screen"], record["language"]) in affected
            if variant in roles and selected:
                xy = (
                    (202, 101)
                    if fault == "coordinates" and record["pass"] == 2
                    else (199, 101)
                    if fault == "owner_only"
                    else (0, 0)
                    if fault == "elsewhere"
                    else (201, 101)
                )
                value = (40 + rgb_delta, 49, 61, 254 if fault == "alpha" else 255)
                if fault == "values" and record["pass"] == 2:
                    value = (41, 49, 61, 255)
                image.putpixel(xy, value)
                if (record["screen"], record["language"]) == ("tech-picker", "en"):
                    image.putpixel((11, 21), (80, 90, 100, 255))
            image.save(png_path)
            raw = png_path.read_bytes()
            pair["png_sha256"] = record["png_sha256"] = digest(raw)
            pair["rgba_sha256"] = record["rgba_sha256"] = rgba_digest(raw)
            path.write_bytes(canonical_bytes(pair))
            if (
                fault != "missing_reverse"
                or variant not in roles
                or record["pass"] != 2
            ):
                on_pair(record)

        summary = capture(
            device,
            effective,
            folder,
            languages,
            on_pair=measured,
            variant=variant,
            **kwargs,
        )
        hashes = {r["request"]: r["dump_sha256"] for r in summary["records"]}
        for operation in summary["app_data_operations"]:
            if operation["operation"] == "hook_output":
                operation["sha256"] = hashes[operation["request"]]
        (folder / "summary.json").write_bytes(canonical_bytes(summary))
        return summary

    return wrapped


@pytest.fixture(scope="module")
def d053_runtime(synthetic_completed_runtime):
    checkpoints = []

    def configure(run):
        checkpoint = run.checkpoint

        def observed():
            checkpoint()
            if any(
                s["role"] == "calibration"
                and s["pass"] == 1
                and s["screen"] == "tech-picker"
                for s in run.content["screenshots"]
            ):
                checkpoints.append(
                    json_bytes((run.folder / "mutation-manifest.json").read_bytes())
                )

        run.checkpoint = observed

    run, result = synthetic_completed_runtime["execute"](
        "d054-large-rgb",
        capture_wrapper=lambda capture: d053_capture(capture, rgb_delta=47),
        configure=configure,
    )
    return run, result, checkpoints


def test_d053_exact_nonzero_rule_keeps_strict_failure_and_pass1_pending(d053_runtime):
    run, result, checkpoints = d053_runtime
    assert result["status"] == "qualified", run.journal
    assert result["mutation_run_version"] == 4
    assert json_bytes((run.folder / "evidence-index.json").read_bytes())["version"] == 5
    assert result["outside_rule_policy"]["decision"] == "D054"
    assert result["outside_rule_policy"]["version"] == 2
    assert result["outside_rule_policy"]["max_rgb_delta"] is None
    used = [s for s in result["screenshots"] if s["outside_rule"]["used"]]
    assert len(used) == 4
    assert all(
        s["verification"]["passed"] is False and s["qualified"] is True for s in used
    )
    assert all(
        s["outside_rule"]["assessment"]["outside"]["max_channel_deltas"]
        == [47, 1, 1, 0]
        for s in used
    )
    assert all(
        s["outside_rule"]["assessment"]["affected_elements"][0]["actor_path"]
        == "root/stable"
        for s in used
    )
    pending = [
        s
        for c in checkpoints
        for s in c["screenshots"]
        if s["role"] == "calibration"
        and s["outside_rule"]["repeat_state"] == "pending"
        and s["outside_rule"]["assessment"]["rule_needed"]
    ]
    assert pending and all(
        s["qualified"] is False and s["outside_rule"]["used"] is False for s in pending
    )
    assert result["outside_rule_usage"]["global"]["used_frames"] == 4
    assert result["outside_rule_usage"]["global"]["used_unique_pairs"] == 2
    assert not result["outside_rule_usage"]["engineering_pauses"]
    assert (
        api().verify_run(
            run.folder,
            run.catalog,
            run.inputs,
            evidence_sha256=result["evidence_sha256"],
        )["status"]
        == "qualified"
    )


def test_d053_runtime_rederives_raw_dump_repeat_despite_complete_summary(
    synthetic_completed_runtime,
):
    run, result = synthetic_completed_runtime["execute"](
        "d053-raw-repeat",
        capture_wrapper=lambda capture: d053_capture(capture, fault="raw_dump_repeat"),
    )
    assert result["status"] == "failed", (
        "Same-build raw dump repeat cannot be relaxed by D053"
    )
    assert result["restoration_verified"] and not result["capture_set_qualified"]
    assert not any(s["role"] != "clean" for s in result["screenshots"])
    assert "repeat" in run.journal["error"].lower()
    retained = json_bytes((run.folder / "mutation-manifest.json").read_bytes())
    assert result["calibration_status"] == retained["calibration_status"] == "not_run"
    assert (
        api().verify_run(
            run.folder,
            run.catalog,
            run.inputs,
            evidence_sha256=result["evidence_sha256"],
        )["calibration_status"]
        == "not_run"
    )


@pytest.mark.parametrize(
    "fault",
    [
        "coordinates",
        "values",
        "alpha",
        "owner_only",
        "elsewhere",
        "unmutated",
        "missing_reverse",
        "measurement",
    ],
)
def test_d053_runtime_fatal_stops_never_split(
    synthetic_completed_runtime, monkeypatch, fault
):
    if fault == "measurement":
        monkeypatch.setattr(
            api(), "assess_outside_rule", lambda *args: {"measurements_complete": False}
        )
    run, result = synthetic_completed_runtime["execute"](
        "d053-fatal-" + fault,
        capture_wrapper=lambda capture: d053_capture(
            capture, fault=fault, rgb_delta=47
        ),
    )
    assert result["status"] == "failed" and result["capture_set_qualified"] is False
    assert result["calibration_status"] == "failed"
    assert result["restoration_verified"] and run.device.build() == "1271048"
    assert not result["dynamic_tests"] and not (run.folder / "builder-handoff").exists()
    assert not any(s["role"] == "mutation" for s in result["screenshots"])
    assert "outside-rule" in run.journal["error"].lower()
    assert result["outside_rule_usage"]["engineering_pauses"] == []
    if fault == "missing_reverse":
        assert result["outside_rule_usage"]["global"]["pending_frames"] == 1


def test_d053_probe_failure_leaves_calibration_not_run(synthetic_completed_runtime):
    def configure(run):
        def failed_probe():
            raise CaptureError("synthetic probe failed before captures")

        run.probe = failed_probe

    run, result = synthetic_completed_runtime["execute"](
        "d053-probe-status", configure=configure
    )
    retained = json_bytes((run.folder / "mutation-manifest.json").read_bytes())
    assert result["status"] == "failed" and result["restoration_verified"] is True
    assert result["capture_set_qualified"] is False and result["screenshots"] == []
    assert result["calibration_status"] == retained["calibration_status"] == "not_run"
    assert (
        api().verify_run(
            run.folder,
            run.catalog,
            run.inputs,
            evidence_sha256=result["evidence_sha256"],
        )["calibration_status"]
        == "not_run"
    )


@pytest.fixture(scope="module", params=["alpha", "values", "missing_reverse"])
def d053_failed_calibration(synthetic_completed_runtime, request):
    return synthetic_completed_runtime["execute"](
        "d053-calibration-status-" + request.param,
        capture_wrapper=lambda capture: d053_capture(
            capture, fault=request.param, rgb_delta=47
        ),
    )


def test_d053_attempted_calibration_failure_is_retained_and_replayed(
    d053_failed_calibration,
):
    run, result = d053_failed_calibration
    assert any(s["role"] == "calibration" for s in result["screenshots"])
    assert result["calibration_status"] == "failed"
    assert result["status"] == "failed" and result["capture_set_qualified"] is False
    assert result["restoration_verified"] is True
    assert result["dynamic_tests"] == []
    assert not any(s["role"] == "mutation" for s in result["screenshots"])
    assert not (run.folder / "builder-handoff").exists()
    retained = json_bytes((run.folder / "mutation-manifest.json").read_bytes())
    assert retained["calibration_status"] == "failed"
    replay = api().verify_run(
        run.folder,
        run.catalog,
        run.inputs,
        evidence_sha256=result["evidence_sha256"],
    )
    assert replay["calibration_status"] == "failed"
    assert replay["status"] == "failed" and replay["capture_set_qualified"] is False


def test_d053_rehashed_not_run_cannot_hide_authenticated_calibration_frames(
    d053_failed_calibration,
    tmp_path,
):
    import shutil

    run, _ = d053_failed_calibration
    folder = tmp_path / "hidden-calibration-attempt"
    shutil.copytree(run.folder, folder)
    value = json_bytes((folder / "mutation-manifest.json").read_bytes())
    assert any(s["role"] == "calibration" for s in value["screenshots"])
    value["calibration_status"] = "not_run"
    rewrite_synthetic_manifest(folder, value)
    with pytest.raises(CaptureError, match="[Cc]alibration.*attempt"):
        api().verify_run(
            folder,
            run.catalog,
            run.inputs,
            evidence_sha256=reindex_synthetic(folder),
        )


def test_d053_calibration_failure_before_first_frame_is_proved_by_capture_summary(
    synthetic_completed_runtime,
    tmp_path,
):
    import shutil

    from l10n_checker import screen_capture

    def capture_wrapper(capture):
        def wrapped(*args, variant, **kwargs):
            if variant != "calibration":
                return capture(*args, variant=variant, **kwargs)

            def failed_build(*args):
                raise CaptureError("synthetic calibration build transport failed")

            with pytest.MonkeyPatch.context() as patch:
                patch.setattr(screen_capture, "check_build", failed_build)
                return screen_capture.capture_manifest(*args, variant=variant, **kwargs)

        return wrapped

    run, result = synthetic_completed_runtime["execute"](
        "d053-calibration-before-frame",
        capture_wrapper=capture_wrapper,
    )
    assert result["status"] == result["calibration_status"] == "failed"
    assert result["restoration_verified"] is True
    assert result["capture_set_qualified"] is False and not result["dynamic_tests"]
    assert all(s["role"] == "clean" for s in result["screenshots"])
    root = api().capture_directory(
        run.folder, run.catalog.calibration["request"]["id"], "calibration"
    )
    summary = json_bytes((root / "capture/summary.json").read_bytes())
    assert summary["status"] == "failed" and summary["records"] == []
    assert summary["fatal_error"] == "synthetic calibration build transport failed"
    assert (
        api().verify_run(
            run.folder,
            run.catalog,
            run.inputs,
            evidence_sha256=result["evidence_sha256"],
        )["calibration_status"]
        == "failed"
    )
    folder = tmp_path / "hidden-calibration-summary"
    shutil.copytree(run.folder, folder)
    value = json_bytes((folder / "mutation-manifest.json").read_bytes())
    value["calibration_status"] = "not_run"
    rewrite_synthetic_manifest(folder, value)
    with pytest.raises(CaptureError, match="[Cc]alibration.*attempt"):
        api().verify_run(
            folder,
            run.catalog,
            run.inputs,
            evidence_sha256=reindex_synthetic(folder),
        )


@pytest.mark.parametrize("role", ["calibration", "mutation"])
def test_d053_high_usage_pauses_at_completed_batch_without_control_dilution(
    synthetic_completed_runtime, role
):
    run, result = synthetic_completed_runtime["execute"](
        "d053-high-" + role,
        capture_wrapper=lambda capture: d053_capture(
            capture,
            affected=(("tech-picker", "en"), ("tech-picker", "de")),
            roles=(role,),
        ),
    )
    assert result["status"] == "failed" and not result["capture_set_qualified"]
    pauses = result["outside_rule_usage"]["engineering_pauses"]
    assert len(pauses) == 1 and pauses[0]["role"] == role
    assert pauses[0]["used_frames"] == 4 and pauses[0]["expected_frames"] == 20
    assert "engineering pause" in run.journal["error"]
    assert (
        result["restoration_verified"] and not (run.folder / "builder-handoff").exists()
    )
    if role == "calibration":
        assert not any(s["role"] == "mutation" for s in result["screenshots"])
    expected_calibration = "failed" if role == "calibration" else "passed"
    retained = json_bytes((run.folder / "mutation-manifest.json").read_bytes())
    assert result["calibration_status"] == expected_calibration
    assert retained["calibration_status"] == expected_calibration
    replay = api().verify_run(
        run.folder,
        run.catalog,
        run.inputs,
        evidence_sha256=result["evidence_sha256"],
    )
    assert replay["status"] == "failed"
    assert replay["calibration_status"] == expected_calibration


@pytest.mark.parametrize(
    "kind",
    [
        "policy_missing",
        "policy_delta",
        "policy_2",
        "policy_47",
        "policy_255",
        "policy_identity",
        "policy_version",
        "d053_policy",
        "policy_bool",
        "usage_missing",
        "usage_count",
        "proof_missing",
        "assessment",
        "pixels",
        "ids",
        "set_hash",
        "values_hash",
        "repeat",
        "binding",
        "used",
        "qualification",
        "version",
        "index",
        "both_versions",
        "d053_version",
        "d053_index",
        "d053_both_versions",
        "producer",
    ],
)
def test_d053_rehashed_proof_policy_usage_and_version_tampering_rejected(
    d053_runtime, tmp_path, kind
):
    import shutil

    run, _, _ = d053_runtime
    folder = tmp_path / "d053-copy"
    shutil.copytree(run.folder, folder)
    value = json_bytes((folder / "mutation-manifest.json").read_bytes())
    shot = next(s for s in value["screenshots"] if s["outside_rule"]["used"])
    proof = shot["outside_rule"]
    version = 5
    if kind == "policy_missing":
        value.pop("outside_rule_policy")
    elif kind == "policy_delta":
        value["outside_rule_policy"]["max_rgb_delta"] = 3
    elif kind in {"policy_2", "policy_47", "policy_255"}:
        value["outside_rule_policy"]["max_rgb_delta"] = int(kind.split("_")[1])
    elif kind == "policy_identity":
        value["outside_rule_policy"]["decision"] = "D053"
    elif kind == "policy_version":
        value["outside_rule_policy"]["version"] = 1
    elif kind == "d053_policy":
        value["outside_rule_policy"].update(decision="D053", version=1, max_rgb_delta=2)
        for screenshot in value["screenshots"]:
            assessment = screenshot["outside_rule"]["assessment"]
            if assessment is not None:
                assessment["policy"] = dict(value["outside_rule_policy"])
    elif kind == "policy_bool":
        value["outside_rule_policy"]["version"] = True
    elif kind == "usage_missing":
        value.pop("outside_rule_usage")
    elif kind == "usage_count":
        value["outside_rule_usage"]["global"]["used_frames"] = 0
    elif kind == "proof_missing":
        shot.pop("outside_rule")
    elif kind == "assessment":
        proof["assessment"]["local_criteria_passed"] = False
    elif kind == "pixels":
        proof["assessment"]["outside"]["different_pixels"] = 0
    elif kind == "ids":
        proof["assessment"]["affected_elements"][0]["before_draw_id"] = (
            "inferred-parent"
        )
    elif kind in {"set_hash", "values_hash"}:
        proof["assessment"][
            "outside_pixel_" + ("set" if kind == "set_hash" else "values") + "_sha256"
        ] = "0" * 64
    elif kind == "repeat":
        proof["repeat"]["passed"] = False
    elif kind == "binding":
        proof["pair_binding"]["reverse"]["control_pair_sha256"] = "0" * 64
    elif kind == "used":
        proof["used"] = False
    elif kind == "qualification":
        shot["qualified"] = 1
    elif kind == "producer":
        value["implementation_hashes"].pop("mutation_diagnostics.py")
    else:
        if kind in {"version", "both_versions"}:
            value["mutation_run_version"] = 2
        if kind in {"index", "both_versions"}:
            version = 3
        if kind in {"d053_version", "d053_both_versions"}:
            value["mutation_run_version"] = 3
        if kind in {"d053_index", "d053_both_versions"}:
            version = 4
    rewrite_synthetic_manifest(folder, value)
    with pytest.raises(CaptureError, match="[Oo]utside|Legacy"):
        api().verify_run(
            folder,
            run.catalog,
            run.inputs,
            evidence_sha256=reindex_synthetic(folder, version),
        )


@pytest.mark.parametrize(
    "producer",
    [
        "mutation_run.py",
        "mutation_catalog.py",
        "mutation_device.py",
        "mutation_verify.py",
        "mutation_outside_rule.py",
        "mutation_diagnostics.py",
        "mutation_cli.py",
        "mutation_plan.py",
        "mutation_recipes.py",
        "screen_manifest.py",
        "screen_capture.py",
        "hook.py",
        "text_dump.py",
        "text_reference.py",
        "capture.py",
    ],
)
@pytest.mark.parametrize("forged", ["0" * 64, True], ids=["wrong-value", "bool"])
def test_d053_rehashed_matching_producer_claims_require_current_values(
    d053_runtime, tmp_path, producer, forged
):
    import shutil

    run, _, _ = d053_runtime
    folder = tmp_path / "forged-producer"
    shutil.copytree(run.folder, folder)
    value = json_bytes((folder / "mutation-manifest.json").read_bytes())
    journal_path = folder / "journal.json"
    journal = json_bytes(journal_path.read_bytes())
    assert value["implementation_hashes"] == api().implementation_hashes()
    assert value["implementation_hashes"][producer] != forged
    value["implementation_hashes"][producer] = forged
    journal["implementation_hashes"] = dict(value["implementation_hashes"])
    rewrite_synthetic_manifest(folder, value)
    journal_path.write_bytes(canonical_bytes(journal))
    with pytest.raises(CaptureError, match="producer implementation hashes mismatch"):
        api().verify_run(
            folder,
            run.catalog,
            run.inputs,
            evidence_sha256=reindex_synthetic(folder),
        )


def test_d053_measurement_requested_at_run_entry_remains_old_strict_mode(
    synthetic_completed_runtime,
):
    from functools import partial

    def configure(run):
        run.run = partial(run.run, measurement_only=True)

    error = None
    completed = None
    try:
        completed = synthetic_completed_runtime["execute"](
            "d053-measure-at-run", configure=configure
        )
    except (KeyError, CaptureError) as exc:
        error = exc
    assert error is None, (
        f"Run-entry measurement must not inherit normal D053 proofs: {error}"
    )
    assert completed is not None
    run, result = completed
    assert result["mutation_run_version"] == 2
    assert (
        result["measurement_complete"] is True and not result["capture_set_qualified"]
    )
    assert "outside_rule_policy" not in result and "outside_rule_usage" not in result
    assert json_bytes((run.folder / "evidence-index.json").read_bytes())["version"] == 3
    assert all("outside_rule" not in s for s in result["screenshots"])
    assert (
        api().verify_run(
            run.folder,
            run.catalog,
            run.inputs,
            evidence_sha256=result["evidence_sha256"],
        )["measurement_complete"]
        is True
    )


def test_d053_usage_counts_needed_even_when_measurement_is_missing():
    from types import SimpleNamespace

    catalog = SimpleNamespace(
        control={"request": {"id": "control"}},
        calibration={"request": {"id": "calibration"}},
        plan={"screen_ids": ["one", "two", "three", "four", "five"], "batches": []},
    )
    shot = {
        "batch_id": "calibration",
        "role": "calibration",
        "screen": "one",
        "language": "en",
        "pass": 1,
        "verification": {"pixels": {"outside": {"different_pixels": 1}}},
        "outside_rule": {"assessment": None, "used": False, "repeat_state": "failed"},
    }
    usage = api().outside_usage(catalog, [shot], "failed")
    assert usage["global"]["needed_frames"] == 1
    assert usage["global"]["missing_measurement_frames"] == 1
    assert usage["global"]["used_frames"] == 0
    assert usage["global"]["expected_frames"] == 20
    assert usage["engineering_pauses"] == []


def test_d053_zero_usage_denominator_is_undefined():
    from types import SimpleNamespace

    catalog = SimpleNamespace(
        control={"request": {"id": "control"}},
        calibration={"request": {"id": "calibration"}},
        plan={"screen_ids": [], "batches": []},
    )
    usage = api().outside_usage(catalog, [], "not_run")
    assert usage["global"]["expected_frames"] == 0
    assert usage["global"]["used_share_expected"] is None
    assert usage["global"]["used_share_observed"] is None
    assert usage["engineering_pauses"] == []


def test_d053_normal_version_and_complete_zero_usage(synthetic_runtime):
    folder, catalog, inputs, result = synthetic_runtime
    assert result["mutation_run_version"] == 4
    assert json_bytes((folder / "evidence-index.json").read_bytes())["version"] == 5
    assert result["outside_rule_policy"] == api().outside_rule_policy()
    assert {"mutation_outside_rule.py", "mutation_diagnostics.py"} <= set(
        result["implementation_hashes"]
    )
    usage = result["outside_rule_usage"]
    assert usage["global"]["expected_frames"] == 40
    assert usage["global"]["observed_frames"] == 40
    assert usage["global"]["used_frames"] == usage["global"]["pending_frames"] == 0
    assert usage["global"]["expected_unique_pairs"] == 20
    assert usage["engineering_pauses"] == []
    for shot in result["screenshots"]:
        proof = shot["outside_rule"]
        assert proof["used"] is False
        if shot["role"] != "clean":
            assert proof["repeat_state"] == "confirmed"
            assert proof["repeat"]["passed"] is True
            assert shot["qualified"] is True
    assert (
        api().verify_run(
            folder, catalog, inputs, evidence_sha256=result["evidence_sha256"]
        )["status"]
        == "qualified"
    )


@pytest.mark.parametrize("status", ["failed", "qualified"])
def test_d054_rejects_d053_identity_with_archived_exact_producer_instruction(
    synthetic_runtime, status
):
    folder, catalog, inputs, _ = synthetic_runtime
    value = json_bytes((folder / "mutation-manifest.json").read_bytes())
    value.update(
        mutation_run_version=3,
        status=status,
        capture_set_qualified=status == "qualified",
    )
    old_policy = {
        **value["outside_rule_policy"],
        "decision": "D053",
        "version": 1,
        "max_rgb_delta": 2,
    }
    value["outside_rule_policy"] = old_policy
    for shot in value["screenshots"]:
        assessment = shot["outside_rule"]["assessment"]
        if assessment is not None:
            assessment["policy"] = dict(old_policy)
    # Exact pre-D054 producer hashes, not matching claims of current authority.
    value["implementation_hashes"].update(
        {
            "mutation_run.py": "fadaf8d32b79e7ba4c516d2f1f00377ab3a0f044d1bbc2cf2a381e4617ae67c3",
            "mutation_outside_rule.py": "7f2ed8a614f5a2a094642b77c7ce3ec0a5b484ee5149c1a1d22165a1992ef0e8",
        }
    )
    journal_path = folder / "journal.json"
    journal = json_bytes(journal_path.read_bytes())
    journal.update(status=status, implementation_hashes=value["implementation_hashes"])
    journal_path.write_bytes(canonical_bytes(journal))
    rewrite_synthetic_manifest(folder, value)
    caught = None
    try:
        api().verify_run(
            folder, catalog, inputs, evidence_sha256=reindex_synthetic(folder, 4)
        )
    except CaptureError as exc:
        caught = str(exc)
    assert caught is not None
    assert "D053" in caught and "archived" in caught and "exact" in caught
    assert "09acc674516196be2badfae247cc1ff76228fa17" in caught


def test_d054_large_rgb_pair_cannot_replace_independent_nonpixel_gates():
    from copy import deepcopy

    from test_mutation_diagnostics import dump, element, png

    before = dump([element()])
    first, second = png(), png([((1, 1), (57, 20, 30, 255))])
    strict = api().verify_screen(first, second, before, before, [])
    pair = [
        {
            "batch_id": "synthetic-batch",
            "role": "calibration",
            "screen": before.screen,
            "language": "en",
            "pass": n,
            "pair_sha256": str(n) * 64,
            "control_pair_sha256": "0" * 64,
            "verification": deepcopy(strict),
        }
        for n in (1, 2)
    ]
    paired = {}
    assert (
        api().measure_outside_record(pair[0], first, second, before, before, paired)
        is None
    )
    assert pair[0]["qualified"] is False
    assert (
        api().measure_outside_record(pair[1], first, second, before, before, paired)
        is None
    )
    assert all(s["qualified"] for s in pair)
    for invalid in (
        {"occurrences": [{"qualified": False}]},
        {"occurrences": [{"qualified": True}] * 3},
        {"changed_unmutated_elements": [{"actor_path": "changed"}]},
    ):
        for shot in pair:
            shot["verification"] = {**deepcopy(strict), **invalid}
        assert api().confirm_outside_pair(*pair) is True  # Pixel proof alone passes.
        assert all(s["qualified"] is False for s in pair)
        assert all(s["verification"]["passed"] is False for s in pair)


def test_synthetic_successful_orchestration_replays_offline(synthetic_runtime):
    folder, catalog, inputs, _ = synthetic_runtime
    value = api().verify_run(
        folder,
        catalog,
        inputs,
        evidence_sha256=digest((folder / "evidence-index.json").read_bytes()),
    )
    assert value["status"] == "qualified" and len(value["screenshots"]) == 60


def differing_calibration(
    capture, *, reverse_only=False, roles=("calibration",), dump_only=False
):
    """Change PNG/raw-dump bytes with valid provenance for the real verifier."""
    import io

    from PIL import Image

    from l10n_checker.text_dump import rgba_digest

    def wrapped(device, effective, folder, languages, *, on_pair, variant, **kwargs):
        assert kwargs["fail_fast"] is True

        def measured(record):
            if variant in roles and (not reverse_only or record["pass"] == 2):
                pair_path = folder / record["pair"]
                pair = json_bytes(pair_path.read_bytes())
                if dump_only:
                    dump_path = pair_path.parent / pair["dump"]
                    raw = dump_path.read_bytes() + b"\n"
                    dump_path.write_bytes(raw)
                    pair["dump_sha256"] = record["dump_sha256"] = digest(raw)
                else:
                    png_path = pair_path.parent / pair["png"]
                    with Image.open(io.BytesIO(png_path.read_bytes())) as image:
                        image = image.convert("RGBA")
                        pixel = image.getpixel((2399, 1079))
                        assert isinstance(pixel, tuple)
                        r, g, b, a = pixel
                        image.putpixel((2399, 1079), (r ^ 255, g, b, a))
                        image.save(png_path)
                    raw = png_path.read_bytes()
                    for name, value in (
                        ("png_sha256", digest(raw)),
                        ("rgba_sha256", rgba_digest(raw)),
                    ):
                        pair[name] = record[name] = value
                pair_path.write_bytes(canonical_bytes(pair))
            on_pair(record)

        summary = capture(
            device,
            effective,
            folder,
            languages,
            on_pair=measured,
            variant=variant,
            **kwargs,
        )
        if reverse_only and variant in roles:
            from l10n_checker.screen_capture import compare_pixels

            for comparison in summary["comparisons"]:
                records = [
                    r
                    for r in summary["records"]
                    if (r["screen"], r["language"])
                    == (comparison["screen"], comparison["language"])
                ]
                comparison.update(compare_pixels(*(folder / r["png"] for r in records)))
                dumps = [(folder / r["dump"]).read_bytes() for r in records]
                comparison["dump_status"] = (
                    "identical" if dumps[0] == dumps[1] else "different"
                )
            if dump_only:
                hashes = {r["request"]: r["dump_sha256"] for r in summary["records"]}
                for operation in summary["app_data_operations"]:
                    if operation["operation"] == "hook_output":
                        operation["sha256"] = hashes[operation["request"]]
            summary["status"] = "failed"
            (folder / "summary.json").write_bytes(canonical_bytes(summary))
        return summary

    return wrapped


def test_measurement_continues_all_failed_pairs_without_production(
    synthetic_completed_runtime,
):
    checkpoints = []

    def configure(run):
        initial = json_bytes((run.folder / "mutation-manifest.json").read_bytes())
        assert (
            initial["measurement_only"] is True
            and initial["measurement_complete"] is False
        )
        assert initial["status"] == initial["calibration_status"] == "failed"
        assert initial["capture_set_qualified"] is False
        checkpoint = run.checkpoint

        def observed():
            checkpoint()
            checkpoints.append(
                json_bytes((run.folder / "mutation-manifest.json").read_bytes())
            )

        run.checkpoint = observed

    run, result = synthetic_completed_runtime["execute"](
        "measurement-differences",
        measurement_only=True,
        volatile=True,
        capture_wrapper=differing_calibration,
        configure=configure,
    )
    assert result["measurement_only"] is True and result["measurement_complete"] is True
    assert result["status"] == "failed" and result["calibration_status"] == "failed"
    assert result["capture_set_qualified"] is False
    assert result["downgrade_verified"] and result["restoration_verified"]
    assert (
        result["dynamic_tests"] == [] and not (run.folder / "builder-handoff").exists()
    )
    assert len(result["screenshots"]) == 40
    for role in ("clean", "calibration"):
        shots = [s for s in result["screenshots"] if s["role"] == role]
        assert len(shots) == 20
        assert {(s["screen"], s["language"], s["pass"]) for s in shots} == {
            (screen, language, n)
            for screen in run.plan["screen_ids"]
            for language in ("en", "de")
            for n in (1, 2)
        }
        if role == "calibration":
            assert all(s["verification"]["passed"] is False for s in shots)
            assert all(
                s["verification"]["pixels"]["outside"]["different_pixels"] == 1
                for s in shots
            )
    assert all(
        s["measurement_only"] is True
        and s["calibration_status"] == "failed"
        and s["capture_set_qualified"] is False
        and s["status"] == "failed"
        for s in checkpoints
    )
    installs = [
        args for args in run.device.calls if args[:3] == ("install", "-r", "-d")
    ]
    assert [Path(args[3]) for args in installs] == [
        run.catalog.apk_path(record)
        for record in (
            run.catalog.control,
            run.reference(),
            run.catalog.control,
            run.catalog.calibration,
            run.reference(),
        )
    ]
    assert run.device.build() == "1271048"
    assert (
        api().verify_run(
            run.folder,
            run.catalog,
            run.inputs,
            evidence_sha256=result["evidence_sha256"],
        )["measurement_complete"]
        is True
    )


@pytest.mark.parametrize("role", ["clean", "calibration"])
@pytest.mark.parametrize("dump_only", [False, True])
def test_measurement_retains_repeat_differences_and_completes_both_roles(
    synthetic_completed_runtime, role, dump_only
):
    run, result = synthetic_completed_runtime["execute"](
        f"measurement-repeat-{role}-{dump_only}",
        measurement_only=True,
        capture_wrapper=lambda capture: differing_calibration(
            capture, reverse_only=True, roles=(role,), dump_only=dump_only
        ),
    )
    assert result["measurement_complete"] is True, run.journal
    assert result["status"] == result["calibration_status"] == "failed"
    assert result["capture_set_qualified"] is False and result["restoration_verified"]
    assert len(result["screenshots"]) == 40
    assert result["dynamic_tests"] == []
    measured = next(r for r in result["measurement_captures"] if r["role"] == role)
    summary = json_bytes((run.folder / measured["summary"]).read_bytes())
    assert measured["repeatability_passed"] is False
    assert summary["status"] == "failed" and not summary.get("fatal_error")
    assert len(summary["records"]) == 20
    assert all(
        c["different_pixels"] == (0 if dump_only else 1) for c in summary["comparisons"]
    )
    assert all(
        c["dump_status"] == ("different" if dump_only else "identical")
        for c in summary["comparisons"]
    )
    replay = api().verify_run(
        run.folder, run.catalog, run.inputs, evidence_sha256=result["evidence_sha256"]
    )
    assert replay["measurement_complete"] is True and replay["status"] == "failed"


@pytest.fixture(scope="module")
def synthetic_measurement_runtime(synthetic_completed_runtime):
    import copy

    class ForbiddenProduction(list):
        def __iter__(self):
            raise AssertionError(
                "Measurement evaluated the production stage collection"
            )

    def configure(run):
        run.catalog = copy.copy(run.catalog)
        run.plan = run.catalog.plan = {**run.plan, "batches": ForbiddenProduction()}

    run, result = synthetic_completed_runtime["execute"](
        "measurement-zero", measurement_only=True, configure=configure
    )
    # All comparisons genuinely pass in this synthetic case; still never qualify.
    assert result["measurement_complete"] is True
    assert result["status"] == result["calibration_status"] == "failed"
    assert result["capture_set_qualified"] is False
    assert all(
        s["verification"] is None or s["verification"]["passed"]
        for s in result["screenshots"]
    )
    # Return the unmodified catalog for semantic replay and tampering tests.
    _, catalog, inputs, _ = synthetic_completed_runtime["completed"]
    return run.folder, catalog, inputs, result


@pytest.mark.parametrize(
    "marker", ["measurement_only", "measurement_complete", "measurement_captures"]
)
def test_measurement_markers_reject_rehashed_success(synthetic_runtime, marker):
    folder, catalog, inputs, _ = synthetic_runtime
    value = json_bytes((folder / "mutation-manifest.json").read_bytes())
    value[marker] = [] if marker == "measurement_captures" else True
    rewrite_synthetic_manifest(folder, value)
    with pytest.raises(CaptureError, match="[Mm]easurement"):
        api().verify_run(
            folder, catalog, inputs, evidence_sha256=reindex_synthetic(folder)
        )


@pytest.mark.parametrize("flag", ["measurement_only", "measurement_complete"])
def test_measurement_journal_flags_require_exact_booleans(
    synthetic_measurement_runtime, tmp_path, flag
):
    import shutil

    source, catalog, inputs, _ = synthetic_measurement_runtime
    folder = tmp_path / "measurement"
    shutil.copytree(source, folder)
    path = folder / "journal.json"
    journal = json_bytes(path.read_bytes())
    journal[flag] = 1
    path.write_bytes(canonical_bytes(journal))
    with pytest.raises(CaptureError, match="[Mm]easurement"):
        api().verify_run(
            folder, catalog, inputs, evidence_sha256=reindex_synthetic(folder)
        )


@pytest.mark.parametrize(
    "tamper", ["qualify", "delete_mode", "delete_all_markers", "partial", "duplicate"]
)
def test_measurement_evidence_cannot_be_promoted_or_claim_incomplete_matrix(
    synthetic_measurement_runtime, tmp_path, tamper
):
    import shutil

    source, catalog, inputs, _ = synthetic_measurement_runtime
    folder = tmp_path / "measurement"
    shutil.copytree(source, folder)
    value = json_bytes((folder / "mutation-manifest.json").read_bytes())
    journal = json_bytes((folder / "journal.json").read_bytes())
    if tamper in {"qualify", "delete_mode", "delete_all_markers"}:
        value.update(
            status="qualified", capture_set_qualified=True, calibration_status="passed"
        )
        journal["status"] = "qualified"
        if tamper == "delete_mode":
            value.pop("measurement_only")
        elif tamper == "delete_all_markers":
            for name in (
                "measurement_only",
                "measurement_complete",
                "measurement_captures",
            ):
                value.pop(name, None)
                journal.pop(name, None)
            # Even fabricated stage flags cannot supply missing production pairs/receipts.
            value["dynamic_tests"] = [
                {"id": b["id"], "recipe_ids": b["recipe_ids"], "split": False}
                for b in catalog.plan["batches"]
            ]
            value["dynamic_split_rate"] = api().split_rate(value["dynamic_tests"])
    elif tamper == "partial":
        value["screenshots"].pop()
    else:
        value["screenshots"][-1] = value["screenshots"][0]
    value["observed_occurrence_matrix"] = api().occurrence_matrix(value["screenshots"])
    (folder / "journal.json").write_bytes(canonical_bytes(journal))
    rewrite_synthetic_manifest(folder, value)
    with pytest.raises(CaptureError):
        api().verify_run(
            folder, catalog, inputs, evidence_sha256=reindex_synthetic(folder)
        )


@pytest.mark.parametrize(
    "invalid", [None, "catalog", "control", "calibration", "probe", "resume"]
)
def test_measurement_config_binds_owner_scope_before_device(
    tmp_path, monkeypatch, invalid
):
    import subprocess
    from types import SimpleNamespace

    runtime = api()
    frozen = "790b21921ca3d4988b6257a6da235817c8b8407b2f029871c74a05598efaf354"
    screens = [
        "options-gameplay",
        "tech-picker",
        "city-production",
        "empire-stats",
        "civilopedia",
    ]
    catalog = SimpleNamespace(
        plan={"screen_ids": screens},
        control={"build": {"version_code": "1888080431"}},
        calibration={"build": {"version_code": "1808820362"}},
    )
    config: dict[str, str] = dict.fromkeys(
        ("catalog", "manifest", "recipes", "sdk", "jdk"), str(tmp_path / "synthetic")
    )
    config.update(
        sha256=frozen,
        serial="emulator-5554",
        approved_output_root=str(tmp_path / "approved"),
        output_dir=str(tmp_path / "approved/run"),
    )
    if invalid == "catalog":
        config["sha256"] = "a" * 64
    elif invalid in {"control", "calibration"}:
        getattr(catalog, invalid)["build"]["version_code"] = "1271048"
    elif invalid == "resume":
        config.update(resume_from="parent", resume_sha256="b" * 64)
    monkeypatch.setattr(runtime, "read_catalog", lambda *args, **kwargs: catalog)
    monkeypatch.setattr(
        runtime,
        "Inputs",
        lambda *args, **kwargs: SimpleNamespace(
            screens=lambda: [SimpleNamespace(id=s) for s in screens]
        ),
    )
    calls = []

    def device(*args):
        assert invalid is None, "Invalid measurement reached device construction"
        calls.append("device")
        return SimpleNamespace(serial="emulator-5554")

    monkeypatch.setattr(runtime, "Device", device)
    common = tmp_path / "synthetic-common"
    common.mkdir()
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(stdout=str(common).encode()),
    )

    class SyntheticRun:
        def __init__(self, *args, **kwargs):
            assert kwargs["measurement_only"] is True
            self.content = {}

        def checkpoint(self):
            pass

        def run(self, **kwargs):
            assert kwargs == {"probe_only": False, "measurement_only": True}
            calls.append("measurement")
            return {"measurement_only": True}

    monkeypatch.setattr(runtime, "MutationRun", SyntheticRun)
    if invalid:
        with pytest.raises(CaptureError, match="[Mm]easurement"):
            runtime.run_config(
                config, measurement_only=True, probe_only=invalid == "probe"
            )
        assert calls == []
    else:
        assert runtime.run_config(config, measurement_only=True) == {
            "measurement_only": True
        }
        assert calls == ["device", "measurement"]


@pytest.mark.parametrize("cleanup_failure", [False, True, "interrupt"])
def test_measurement_cancellation_retains_primary_and_finalizes_once(
    synthetic_completed_runtime, cleanup_failure
):
    primary = KeyboardInterrupt("owner cancelled measurement")
    runs, restores = [], []

    def configure(run):
        runs.append(run)
        restore = run._restore_once

        def once():
            restores.append(run.counter)
            if cleanup_failure and run.counter == 4:
                if cleanup_failure == "interrupt":
                    raise KeyboardInterrupt("reference cleanup failed")
                raise CaptureError("reference cleanup failed")
            restore()

        run._restore_once = once

    def interrupted(capture):
        def wrapped(*args, on_pair, variant, **kwargs):
            def measured(record):
                on_pair(record)
                if variant == "calibration":
                    raise primary

            return capture(*args, on_pair=measured, variant=variant, **kwargs)

        return wrapped

    with pytest.raises(KeyboardInterrupt) as caught:
        synthetic_completed_runtime["execute"](
            f"measurement-cancel-{cleanup_failure}",
            measurement_only=True,
            configure=configure,
            capture_wrapper=interrupted,
        )
    assert caught.value is primary
    run = runs[0]
    assert restores == [2, 4], "One probe restore and one final restore, never a retry"
    journal = json_bytes((run.folder / "journal.json").read_bytes())
    value = json_bytes((run.folder / "mutation-manifest.json").read_bytes())
    assert journal["error_details"]["type"] == "KeyboardInterrupt"
    assert value["measurement_complete"] is False and value["measurement_only"] is True
    assert (
        value["calibration_status"] == "failed" and not value["capture_set_qualified"]
    )
    assert value["status"] == ("restoration_failed" if cleanup_failure else "failed")
    assert value["restoration_verified"] is (not cleanup_failure)
    assert json_bytes((run.folder / "evidence-index.json").read_bytes())["version"] == 3
    if cleanup_failure:
        assert journal["restoration_error"] == "reference cleanup failed"
        assert journal["cleanup_errors"] and getattr(primary, "cleanup_errors", [])
    else:
        assert run.device.build() == "1271048"


@pytest.mark.parametrize(
    "tamper",
    [
        "install",
        "environment",
        "backup",
        "ledger",
        "fatal",
        "cleanup",
        "saves",
        "repeat_claim",
    ],
)
def test_complete_measurement_replays_safety_receipts(
    synthetic_measurement_runtime, tmp_path, tamper
):
    import shutil

    source, catalog, inputs, _ = synthetic_measurement_runtime
    folder = tmp_path / "measurement"
    shutil.copytree(source, folder)
    value = json_bytes((folder / "mutation-manifest.json").read_bytes())
    if tamper == "install":
        (folder / "private/install-005/install.json").unlink()
    elif tamper == "environment":
        path = folder / "environment/005/receipt.json"
        receipt = json_bytes(path.read_bytes())
        receipt["exit_code"] = 1
        path.write_bytes(canonical_bytes(receipt))
    elif tamper == "backup":
        from test_mutation_device import archive

        (folder / "private/original/private.tar").write_bytes(
            archive(b"altered backup")
        )
    elif tamper == "ledger":
        path = folder / "journal.json"
        journal = json_bytes(path.read_bytes())
        journal["restoration_preservation"]["bookkeeping"] = []
        path.write_bytes(canonical_bytes(journal))
    elif tamper == "repeat_claim":
        value["measurement_captures"][0]["repeatability_passed"] = False
        rewrite_synthetic_manifest(folder, value)
    else:
        path = folder / value["measurement_captures"][0]["summary"]
        summary = json_bytes(path.read_bytes())
        if tamper == "fatal":
            summary["fatal_error_details"] = {"type": "TimeoutExpired"}
        elif tamper == "cleanup":
            summary["cleanup_errors"] = [{"type": "CaptureError"}]
        else:
            summary["saves_unchanged"] = False
        path.write_bytes(canonical_bytes(summary))
    with pytest.raises(CaptureError):
        api().verify_run(
            folder, catalog, inputs, evidence_sha256=reindex_synthetic(folder)
        )


def test_normal_calibration_still_stops_at_first_failed_pair(
    synthetic_completed_runtime,
):
    run, result = synthetic_completed_runtime["execute"](
        "normal-first-pixel", capture_wrapper=differing_calibration
    )
    assert result["status"] == "failed" and result["capture_set_qualified"] is False
    assert "measurement_only" not in result and "measurement_complete" not in result
    assert len(result["screenshots"]) == 21
    failed = [s for s in result["screenshots"] if s["role"] == "calibration"]
    assert len(failed) == 1 and failed[0]["verification"]["passed"] is False
    assert result["dynamic_tests"] == [] and result["restoration_verified"]
    assert run.device.build() == "1271048"


@pytest.mark.parametrize(
    "fault,role",
    [
        ("native", "calibration"),
        ("cleanup", "calibration"),
        ("settings", "clean"),
        ("saves", "calibration"),
        ("record", "calibration"),
        ("incomplete", "clean"),
        ("unavailable", "clean"),
        ("invalid_pair", "calibration"),
    ],
)
def test_measurement_operational_failures_are_fatal_not_repeat_differences(
    synthetic_completed_runtime, fault, role
):
    def faulty(capture):
        capture = differing_calibration(capture)

        def wrapped(*args, on_pair, variant, **kwargs):
            def measured(record):
                if fault == "invalid_pair" and variant == role:
                    path = args[2] / record["pair"]
                    pair = json_bytes(path.read_bytes())
                    pair["state_sha256"] = "0" * 64
                    path.write_bytes(canonical_bytes(pair))
                on_pair(record)

            summary = capture(*args, on_pair=measured, variant=variant, **kwargs)
            if variant == role:
                summary["status"] = "failed"
                if fault == "native":
                    summary["fatal_error"] = "native timeout after captures"
                    summary["fatal_error_details"] = {
                        "type": "TimeoutExpired",
                        "stderr": "retained native stderr",
                    }
                elif fault == "cleanup":
                    summary["cleanup_errors"] = [
                        {"type": "CaptureError", "message": "unroot failed"}
                    ]
                elif fault == "settings":
                    summary["settings_restored"] = False
                elif fault == "saves":
                    summary["saves_unchanged"] = False
                elif fault == "record":
                    summary["records"][-1]["error_details"] = {"type": "CaptureError"}
                elif fault == "incomplete":
                    summary["records"].pop()
                elif fault == "unavailable":
                    summary["comparisons"][0]["status"] = "unavailable"
                (args[2] / "summary.json").write_bytes(canonical_bytes(summary))
            return summary

        return wrapped

    run, result = synthetic_completed_runtime["execute"](
        f"measurement-fatal-{fault}", measurement_only=True, capture_wrapper=faulty
    )
    assert result["status"] == result["calibration_status"] == "failed"
    assert (
        result["measurement_complete"] is False
        and result["capture_set_qualified"] is False
    )
    assert result["restoration_verified"] and run.device.build() == "1271048"
    assert (
        result["dynamic_tests"] == [] and not (run.folder / "builder-handoff").exists()
    )
    assert len(result["screenshots"]) == (
        20 if role == "clean" or fault == "invalid_pair" else 40
    )
    assert run.journal.get("error")
    if fault in {"native", "cleanup", "record"}:
        assert run.journal["capture_errors"][-1]["role"] == role
        if fault == "native":
            assert (
                run.journal["capture_errors"][-1]["fatal_error_details"]["stderr"]
                == "retained native stderr"
            )


@pytest.mark.parametrize("kind", ["settings", "save", "other"])
def test_measurement_preservation_failure_stops_and_restores_without_repair(
    synthetic_completed_runtime, kind
):
    root_name = "external" if kind == "save" else "private"
    target = (
        "files/SaveFiles/unexpected-save"
        if kind == "save"
        else "files/GameSettings.json"
        if kind == "settings"
        else "files/other-state"
    )

    def change(root, number, files):
        # A transient unexpected post-clean observation, not an app-data repair.
        if root == root_name and number == 14:
            files[target] = b"unauthorized state"

    run, result = synthetic_completed_runtime["execute"](
        "measurement-preservation-" + kind,
        measurement_only=True,
        volatile=True,
        transform=change,
    )
    assert result["status"] == "failed" and result["measurement_complete"] is False
    assert (
        result["calibration_status"] == "failed" and not result["capture_set_qualified"]
    )
    assert result["restoration_verified"] and run.device.build() == "1271048"
    assert len(result["screenshots"]) == 20
    check = run.journal["capture_data_checks"][-1]
    assert [entry["path"] for entry in check["preservation"]["unexpected_changes"]] == [
        root_name + ":" + target
    ]
    assert result["dynamic_tests"] == []


def test_measurement_rejects_production_capture_before_install(real_capture_runtime):
    run, record, events = real_capture_runtime
    run.content.update(measurement_only=True, measurement_complete=False)
    with pytest.raises(CaptureError, match="authorized control/calibration"):
        run.capture(record, "mutation", measurement_only=False)
    assert events == []


def test_d051_runtime_accepts_only_bookkeeping_at_all_preservation_boundaries(
    synthetic_completed_runtime,
):
    from l10n_checker.mutation_device import preservation_policy, preservation_report

    run, result = synthetic_completed_runtime["execute"]("d051-runtime", volatile=True)
    assert result["status"] == "qualified", run.journal
    assert result["preservation_policy"] == preservation_policy()
    original = json_bytes((run.folder / "private/original/inventory.json").read_bytes())
    readback = json_bytes((run.folder / "private/original-readback.json").read_bytes())
    assert run.journal["original_readback_preservation"] == preservation_report(
        original, readback
    )
    final = json_bytes((run.folder / "private/final-inventory.json").read_bytes())
    assert run.journal["restoration_preservation"] == preservation_report(
        original, final, run.allowed_outputs
    )
    assert run.journal["restoration_data_changes"] == api().inventory_changes(
        original, final, run.allowed_outputs
    )
    assert len(run.journal["capture_data_checks"]) == 3
    for check in run.journal["capture_data_checks"]:
        assert check["preservation"]["exempt_changes"] == check["changes"]
        assert check["changes"] and check["preservation"]["unexpected_changes"] == []
        assert len(check["preservation"]["bookkeeping"]) == 4
    assert result["capture_set_qualified"] and result["restoration_verified"]


@pytest.fixture(scope="module")
def d051_completed_runtime(synthetic_completed_runtime):
    run, result = synthetic_completed_runtime["execute"]("d051-replay", volatile=True)
    assert result["status"] == "qualified", run.journal
    _, catalog, inputs, _ = synthetic_completed_runtime["completed"]
    return run.folder, catalog, inputs, result


def test_d051_replay_recomputes_authorized_drift_from_inventories(
    d051_completed_runtime,
):
    folder, catalog, inputs, result = d051_completed_runtime
    caught = None
    replay = None
    try:
        replay = api().verify_run(
            folder, catalog, inputs, evidence_sha256=result["evidence_sha256"]
        )
    except CaptureError as exc:
        caught = exc
    assert caught is None, (
        f"D-051 operational replay rejected authorized drift: {caught}"
    )
    assert replay is not None
    assert replay["status"] == "qualified" and replay["mutation_run_version"] == 4
    assert json_bytes((folder / "evidence-index.json").read_bytes())["version"] == 5


@pytest.mark.parametrize("boundary,inventory_number", [("install", 3), ("capture", 13)])
def test_d051_runtime_stops_on_strict_drift_between_transactions(
    synthetic_completed_runtime,
    boundary,
    inventory_number,
):
    def change(root, number, files):
        if root == "private" and number >= inventory_number:
            files["files/not-bookkeeping"] = b"unexpected game state"

    run, result = synthetic_completed_runtime["execute"](
        "d051-gap-" + boundary,
        volatile=True,
        transform=change,
    )
    assert not result["capture_set_qualified"] and result["status"] in {
        "failed",
        "restoration_failed",
    }
    assert result["screenshots"] == [], "Strict drift must stop before capturing"
    installs = [c for c in run.device.calls if c[:3] == ("install", "-r", "-d")]
    if boundary == "install":
        assert installs == [], "Prior app-data drift must stop before the next install"
    else:
        assert "preflight" in run.journal["error"].lower()


def test_d051_retains_every_reference_and_transaction_boundary(d051_completed_runtime):
    from l10n_checker.mutation_device import preservation_report

    folder, _, _, _ = d051_completed_runtime
    journal = json_bytes((folder / "journal.json").read_bytes())
    assert len(journal.get("restoration_checks", [])) == 2, (
        "Probe restore must not be overwritten"
    )
    for operation in journal["operations"]:
        receipt = json_bytes((folder / operation["receipt"]).read_bytes())
        assert receipt.get("input_preservation"), (
            "Missing install input continuity ledger"
        )
    for check in journal["capture_data_checks"]:
        assert check.get("preflight_preservation"), "Missing capture preflight ledger"
    original = json_bytes((folder / "private/original/inventory.json").read_bytes())
    for check in journal["restoration_checks"]:
        current = json_bytes((folder / check["inventory"]).read_bytes())
        assert check["preservation"] == preservation_report(
            original, current, check["allowed_outputs"]
        )
        assert check["prior_preservation"]["unexpected_changes"] == []


@pytest.mark.parametrize("inventory_number", [2, 4, 5, 14, 28])
@pytest.mark.parametrize("kind", ["settings", "save", "other"])
def test_d051_bookkeeping_drift_cannot_hide_strict_runtime_changes(
    synthetic_completed_runtime,
    inventory_number,
    kind,
):
    root_name = "external" if kind == "save" else "private"
    target = (
        "files/GameSettings.json"
        if kind == "settings"
        else "files/SaveFiles/unexpected-save"
        if kind == "save"
        else "files/other-state"
    )

    def change(root, number, files):
        if root == root_name and number >= inventory_number:
            files[target] = b"unauthorized delta"

    run, result = synthetic_completed_runtime["execute"](
        f"d051-strict-{inventory_number}-{kind}",
        volatile=True,
        transform=change,
    )
    assert result["status"] in {"failed", "restoration_failed"}
    assert not result["capture_set_qualified"]
    assert not (run.folder / "builder-handoff").exists()

    # Inspect complete ledgers rather than accepting an unrelated operational error.
    def unexpected(value):
        if isinstance(value, dict):
            yield from value.get("unexpected_changes", [])
            for child in value.values():
                yield from unexpected(child)
        elif isinstance(value, list):
            for child in value:
                yield from unexpected(child)

    receipts = [
        json_bytes(p.read_bytes())
        for p in (run.folder / "private").glob("install-*/install.json")
    ]
    assert any(
        c["path"] == root_name + ":" + target
        for c in unexpected([run.journal, receipts])
    )


@pytest.fixture
def d051_runtime_copy(d051_completed_runtime, tmp_path):
    import shutil

    folder, catalog, inputs, _ = d051_completed_runtime
    target = tmp_path.resolve() / "d051-evidence"
    shutil.copytree(folder, target)
    return target, catalog, inputs


@pytest.mark.parametrize(
    "kind",
    [
        "manifest_policy_missing",
        "manifest_policy_widened",
        "manifest_policy_bool",
        "manifest_downgrade",
        "index_downgrade",
        "complete_downgrade",
        "journal_policy",
        "original_readback",
        "restoration",
        "restoration_checks",
        "capture",
        "capture_preflight",
        "install_policy",
        "install_input",
        "install_readback",
        "install_post_readback",
        "install_ledger",
        "install_raw",
        "bookkeeping_row",
        "ledger_widened",
    ],
)
def test_d051_rehashed_policy_and_ledger_tampering_is_rejected(d051_runtime_copy, kind):
    folder, catalog, inputs = d051_runtime_copy
    value = json_bytes((folder / "mutation-manifest.json").read_bytes())
    journal_path = folder / "journal.json"
    journal = json_bytes(journal_path.read_bytes())
    operation = journal["operations"][0]
    install_path = folder / operation["receipt"]
    receipt = json_bytes(install_path.read_bytes())
    version = 5
    if kind == "manifest_policy_missing":
        value.pop("preservation_policy")
    elif kind == "manifest_policy_widened":
        value["preservation_policy"]["regular_file_paths"].append(
            "private:files/GameSettings.json"
        )
    elif kind == "manifest_policy_bool":
        value["preservation_policy"]["app_data_writes"] = False
    elif kind in {"manifest_downgrade", "complete_downgrade"}:
        value["mutation_run_version"] = 1
        value.pop("preservation_policy")
        if kind == "complete_downgrade":
            version = 2
    elif kind == "index_downgrade":
        version = 2
    elif kind == "journal_policy":
        journal.pop("preservation_policy")
    elif kind == "original_readback":
        journal.pop("original_readback_preservation")
    elif kind == "restoration":
        journal["restoration_preservation"]["exempt_changes"] = []
    elif kind == "restoration_checks":
        journal["restoration_checks"].pop(0)
    elif kind == "capture":
        journal["capture_data_checks"][0]["preservation"]["exempt_changes"] = []
    elif kind == "capture_preflight":
        path = next((folder / "artifacts/clean").glob("*/preflight-preservation.json"))
        ledger = json_bytes(path.read_bytes())
        ledger["bookkeeping"].pop()
        path.write_bytes(canonical_bytes(ledger))
    elif kind.startswith("install_"):
        field = {
            "install_policy": "preservation_policy",
            "install_input": "input_preservation",
            "install_readback": "backup_readback_preservation",
            "install_post_readback": "post_readback_preservation",
            "install_ledger": "preservation",
        }.get(kind)
        if field:
            receipt.pop(field)
        else:
            receipt["data_changes"] = []
    elif kind == "bookkeeping_row":
        receipt["preservation"]["bookkeeping"].pop()
    else:
        receipt["preservation"]["policy"]["allowed_changes"].append("mode")
    rewrite_synthetic_manifest(folder, value)
    install_path.write_bytes(canonical_bytes(receipt))
    operation["sha256"] = digest(canonical_bytes(receipt))
    journal_path.write_bytes(canonical_bytes(journal))
    with pytest.raises(
        CaptureError, match="[Pp]reservation|[Ll]edger|[Ll]egacy|receipt|inventory"
    ):
        api().verify_run(
            folder, catalog, inputs, evidence_sha256=reindex_synthetic(folder, version)
        )


@pytest.mark.parametrize(
    "kind", ["settings", "save", "other", "mode", "symlink", "external_alias"]
)
def test_d051_rehashed_inventories_with_honest_ledgers_still_reject_unexpected_changes(
    d051_runtime_copy,
    kind,
):
    import io
    import tarfile

    from l10n_checker.mutation_device import (
        data_inventory,
        inventory_changes,
        preservation_report,
    )

    folder, catalog, inputs = d051_runtime_copy
    tx = folder / "private/install-001"
    journal_path = folder / "journal.json"
    journal = json_bytes(journal_path.read_bytes())
    receipt_path = tx / "install.json"
    receipt = json_bytes(receipt_path.read_bytes())
    root = "external" if kind in {"save", "external_alias"} else "private"
    path = tx / "after" / (root + ".tar")
    target = {
        "settings": "files/GameSettings.json",
        "other": "files/not-bookkeeping",
        "mode": "files/profileInstalled",
        "symlink": "files/profileInstalled",
        "external_alias": "files/profileInstalled",
        "save": "files/SaveFiles/" + next(iter(inputs.fixtures)),
    }[kind]
    stream = io.BytesIO()
    found = False
    with (
        tarfile.open(fileobj=io.BytesIO(path.read_bytes())) as source,
        tarfile.open(fileobj=stream, mode="w") as output,
    ):
        for member in source.getmembers():
            payload = source.extractfile(member)
            assert payload is not None
            raw = payload.read()
            if str(Path(member.name)) == target:
                found = True
                if kind == "mode":
                    member.mode = 0o644
                elif kind == "symlink":
                    member.type, member.linkname, member.size = (
                        tarfile.SYMTYPE,
                        "elsewhere",
                        0,
                    )
                    raw = b""
                else:
                    raw = b"unexpected changed bytes"
                    member.size = len(raw)
            output.addfile(member, io.BytesIO(raw))
        if not found:
            member = tarfile.TarInfo("./" + target)
            member.size, member.uid, member.gid, member.mode = 3, 10001, 10001, 0o600
            output.addfile(member, io.BytesIO(b"new"))
    path.write_bytes(stream.getvalue())
    archives = {
        name: (tx / "after" / (name + ".tar")).read_bytes()
        for name in ("private", "external", "device_encrypted")
    }
    after = data_inventory(archives)
    (tx / "after/inventory.json").write_bytes(canonical_bytes(after))
    receipt["post_install"] = {
        "archives": {
            name: {"path": name + ".tar", "sha256": digest(raw), "bytes": len(raw)}
            for name, raw in archives.items()
        },
        "inventory_sha256": digest(canonical_bytes(after)),
    }
    before = json_bytes((tx / "before/inventory.json").read_bytes())
    readback = json_bytes((tx / "before-readback.json").read_bytes())
    receipt["data_changes"] = inventory_changes(before, after)
    receipt["preservation"] = preservation_report(before, after)
    receipt["post_readback_preservation"] = preservation_report(readback, after)
    assert any(
        c["path"] == root + ":" + target
        for c in (
            receipt["preservation"]["unexpected_changes"]
            + receipt["post_readback_preservation"]["unexpected_changes"]
        )
    )
    receipt_path.write_bytes(canonical_bytes(receipt))
    journal["operations"][0]["sha256"] = digest(canonical_bytes(receipt))
    journal_path.write_bytes(canonical_bytes(journal))
    with pytest.raises(CaptureError, match="Unexpected app-data inventory change"):
        api().verify_run(
            folder, catalog, inputs, evidence_sha256=reindex_synthetic(folder)
        )


def test_empty_evidence_index_cannot_skip_verification(synthetic_runtime):
    folder, catalog, inputs, _ = synthetic_runtime
    (folder / "evidence-index.json").write_bytes(
        canonical_bytes({"version": 1, "files": {}})
    )
    with pytest.raises(CaptureError, match="evidence|membership"):
        api().verify_run(
            folder,
            catalog,
            inputs,
            evidence_sha256=digest((folder / "evidence-index.json").read_bytes()),
        )


@pytest.mark.parametrize(
    "kind",
    [
        "missing_install",
        "install",
        "environment",
        "data",
        "final_reference",
        "calibration_summary",
        "capture_error",
        "missing_operations",
    ],
)
def test_success_claims_require_replayed_operational_receipts(synthetic_runtime, kind):
    folder, catalog, inputs, _ = synthetic_runtime
    journal_path = folder / "journal.json"
    journal = json_bytes(journal_path.read_bytes())
    first = journal["operations"][0]
    if kind == "missing_install":
        (folder / first["receipt"]).unlink()
    elif kind == "install":
        receipt_path = folder / first["receipt"]
        receipt = json_bytes(receipt_path.read_bytes())
        receipt.update(status="failed", app_data_preserved=False)
        receipt_path.write_bytes(canonical_bytes(receipt))
        first["sha256"] = digest(canonical_bytes(receipt))
        journal_path.write_bytes(canonical_bytes(journal))
    elif kind == "environment":
        path = folder / "environment/initial/receipt.json"
        value = json_bytes(path.read_bytes())
        value["exit_code"] = 1
        path.write_bytes(canonical_bytes(value))
    elif kind == "data":
        path = next((folder / "artifacts/clean").glob("*/after-capture/inventory.json"))
        path.write_bytes(canonical_bytes({"synthetic changed inventory": {}}))
    elif kind == "final_reference":
        (folder / "private/final-apk/installed.apk").write_bytes(
            b"synthetic wrong reference"
        )
    elif kind == "calibration_summary":
        path = next((folder / "artifacts/calibration").glob("*/capture/summary.json"))
        value = json_bytes(path.read_bytes())
        value["status"] = "failed"
        path.write_bytes(canonical_bytes(value))
    elif kind == "capture_error":
        journal["capture_errors"] = [
            {"fatal_error_details": {"type": "TimeoutExpired"}}
        ]
        journal_path.write_bytes(canonical_bytes(journal))
    else:
        journal["operations"] = []
        journal_path.write_bytes(canonical_bytes(journal))
    pin = reindex_synthetic(folder)
    with pytest.raises(
        CaptureError,
        match="receipt|backup|inventory|install|reference|environment|capture",
    ):
        api().verify_run(folder, catalog, inputs, evidence_sha256=pin)


def rewrite_synthetic_manifest(folder, value):
    raw = canonical_bytes(value)
    (folder / "mutation-manifest.json").write_bytes(raw)
    (folder / "mutation-manifest.sha256").write_text(digest(raw) + "\n")


@pytest.mark.parametrize("target", ["manifest", "receipt"])
def test_semantic_reads_are_bound_to_the_pinned_index(
    synthetic_runtime, monkeypatch, target
):
    folder, catalog, inputs, _ = synthetic_runtime
    original = Path.read_bytes
    pin = digest(original(folder / "evidence-index.json"))
    path = folder / (
        "mutation-manifest.json"
        if target == "manifest"
        else "environment/initial/receipt.json"
    )
    calls = 0

    def read(candidate):
        nonlocal calls
        if candidate == path:
            calls += 1
            if calls == 2:
                value = json_bytes(original(candidate))
                if target == "manifest":
                    value["implementation_hashes"]["mutation_run.py"] = "0" * 64
                    rewrite_synthetic_manifest(folder, value)
                else:
                    value["unused_changed_receipt_metadata"] = True
                    candidate.write_bytes(canonical_bytes(value))
        return original(candidate)

    monkeypatch.setattr(Path, "read_bytes", read)
    with pytest.raises(CaptureError, match="evidence|authenticated|hash"):
        api().verify_run(folder, catalog, inputs, evidence_sha256=pin)
    assert calls == 2


@pytest.mark.parametrize(
    "relative",
    [
        "private/original-readback.json",
        "private/install-001/before-readback.json",
        "private/final-inventory.json",
    ],
)
def test_success_retains_app_data_readback_evidence(synthetic_runtime, relative):
    folder, _, _, _ = synthetic_runtime
    assert (folder / relative).is_file(), (
        "Missing replayable app-data readback evidence"
    )


@pytest.mark.parametrize(
    "kind",
    [
        "original_receipt",
        "install_command",
        "install_signature",
        "install_backup",
        "environment_command",
        "environment_log",
        "capture_settings",
        "capture_saves",
        "capture_operations",
        "capture_records",
        "prepare_plan",
        "effective_manifest",
        "capture_comparisons",
        "capture_inventory",
        "original_readback",
        "install_readback",
        "final_readback",
    ],
)
def test_rehashed_semantic_operational_corruption_is_rejected(synthetic_runtime, kind):
    folder, catalog, inputs, _ = synthetic_runtime
    journal_path = folder / "journal.json"
    journal = json_bytes(journal_path.read_bytes())
    install_path = folder / journal["operations"][0]["receipt"]
    install = json_bytes(install_path.read_bytes())
    root = next((folder / "artifacts/calibration").iterdir())
    path = root / "capture/summary.json"
    value = json_bytes(path.read_bytes())
    if kind.endswith("readback"):
        relative = {
            "original_readback": "private/original-readback.json",
            "install_readback": "private/install-001/before-readback.json",
            "final_readback": "private/final-inventory.json",
        }[kind]
        (folder / relative).write_bytes(b"{}\n")
    elif kind == "capture_inventory":
        (root / "before-inventory.json").write_bytes(b"{}\n")
    elif kind == "original_receipt":
        journal["original_backup"]["inventory_sha256"] = "0" * 64
        journal_path.write_bytes(canonical_bytes(journal))
    elif kind.startswith("install_"):
        if kind == "install_command":
            install["command"][2] = "--unapproved"
        elif kind == "install_signature":
            install["observed_build"]["certificate_sha256"] = "0" * 64
        else:
            install["backup"]["inventory_sha256"] = "0" * 64
        install_path.write_bytes(canonical_bytes(install))
        journal["operations"][0]["sha256"] = digest(canonical_bytes(install))
        journal_path.write_bytes(canonical_bytes(journal))
    elif kind.startswith("environment_"):
        path = folder / "environment/initial/receipt.json"
        value = json_bytes(path.read_bytes())
        if kind == "environment_command":
            value["command"].append("--version-code=unapproved")
        else:
            value["stdout_sha256"] = "0" * 64
        path.write_bytes(canonical_bytes(value))
    elif kind == "prepare_plan":
        path = root / "prepare/device-plan.json"
        value = json_bytes(path.read_bytes())
        value["planned_hook_output_operations"] = []
        path.write_bytes(canonical_bytes(value))
    elif kind == "effective_manifest":
        (root / "effective-manifest.json").write_bytes(b"{}\n")
    else:
        if kind == "capture_settings":
            value["backup"]["settings_sha256"] = "0" * 64
        elif kind == "capture_saves":
            value["backup"]["saves"] = {}
        elif kind == "capture_operations":
            value["app_data_operations"] = []
        elif kind == "capture_comparisons":
            value["comparisons"][0]["dump_status"] = "different"
        else:
            value["records"] = []
        path.write_bytes(canonical_bytes(value))
    with pytest.raises(
        CaptureError,
        match="receipt|backup|inventory|install|reference|environment|capture|manifest|Preservation",
    ):
        api().verify_run(
            folder, catalog, inputs, evidence_sha256=reindex_synthetic(folder)
        )


def change_reverse_payload(folder, value, plan, role, kind):
    import io

    from PIL import Image

    from l10n_checker.text_dump import rgba_digest
    from l10n_checker.text_reference import load_pair

    selected = [
        r
        for r in value["screenshots"]
        if r["screen"] == "tech-picker"
        and r["language"] == "en"
        and r["pass"] == 2
        and (r["role"] == role or (role == "clean" and kind == "rgba"))
    ]
    for shot in selected:
        path = folder / shot["pair"]
        pair = json_bytes(path.read_bytes())
        if kind == "dump":
            payload = path.parent / pair["dump"]
            payload.write_bytes(payload.read_bytes() + b" \n")
            pair["dump_sha256"] = digest(payload.read_bytes())
        else:
            payload = path.parent / pair["png"]
            with Image.open(payload) as source:
                image = source.convert("RGBA")
            if kind == "rgba":
                xy = (
                    (0, 0)
                    if role == "clean"
                    else tuple(
                        shot["verification"]["pixels"]["mask"]["rectangles"][0][:2]
                    )
                )
                red, green, blue, alpha = image.getpixel(xy)
                image.putpixel(xy, (red, green, blue, alpha - 1))
            stream = io.BytesIO()
            image.save(stream, format="PNG", compress_level=1)
            payload.write_bytes(stream.getvalue())
            pair["png_sha256"] = digest(stream.getvalue())
            pair["rgba_sha256"] = rgba_digest(stream.getvalue())
        path.write_bytes(canonical_bytes(pair))
        shot.update(
            {key: pair[key] for key in ("png_sha256", "rgba_sha256", "dump_sha256")}
        )
        shot["pair_sha256"] = digest(path.read_bytes())
        root = path.parents[1]
        summary_path = root / "summary.json"
        summary = json_bytes(summary_path.read_bytes())
        record = next(
            r
            for r in summary["records"]
            if (r["screen"], r["language"], r["pass"]) == ("tech-picker", "en", 2)
        )
        record.update(
            {key: pair[key] for key in ("png_sha256", "rgba_sha256", "dump_sha256")}
        )
        for operation in summary["app_data_operations"]:
            if (
                operation["operation"] == "hook_output"
                and operation["request"] == record["request"]
            ):
                operation["sha256"] = pair["dump_sha256"]
        summary_path.write_bytes(canonical_bytes(summary))
    clean = next(
        r
        for r in value["screenshots"]
        if r["role"] == "clean"
        and (r["screen"], r["language"], r["pass"]) == ("tech-picker", "en", 2)
    )
    _, old_png, _, old_dump = load_pair(folder / clean["pair"])
    for shot in value["screenshots"]:
        if shot["role"] == "clean" or (
            shot["screen"],
            shot["language"],
            shot["pass"],
        ) != ("tech-picker", "en", 2):
            continue
        shot["control_pair_sha256"] = clean["pair_sha256"]
        _, png, _, dump = load_pair(folder / shot["pair"])
        shot["verification"] = api().verify_screen(
            old_png,
            png,
            old_dump,
            dump,
            [plan["mutations"][i] for i in shot["batch_recipe_ids"]],
        )
        assert shot["verification"]["passed"], (
            "Regression must preserve every per-pass dynamic gate"
        )
    if value.get("mutation_run_version") == 4:
        for shot in value["screenshots"]:
            proof = shot["outside_rule"]
            if shot["role"] == "clean":
                continue
            siblings = [
                s
                for s in value["screenshots"]
                if (s["batch_id"], s["role"], s["screen"], s["language"])
                == (shot["batch_id"], shot["role"], shot["screen"], shot["language"])
            ]
            proof["pair_binding"] = {
                "forward" if s["pass"] == 1 else "reverse": {
                    "pair_sha256": s["pair_sha256"],
                    "control_pair_sha256": s["control_pair_sha256"],
                }
                for s in siblings
            }
    rewrite_synthetic_manifest(folder, value)


@pytest.mark.parametrize("role", ["clean", "calibration", "mutation"])
@pytest.mark.parametrize("kind", ["rgba", "dump"])
def test_forward_reverse_replay_rejects_nonrepeatable_payloads(
    synthetic_runtime, role, kind
):
    folder, catalog, inputs, _ = synthetic_runtime
    value = json_bytes((folder / "mutation-manifest.json").read_bytes())
    change_reverse_payload(folder, value, catalog.plan, role, kind)
    with pytest.raises(CaptureError, match="repeat|forward|reverse"):
        api().verify_run(
            folder, catalog, inputs, evidence_sha256=reindex_synthetic(folder)
        )


def test_repeatability_compares_decoded_rgba_not_encoded_png_bytes(synthetic_runtime):
    folder, catalog, inputs, _ = synthetic_runtime
    value = json_bytes((folder / "mutation-manifest.json").read_bytes())
    change_reverse_payload(folder, value, catalog.plan, "mutation", "reencode")
    assert (
        api().verify_run(
            folder, catalog, inputs, evidence_sha256=reindex_synthetic(folder)
        )["status"]
        == "qualified"
    )


@pytest.mark.parametrize("synthetic_runtime", ["completed", "probe"], indirect=True)
@pytest.mark.parametrize(
    "field,replacement",
    [
        ("capture_set_qualified", "opposite"),
        ("capture_set_qualified", 1),
        ("downgrade_verified", False),
        ("restoration_verified", False),
        ("downgrade_verified", 1),
        ("restoration_verified", 1),
        ("status", "unknown_success"),
    ],
)
def test_success_statuses_require_exact_flags(synthetic_runtime, field, replacement):
    folder, catalog, inputs, _ = synthetic_runtime
    value = json_bytes((folder / "mutation-manifest.json").read_bytes())
    value[field] = not value[field] if replacement == "opposite" else replacement
    rewrite_synthetic_manifest(folder, value)
    with pytest.raises(CaptureError, match="status|flag|claim|qualification"):
        api().verify_run(
            folder, catalog, inputs, evidence_sha256=reindex_synthetic(folder)
        )


@pytest.mark.parametrize("kind", ["missing", "split", "wrong_recipes"])
def test_qualified_status_requires_successful_production_stage_gates(
    synthetic_runtime, kind
):
    folder, catalog, inputs, _ = synthetic_runtime
    value = json_bytes((folder / "mutation-manifest.json").read_bytes())
    if kind == "missing":
        value["dynamic_tests"] = []
    elif kind == "split":
        value["dynamic_tests"][0]["split"] = True
    else:
        value["dynamic_tests"][0]["recipe_ids"] = []
    value["dynamic_split_rate"] = api().split_rate(value["dynamic_tests"])
    rewrite_synthetic_manifest(folder, value)
    with pytest.raises(CaptureError, match="stage|dynamic|qualification"):
        api().verify_run(
            folder, catalog, inputs, evidence_sha256=reindex_synthetic(folder)
        )


@pytest.mark.parametrize("synthetic_runtime", ["probe"], indirect=True)
def test_successful_probe_replays_its_own_proof_without_captures(synthetic_runtime):
    folder, catalog, inputs, _ = synthetic_runtime
    value = api().verify_run(
        folder, catalog, inputs, evidence_sha256=reindex_synthetic(folder)
    )
    assert (
        value["status"] == "probe_verified" and value["capture_set_qualified"] is False
    )
    assert value["screenshots"] == [] and value["calibration_status"] == "not_run"


@pytest.mark.parametrize("synthetic_runtime", ["probe"], indirect=True)
@pytest.mark.parametrize(
    "kind", ["missing_install", "final_data", "calibration", "dynamic"]
)
def test_probe_success_requires_downgrade_restore_only_contract(
    synthetic_runtime, kind
):
    folder, catalog, inputs, _ = synthetic_runtime
    value = json_bytes((folder / "mutation-manifest.json").read_bytes())
    if kind == "missing_install":
        (folder / "private/install-002/install.json").unlink()
    elif kind == "final_data":
        (folder / "private/final-inventory.json").write_bytes(b"{}\n")
    elif kind == "calibration":
        value["calibration_status"] = "passed"
    else:
        value["dynamic_tests"] = [
            {
                "id": catalog.plan["batches"][0]["id"],
                "recipe_ids": catalog.plan["batches"][0]["recipe_ids"],
                "split": False,
            }
        ]
    rewrite_synthetic_manifest(folder, value)
    with pytest.raises(CaptureError, match="probe|receipt|inventory|install"):
        api().verify_run(
            folder, catalog, inputs, evidence_sha256=reindex_synthetic(folder)
        )


@pytest.mark.parametrize("command", ["run", "probe", "verify"])
def test_cli_never_returns_zero_for_contradictory_success(
    tmp_path, monkeypatch, command
):
    import l10n_checker.mutation_catalog as catalog_api
    import l10n_checker.mutation_cli as cli
    import l10n_checker.screen_manifest as manifest_api

    value = {
        "status": "qualified",
        "capture_set_qualified": False,
        "labels_created": False,
        "downgrade_verified": True,
        "restoration_verified": True,
        "calibration_status": "passed",
    }
    monkeypatch.setattr(api(), "run_config", lambda *args, **kwargs: value)
    monkeypatch.setattr(api(), "verify_run", lambda *args, **kwargs: value)
    monkeypatch.setattr(catalog_api, "read_catalog", lambda *args, **kwargs: None)
    monkeypatch.setattr(manifest_api, "Inputs", lambda *args, **kwargs: None)
    argv = [command]
    for field in ("catalog", "manifest", "recipes", "sdk", "jdk"):
        argv += ["--" + field, str(tmp_path / "synthetic")]
    argv += ["--sha256", "a" * 64]
    if command == "verify":
        argv += ["--run-dir", str(tmp_path), "--evidence-sha256", "b" * 64]
    else:
        argv += [
            "--output-dir",
            str(tmp_path / "run"),
            "--approved-output-root",
            str(tmp_path),
        ]
    assert cli.main(argv) != 0


@pytest.mark.parametrize(
    "kind",
    [
        "languages",
        "passes",
        "signing",
        "source_inputs",
        "builder",
        "toolchain",
        "source_commit",
        "matrix",
        "capture_build_identity",
        "capture_patch_set",
        "clean_gate",
        "bool_pass",
    ],
)
def test_qualification_replays_exact_metadata_contract(synthetic_runtime, kind):
    folder, catalog, inputs, _ = synthetic_runtime
    value = json_bytes((folder / "mutation-manifest.json").read_bytes())
    if kind in {"languages", "passes"}:
        value[kind].reverse()
    elif kind == "signing":
        value["signing"]["reference_certificate_sha256"] = "0" * 64
    elif kind == "source_inputs":
        value["source_inputs"]["manifest"]["sha256"] = "0" * 64
    elif kind == "source_commit":
        value["source_commit"] = "0" * 40
    elif kind in {"builder", "toolchain"}:
        value["builder_content_sha256" if kind == "builder" else "toolchain_sha256"] = (
            "0" * 64
        )
    elif kind == "matrix":
        value["observed_occurrence_matrix"] = []
    else:
        shot = next(
            r for r in value["screenshots"] if r["role"] == "clean" and r["pass"] == 1
        )
        if kind == "capture_build_identity":
            shot["build_identity_sha256"] = "0" * 64
        elif kind == "capture_patch_set":
            shot["patch_set_sha256"] = "0" * 64
        elif kind == "bool_pass":
            shot["pass"] = True
        else:
            shot["verification"] = {"passed": True}
    rewrite_synthetic_manifest(folder, value)
    with pytest.raises(
        CaptureError, match="metadata|provenance|scope|identity|mapping|control"
    ):
        api().verify_run(
            folder, catalog, inputs, evidence_sha256=reindex_synthetic(folder)
        )


@pytest.mark.parametrize(
    "status",
    ["failed", "restoration_failed", "awaiting_builder_approval", "probe_verified"],
)
def test_capture_qualification_flag_cannot_disagree_with_status(
    synthetic_runtime, status
):
    folder, catalog, inputs, _ = synthetic_runtime
    value = json_bytes((folder / "mutation-manifest.json").read_bytes())
    value["status"] = status
    rewrite_synthetic_manifest(folder, value)
    with pytest.raises(CaptureError, match="status|flag|claim"):
        api().verify_run(
            folder, catalog, inputs, evidence_sha256=reindex_synthetic(folder)
        )


@pytest.mark.parametrize("index_version", [1, 2])
def test_failed_legacy_v1_is_inspectable_only_with_an_explicit_index_pin(
    synthetic_runtime,
    index_version,
):
    folder, catalog, inputs, _ = synthetic_runtime
    value = json_bytes((folder / "mutation-manifest.json").read_bytes())
    value.update(status="failed", capture_set_qualified=False, mutation_run_version=1)
    value.pop("preservation_policy")
    value.pop("outside_rule_policy")
    value.pop("outside_rule_usage")
    for shot in value["screenshots"]:
        shot.pop("outside_rule")
        shot.pop("qualified")
    rewrite_synthetic_manifest(folder, value)
    assert (
        api().verify_run(
            folder,
            catalog,
            inputs,
            evidence_sha256=reindex_synthetic(folder, version=index_version),
        )["status"]
        == "failed"
    )
    value.update(status="qualified", capture_set_qualified=True)
    rewrite_synthetic_manifest(folder, value)
    with pytest.raises(CaptureError, match="Legacy"):
        api().verify_run(
            folder,
            catalog,
            inputs,
            evidence_sha256=reindex_synthetic(folder, version=index_version),
        )


def test_pair_identity_guard_precedes_png_and_dump_reads(tmp_path, monkeypatch):
    inputs = Inputs(MANIFEST, split="dev")
    pair = {
        "pair_version": 1,
        "protocol_version": 2,
        "screen": "not-selected",
        "language": "English",
        "build": inputs.manifest.build.model_dump(),
        "png": "NEVER_READ.png",
        "dump": "NEVER_READ.json",
    }
    (tmp_path / "pair.json").write_bytes(canonical_bytes(pair))
    original = Path.read_bytes

    def read(path):
        assert not path.name.startswith("NEVER_READ")
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", read)
    with pytest.raises(CaptureError):
        api().verified_pair(
            inputs,
            tmp_path,
            {"pair": "pair.json", "screen": "tech-picker", "language": "en", "pass": 1},
        )


def test_verified_pair_binds_state_build_and_hashes(tmp_path):
    inputs = Inputs(MANIFEST, split="dev")
    state = inputs.states["tech-picker", "en"]
    dump = dump_for(screen="tech-picker", language="English", state=state, elements=[])
    dump["build_version_code"] = 1271048
    path = write_pair(tmp_path, dump)
    data = json_bytes(path.read_bytes())
    data["build"] = inputs.manifest.build.model_dump()
    path.write_bytes(canonical_bytes(data))
    record = {"pair": path.name, "screen": "tech-picker", "language": "en", "pass": 1}
    pair, _, _, loaded = api().verified_pair(inputs, tmp_path, record)
    assert loaded.screen == "tech-picker" and pair["build"] == data["build"]
    record["pair_sha256"] = "0" * 64
    with pytest.raises(CaptureError, match="hash"):
        api().verified_pair(inputs, tmp_path, record)


def test_handoff_projects_split_plan_and_does_not_run_builder(tmp_path, monkeypatch):
    assert hasattr(api(), "write_handoff"), "Immutable builder handoff missing"
    source = tmp_path / "source"
    source.mkdir()
    path, kwargs, _, _ = synthetic_catalog(source)
    from l10n_checker.mutation_catalog import read_catalog

    catalog = read_catalog(path, digest(path.read_bytes()), **kwargs)
    # A singleton cannot be split, even when a caller requests a new APK.
    with pytest.raises(CaptureError, match="singleton"):
        api().write_handoff(
            catalog,
            catalog.plan,
            catalog.plan["batches"][0]["id"],
            {"kind": "outside_mask_pixels"},
            tmp_path / "handoff",
            kwargs["manifest"],
        )
    assert not (tmp_path / "handoff").exists()


def test_public_cli_has_run_and_offline_verify_subcommands():
    import l10n_checker.mutation_cli as cli

    with pytest.raises(SystemExit) as error:
        cli.main(["run", "--help"])
    assert error.value.code == 0
    with pytest.raises(SystemExit) as error:
        cli.main(["verify", "--help"])
    assert error.value.code == 0


def test_calibration_artifact_can_also_be_a_split_production_singleton(tmp_path):
    from types import SimpleNamespace

    assert hasattr(api(), "capture_directory"), (
        "Role-scoped capture directories missing"
    )
    identity = "batch-" + "a" * 16
    clean = "batch-" + "b" * 16
    assert api().capture_directory(
        tmp_path, identity, "calibration"
    ) != api().capture_directory(tmp_path, identity, "mutation")
    catalog = SimpleNamespace(
        control={"request": {"id": clean}},
        calibration={"request": {"id": identity}},
        plan={"screen_ids": ["tech-picker"], "batches": [{"id": identity}]},
    )
    expected = api().expected_capture_keys(catalog)
    assert len(expected) == 12
    assert (identity, "calibration", "tech-picker", "en", 1) in expected
    assert (identity, "mutation", "tech-picker", "en", 1) in expected


@pytest.mark.parametrize("replaced_handoff", [False, True])
def test_split_handoff_is_byte_deterministic_and_never_invokes_builder(
    tmp_path, monkeypatch, replaced_handoff
):
    import subprocess
    from types import SimpleNamespace

    from test_mutation_plan import inputs, named_recipe, positioned

    from l10n_checker.mutation_cli import build_requests
    from l10n_checker.mutation_plan import create_plan, load_plan

    inventory = tmp_path / "inventory"
    inventory.mkdir()
    names = ("Alpha", "Beta", "Gamma", "Delta")
    extras = [
        positioned(name, f"root/{name}", 300 + i * 150) for i, name in enumerate(names)
    ]
    kwargs = inputs(
        inventory,
        [named_recipe(name) for name in names],
        {("tech-picker", "en"): extras},
    )
    plan = create_plan(**kwargs)
    batch = next(batch for batch in plan["batches"] if len(batch["recipe_ids"]) == 2)
    catalog = SimpleNamespace(
        sha256="a" * 64, data={"builder": {"content_sha256": "b" * 64}}
    )

    def forbidden(*args, **kwargs):
        pytest.fail("Split handoff attempted an unapproved builder/process")

    monkeypatch.setattr(subprocess, "run", forbidden)
    reason = {"kind": "outside_mask_pixels", "verification_sha256": "c" * 64}
    first, handoff = api().write_handoff(
        catalog, plan, batch["id"], reason, tmp_path / "handoff-1", kwargs["manifest"]
    )
    second, _ = api().write_handoff(
        catalog, plan, batch["id"], reason, tmp_path / "handoff-2", kwargs["manifest"]
    )
    assert canonical_bytes(first) == canonical_bytes(second)
    raw = (tmp_path / "handoff-1/plan.json").read_bytes()
    assert digest(raw) == handoff["plan_sha256"]
    assert load_plan(raw, manifest=kwargs["manifest"]) == first
    assert (tmp_path / "handoff-1/build-requests.json").read_bytes() == canonical_bytes(
        build_requests(first)
    )
    assert handoff["status"] == "awaiting_builder_approval"
    parent = tmp_path / "pending-run"
    pending = parent / "builder-handoff"
    pending.mkdir(parents=True)
    for name in ("plan.json", "build-requests.json", "handoff.json"):
        (pending / name).write_bytes((tmp_path / "handoff-1" / name).read_bytes())
    tests = [{"id": batch["id"], "recipe_ids": batch["recipe_ids"], "split": True}]
    from l10n_checker.mutation_verify import split_rate

    previous = {
        "status": "awaiting_builder_approval",
        "labels_created": False,
        "catalog_sha256": catalog.sha256,
        "dynamic_tests": tests,
        "dynamic_split_rate": split_rate(tests),
        "handoff": handoff,
    }
    previous_raw = canonical_bytes(previous)
    (parent / "mutation-manifest.json").write_bytes(previous_raw)
    catalog.plan = first
    catalog.data["inputs"] = {
        "plan": {"sha256": handoff["plan_sha256"]},
        "requests": {"sha256": handoff["requests_sha256"]},
    }
    if replaced_handoff:
        replacement = {**handoff, "builder_content_sha256": "d" * 64}
        catalog.data["builder"]["content_sha256"] = "d" * 64
        (pending / "handoff.json").write_bytes(canonical_bytes(replacement))
        original_read = Path.read_bytes

        def guarded_read(path):
            assert path not in (
                pending / "plan.json",
                pending / "build-requests.json",
            ), "Replaced handoff reached untrusted payloads"
            return original_read(path)

        monkeypatch.setattr(Path, "read_bytes", guarded_read)
        with pytest.raises(CaptureError, match="handoff"):
            api().resume_evidence(
                parent, digest(previous_raw), catalog, kwargs["manifest"], tmp_path
            )
        return
    resumed = api().resume_evidence(
        parent, digest(previous_raw), catalog, kwargs["manifest"], tmp_path
    )
    assert resumed == {
        "parent_run_sha256": digest(previous_raw),
        "dynamic_tests": tests,
    }


@pytest.mark.parametrize("serial", ["emulator-5554", None])
def test_device_lock_contends_across_two_output_roots(tmp_path, monkeypatch, serial):
    import subprocess
    from types import SimpleNamespace

    runtime = api()
    root = tmp_path.resolve()
    common = root / "synthetic-git-common"
    common.mkdir()
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(stdout=str(common).encode() + b"\n"),
    )
    catalog = SimpleNamespace(plan={"screen_ids": ["synthetic-screen"]})
    monkeypatch.setattr(runtime, "read_catalog", lambda *args, **kwargs: catalog)
    monkeypatch.setattr(
        runtime,
        "Inputs",
        lambda *args, **kwargs: SimpleNamespace(
            screens=lambda: [SimpleNamespace(id="synthetic-screen")]
        ),
    )
    device_calls = []

    class SyntheticDevice:
        def __init__(self, adb, serial):
            self.serial = serial

        def run(self, *args):
            device_calls.append(args)
            assert args == ("devices",), "Device mutation before lock"
            return b"List of devices attached\nemulator-5554\tdevice\n"

    monkeypatch.setattr(runtime, "Device", SyntheticDevice)
    configs = []
    for name in ("one", "two"):
        config = dict.fromkeys(
            ("catalog", "manifest", "recipes", "sdk", "jdk"), str(root / "synthetic")
        )
        config.update(
            sha256="a" * 64,
            approved_output_root=str(root / name),
            output_dir=str(root / name / "run"),
        )
        if serial:
            config["serial"] = serial
        configs.append(config)
    entered = []

    class SyntheticRun:
        def __init__(self, catalog, inputs, folder, **kwargs):
            entered.append(folder)
            self.content = {}

        def checkpoint(self):
            pass

        def run(self, **kwargs):
            if len(entered) == 1:
                with pytest.raises(CaptureError, match="owns this device"):
                    runtime.run_config(configs[1])
            return {"status": "synthetic"}

    monkeypatch.setattr(runtime, "MutationRun", SyntheticRun)
    runtime.run_config(configs[0])
    assert len(entered) == 1
    assert device_calls == ([] if serial else [("devices",), ("devices",)])


def test_resume_rejects_parent_traversal_before_payload_reads(tmp_path, monkeypatch):
    root = tmp_path.resolve() / "approved"
    root.mkdir()
    outside = tmp_path.resolve() / "outside"
    outside.mkdir()
    parent = root / ".." / "outside"

    def forbidden(path):
        pytest.fail("Traversal reached a parent payload read")

    monkeypatch.setattr(Path, "read_bytes", forbidden)
    with pytest.raises(CaptureError, match="traversal|outside"):
        api().resume_evidence(parent, "0" * 64, None, None, root)


def test_resume_requires_independent_parent_digest_before_reading_handoff(tmp_path):
    assert hasattr(api(), "resume_evidence"), "Pinned resumable evidence missing"
    parent = tmp_path / "parent"
    parent.mkdir()
    (parent / "mutation-manifest.json").write_bytes(b"{}\n")
    with pytest.raises(CaptureError, match="parent.*hash"):
        api().resume_evidence(parent, "0" * 64, None, None, tmp_path)


@pytest.fixture
def real_capture_runtime(tmp_path, monkeypatch):
    """Exercise real preparation/capture wrappers; only device/native I/O is fake."""
    from functools import partial

    from test_mutation_device import archive
    from test_screen_capture import FakeDevice

    from l10n_checker import screen_capture

    inputs = Inputs(MANIFEST, split="dev").select_screens(screen_ids=["tech-picker"])
    inputs.manifest = inputs.manifest.model_copy(update={"resolution": [4, 2]})
    device = FakeDevice(inputs)
    monkeypatch.setattr(device, "serial", "emulator-5554", raising=False)
    monkeypatch.setattr(device, "build", lambda: inputs.manifest.build.version_code)
    run = object.__new__(api().MutationRun)
    run.folder = tmp_path.resolve() / "run"
    run.folder.mkdir()
    run.inputs, run.device = inputs, device
    run.last_inventory = api().data_inventory(
        {"private": archive(), "external": archive()}
    )
    run.plan = {"mutations": {}, "batches": []}
    run.allowed_outputs, run.clean = set(), {}
    run.content = {
        "status": "not_run",
        "capture_set_qualified": False,
        "screenshots": [],
        "dynamic_tests": [],
    }
    run.journal = {"operations": []}
    events = []
    run.install = lambda record: events.append("install")
    run.restore = lambda: events.append("restore")
    record = {
        "request": {"id": "synthetic-batch", "patch_set_sha256": "a" * 64},
        "build": inputs.manifest.build.model_dump(),
        "build_identity_sha256": "b" * 64,
    }
    run.probe = lambda: run.capture(record, "clean")
    monkeypatch.setattr(
        api(),
        "read_app_data",
        lambda device: {"private": archive(), "external": archive()},
    )
    monkeypatch.setattr(
        api(),
        "capture_manifest",
        partial(screen_capture.capture_manifest, request=device.request),
    )
    return run, record, events


@pytest.mark.parametrize("after_capture_failure", [False, True])
@pytest.mark.parametrize("measurement_only", [False, True])
def test_real_capture_wrapped_timeout_is_checkpointed_in_runtime_journal(
    real_capture_runtime, monkeypatch, after_capture_failure, measurement_only
):
    import subprocess

    from l10n_checker.capture import Device

    run, record, events = real_capture_runtime
    native = Device(Path("synthetic-adb"), run.device.serial)
    timeout = subprocess.TimeoutExpired(
        "synthetic-capture-build", 1, b"capture stdout", b"capture stderr"
    )

    def fail_native(command, **kwargs):
        assert command == [
            "synthetic-adb",
            "-s",
            run.device.serial,
            "synthetic-capture-build",
        ]
        raise timeout

    monkeypatch.setattr(subprocess, "run", fail_native)
    connects = 0

    def connect():
        nonlocal connects
        connects += 1
        if connects == 2:  # Preparation succeeds; real capture check_build fails.
            native.run("synthetic-capture-build")

    run.device.connect = connect
    if after_capture_failure:
        read_data = api().read_app_data
        reads = 0

        def inventory(device):
            nonlocal reads
            reads += 1
            if reads == 2:
                raise CaptureError("post-capture inventory failed")
            return read_data(device)

        monkeypatch.setattr(api(), "read_app_data", inventory)
    if measurement_only:
        from types import SimpleNamespace

        run.catalog = SimpleNamespace(control=record, calibration=record)
        result = run.run(measurement_only=True)
        assert result["measurement_complete"] is False
        assert result["calibration_status"] == "failed"
    else:
        result = run.run(probe_only=True)
    assert result["status"] == "failed" and not result["capture_set_qualified"]
    assert result["dynamic_tests"] == [] and events == ["install", "restore"]
    assert connects == 2
    summary_path = run.folder / "artifacts/clean/synthetic-batch/capture/summary.json"
    summary = json_bytes(summary_path.read_bytes())
    journal = json_bytes((run.folder / "journal.json").read_bytes())
    error = journal["capture_errors"][0]
    assert error["batch_id"] == record["request"]["id"] and error["role"] == "clean"
    assert error["receipt"] == str(summary_path.relative_to(run.folder))
    assert error["fatal_error_details"] == summary["fatal_error_details"]
    cause = error["fatal_error_details"]["cause"]
    assert cause["type"] == "TimeoutExpired"
    assert cause["stdout"] == "capture stdout" and cause["stderr"] == "capture stderr"
    assert not (run.folder / "builder-handoff").exists()


@pytest.mark.parametrize("failure", ["transport", "dynamic"])
@pytest.mark.parametrize(
    "cleanup", ["none", "unroot", "settings_and_unroot", "recovery"]
)
def test_real_capture_cleanup_is_journaled_without_becoming_batch_interference(
    real_capture_runtime, monkeypatch, failure, cleanup
):
    import subprocess
    from functools import partial
    from types import SimpleNamespace

    from test_screen_capture import ORIGINAL

    from l10n_checker import screen_capture
    from l10n_checker.capture import Device

    run, record, events = real_capture_runtime
    native = Device(Path("synthetic-adb"), run.device.serial)

    def fail_native(command, **kwargs):
        assert command[:3] == ["synthetic-adb", "-s", run.device.serial]
        assert len(command) == 4 and command[3] in {
            "request",
            "unroot",
            "settings",
            "recovery",
        }
        label = command[3]
        raise subprocess.TimeoutExpired(
            f"synthetic-{label}",
            1,
            f"{label} stdout".encode(),
            f"{label} stderr".encode(),
        )

    monkeypatch.setattr(subprocess, "run", fail_native)

    def request(device, screen, token, state, timeout, **kwargs):
        ready = device.request(device, screen, token, state, timeout)
        if failure == "transport":
            native.run("request")
        return {**ready, "dump": {"file": f"files/l10n-hook/{token}.json"}}

    monkeypatch.setattr(
        api(),
        "capture_manifest",
        partial(screen_capture.capture_manifest, request=request),
    )
    monkeypatch.setattr(screen_capture, "read_dump", lambda *args: b"{}")
    stop, write, unroot = (
        run.device.force_stop,
        run.device.write_file,
        run.device.unroot,
    )
    unroots = 0

    def force_stop():
        running = run.device.running
        stop()
        if cleanup == "recovery" and running:
            native.run("recovery")

    def write_file(path, data):
        if cleanup == "settings_and_unroot" and data == ORIGINAL:
            native.run("settings")
        write(path, data)

    def unroot_device():
        nonlocal unroots
        unroots += 1
        unroot()
        if unroots == 2 and cleanup in {"unroot", "settings_and_unroot"}:
            native.run("unroot")

    monkeypatch.setattr(run.device, "force_stop", force_stop)
    monkeypatch.setattr(run.device, "write_file", write_file)
    monkeypatch.setattr(run.device, "unroot", unroot_device)
    ids = ["synthetic-one", "synthetic-two"]
    run.plan = {
        "mutations": {
            identity: {"occurrences": [{"screen": "tech-picker", "language": "en"}]}
            for identity in ids
        },
        "batches": [{"id": record["request"]["id"], "recipe_ids": ids}],
    }
    run.catalog = SimpleNamespace()
    run.clean["tech-picker", "en", 1] = (b"synthetic clean", None, "c" * 64)
    monkeypatch.setattr(
        api(),
        "verified_pair",
        lambda effective, folder, captured: (
            json_bytes((folder / captured["pair"]).read_bytes()),
            b"synthetic PNG",
            None,
            None,
        ),
    )
    monkeypatch.setattr(
        api(),
        "verify_screen",
        lambda *args: {
            "passed": False,
            "pixels": {"outside": {"different_pixels": 1}},
            "changed_unmutated_elements": [],
            "occurrences": [],
        },
    )

    def handoff(catalog, plan, batch_id, reason, folder, manifest):
        events.append("split")
        assert reason["kind"] == "outside_mask_pixels"
        return {**plan, "split_history": [], "density": {}}, {
            "status": "awaiting_builder_approval"
        }

    monkeypatch.setattr(api(), "write_handoff", handoff)
    run.probe = lambda: run.capture(record, "mutation")
    result = run.run(probe_only=True)
    # D053 makes every outside failure fatal, even in a multi-recipe batch.
    split = False
    assert result["status"] == ("awaiting_builder_approval" if split else "failed")
    assert result["capture_set_qualified"] is False
    assert bool(result["dynamic_tests"]) is split
    assert events == (
        ["install", "split", "restore"] if split else ["install", "restore"]
    )
    summary = json_bytes(
        (
            run.folder / "artifacts/mutation/synthetic-batch/capture/summary.json"
        ).read_bytes()
    )
    assert len(summary["records"]) == 1 and unroots == 2
    assert bool(summary.get("settings_restored")) is (cleanup != "settings_and_unroot")
    journal = json_bytes((run.folder / "journal.json").read_bytes())
    error = journal["capture_errors"][0]
    assert error["fatal_error_details"] == summary["fatal_error_details"]
    assert (
        error["records"][0]["error_details"] == summary["records"][0]["error_details"]
    )
    if failure == "transport":
        cause = error["fatal_error_details"]["cause"]
        assert cause["type"] == "TimeoutExpired"
        assert (
            cause["stdout"] == "request stdout" and cause["stderr"] == "request stderr"
        )
    if cleanup != "none":
        assert error["cleanup_errors"] == summary["cleanup_errors"]
        expected = (
            ["settings", "unroot"] if cleanup == "settings_and_unroot" else [cleanup]
        )
        assert [e["cause"]["stdout"] for e in error["cleanup_errors"]] == [
            label + " stdout" for label in expected
        ]
        assert [e["cause"]["stderr"] for e in error["cleanup_errors"]] == [
            label + " stderr" for label in expected
        ]
