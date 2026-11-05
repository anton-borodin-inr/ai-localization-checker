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
    archives = {
        "private": archive({"files/GameSettings.json": settings_raw}),
        "external": archive(
            {"files/SaveFiles/" + name: raw for name, raw in inputs.fixtures.items()}
        ),
        "device_encrypted": archive({"synthetic": b"unchanged"}),
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

        def __init__(self):
            self.apk = catalog.apk_path(
                {"apk": catalog.data["reference"]["apk"]}
            ).read_bytes()
            self.calls = []

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
                return archives[
                    next(name for name, path in DATA_ROOTS.items() if path == args[-2])
                ]
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

    device = SyntheticDevice()
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(subprocess, "run", native)
        monkeypatch.setattr(runtime, "prepare_device", prepare)
        monkeypatch.setattr(runtime, "capture_manifest", capture)
        run = runtime.MutationRun(
            catalog,
            inputs,
            root / "outputs/synthetic-run",
            approved_root=root / "outputs",
            device=device,
            tools=kwargs["tools"],
        )
        result = run.run()
        probe = runtime.MutationRun(
            catalog,
            inputs,
            root / "outputs/synthetic-probe",
            approved_root=root / "outputs",
            device=device,
            tools=kwargs["tools"],
        )
        probe_result = probe.run(probe_only=True)
    assert result["status"] == "qualified", run.journal
    assert probe_result["status"] == "probe_verified", probe.journal
    assert result["capture_set_qualified"] is True and result["labels_created"] is False
    assert device.build() == "1271048"
    assert (
        len(result["screenshots"]) == len(runtime.expected_capture_keys(catalog)) == 60
    )
    return {
        "completed": (run.folder, catalog, inputs, result),
        "probe": (probe.folder, catalog, inputs, probe_result),
    }


@pytest.fixture(params=["completed"])
def synthetic_runtime(synthetic_completed_runtime, tmp_path, request):
    import shutil

    folder, catalog, inputs, result = synthetic_completed_runtime[request.param]
    target = tmp_path.resolve() / "synthetic-run"
    shutil.copytree(folder, target)
    return target, catalog, inputs, result


def reindex_synthetic(folder, version=2):
    files = {
        str(p.relative_to(folder)): digest(p.read_bytes())
        for p in folder.rglob("*")
        if p.is_file() and p != folder / "evidence-index.json"
    }
    raw = canonical_bytes({"version": version, "files": files})
    (folder / "evidence-index.json").write_bytes(raw)
    return digest(raw)


def test_synthetic_successful_orchestration_replays_offline(synthetic_runtime):
    folder, catalog, inputs, _ = synthetic_runtime
    value = api().verify_run(
        folder,
        catalog,
        inputs,
        evidence_sha256=digest((folder / "evidence-index.json").read_bytes()),
    )
    assert value["status"] == "qualified" and len(value["screenshots"]) == 60


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
        match="receipt|backup|inventory|install|reference|environment|capture|manifest",
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


def test_failed_legacy_v1_is_inspectable_only_with_an_explicit_index_pin(
    synthetic_runtime,
):
    folder, catalog, inputs, _ = synthetic_runtime
    value = json_bytes((folder / "mutation-manifest.json").read_bytes())
    value.update(status="failed", capture_set_qualified=False)
    rewrite_synthetic_manifest(folder, value)
    assert (
        api().verify_run(
            folder,
            catalog,
            inputs,
            evidence_sha256=reindex_synthetic(folder, version=1),
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
            evidence_sha256=reindex_synthetic(folder, version=1),
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
def test_real_capture_wrapped_timeout_is_checkpointed_in_runtime_journal(
    real_capture_runtime, monkeypatch, after_capture_failure
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
    split = failure == "dynamic" and cleanup == "none"
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
