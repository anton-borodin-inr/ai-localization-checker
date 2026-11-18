"""Disposable dev captures with a task-scoped APK set and app-state snapshot."""

import io
import re
import subprocess
import tarfile
import uuid
import zipfile
from collections import Counter
from pathlib import Path

from l10n_checker.app_data import validate_tar
from l10n_checker.capture import (
    PACKAGE,
    REPO_ROOT,
    SETTINGS_PATH,
    Device,
    filename,
    png_size,
    preserve_cleanup,
    unciv_in_foreground,
)
from l10n_checker.hook import request_screen
from l10n_checker.mutation_catalog import (
    TRANSLATIONS,
    ApkTools,
    apk_payloads,
    apply_patches,
    fields,
    invariant_payloads,
    no_symlinks,
    require,
)
from l10n_checker.mutation_cli import build_requests
from l10n_checker.mutation_device import assert_idle
from l10n_checker.mutation_plan import load_plan
from l10n_checker.mutation_recipes import load_recipes
from l10n_checker.mutation_verify import occurrence_matrix, verify_screen
from l10n_checker.screen_capture import (
    SAVES_PATH,
    check_build,
    manifest_output_directory,
    save_inventory,
    write_json,
)
from l10n_checker.screen_manifest import Inputs, digest, json_bytes
from l10n_checker.text_dump import canonical_bytes, load_dump, read_dump, rgba_digest

LANGUAGES = ["en", "de"]


def read_builds(path, expected_sha, plan, inputs, tools):
    """Bind each requested patch to one signed APK without retaining proof files."""
    raw = path.read_bytes()
    require(digest(raw) == expected_sha, "Build list differs from approved digest")
    value = json_bytes(raw)
    fields(value, {"source_commit", "builder_commit", "reference", "artifacts"})
    require(
        value["source_commit"] == plan["fork_commit"]
        and re.fullmatch(r"[a-f0-9]{40}", value["builder_commit"]),
        "Invalid source/builder commit",
    )
    requests = {r["id"]: r for r in build_requests(plan)["requests"]}
    # The builder contract still includes a standalone APK that production skips.
    needed = {i: r for i, r in requests.items() if r["role"] != "calibration"}
    artifact_records = value["artifacts"]
    require(
        isinstance(artifact_records, dict)
        and needed.keys() <= artifact_records.keys() <= requests.keys(),
        "Build list differs from plan",
    )

    def load_apk(record, build=None):
        fields(record, {"file", "sha256"})
        name = record["file"]
        require(
            re.fullmatch(r"[A-Za-z0-9_.-]+\.apk", name) is not None,
            "Invalid task APK filename",
        )
        apk = no_symlinks(path.parent / name)
        contents = apk.read_bytes()
        require(digest(contents) == record["sha256"], "Task APK digest differs")
        identity = tools.inspect(apk)
        effective = inputs.manifest.build.model_dump()
        effective.update(
            version_code=identity["version_code"], apk_sha256=record["sha256"]
        )
        require(build is None or build == effective, "Reference APK differs from pin")
        return apk, contents, identity, effective

    reference, stock, stock_identity, reference_build = load_apk(
        value["reference"], inputs.manifest.build.model_dump()
    )
    with zipfile.ZipFile(io.BytesIO(stock)) as archive:
        originals = {
            name: archive.read(name.removeprefix("android/")) for name in TRANSLATIONS
        }
    artifacts = {}
    clean_payloads = None
    version_codes = {reference_build["version_code"]}
    for identity, request in sorted(
        needed.items(), key=lambda pair: bool(pair[1]["patches"])
    ):
        apk, contents, metadata, build = load_apk(artifact_records[identity])
        require(
            metadata["certificate_sha256"] == stock_identity["certificate_sha256"]
            and build["version_code"] not in version_codes,
            "Task APK signer mismatch or duplicate version code",
        )
        version_codes.add(build["version_code"])
        payloads = invariant_payloads(
            apk_payloads(contents, apply_patches(originals, request["patches"])),
            metadata["normalized_manifest"],
        )
        if request["role"] == "clean":
            clean_payloads = payloads
        require(payloads == clean_payloads, "Nontranslation APK payload drift")
        artifacts[identity] = (apk, build)
    return reference, artifacts, value["builder_commit"]


def saved_games(device):
    raw = device.run(
        "exec-out", "tar", "-cf", "-", "-C", SAVES_PATH, ".", timeout_s=300
    )
    validate_tar(raw)
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        require(
            all(member.isfile() or member.isdir() for member in archive.getmembers()),
            "Prepared saves must be regular files and directories",
        )
    return raw


def app_snapshot(device, inputs, folder):
    """Record prepared settings and saves once and reuse them across attempts."""
    stat = device.stat(SETTINGS_PATH)
    require(stat is not None, "Prepared game settings are missing")
    settings = device.read_file(SETTINGS_PATH)
    require(
        isinstance(json_bytes(settings), dict)
        and len(settings) == int(stat.split()[3]),
        "Incomplete prepared settings",
    )
    saves = saved_games(device)
    inventory = save_inventory(saves)
    for name, payload in inputs.fixtures.items():
        require(
            inventory.get("./" + name) == digest(payload),
            f"Invalid prepared save: {name}",
        )
    binding = {
        "serial": device.serial,
        "reference": inputs.manifest.build.apk_sha256,
        "settings_stat": stat,
        "settings_sha256": digest(settings),
        "saves_sha256": digest(saves),
    }
    state = folder / "snapshot.json"
    if state.exists():
        old = json_bytes(no_symlinks(state).read_bytes())
        original_settings = no_symlinks(folder / "GameSettings.json").read_bytes()
        original_saves = no_symlinks(folder / "SaveFiles.tar").read_bytes()
        require(
            all(old[key] == binding[key] for key in binding if key != "saves_sha256")
            and old["saves_sha256"] == digest(original_saves)
            and original_settings == settings
            and save_inventory(original_saves) == inventory,
            "Prepared app state differs from the task snapshot",
        )
        return original_settings, original_saves, stat
    folder.mkdir(mode=0o700, exist_ok=False)
    (folder / "GameSettings.json").write_bytes(settings)
    (folder / "SaveFiles.tar").write_bytes(saves)
    write_json(state, binding)
    return settings, saves, stat


def install(device, apk, inputs):
    require(
        digest(apk.read_bytes()) == inputs.manifest.build.apk_sha256,
        "APK changed before install",
    )
    device.force_stop()
    result = device.run("install", "-r", "-d", str(apk), timeout_s=300)
    require(result.decode().strip() == "Success", "APK installation failed")
    check_build(device, inputs)


def restore(device, reference, inputs, snapshot):
    settings, saves, stat = snapshot
    install(device, reference, inputs)
    require(
        device.shell("pm", "clear", PACKAGE).strip() == "Success",
        "Could not clear task app data",
    )
    uid, gid, mode, _size = stat.split()
    settings_dir = str(Path(SETTINGS_PATH).parent)
    device.shell("mkdir", "-p", settings_dir, SAVES_PATH)
    device.shell("chown", f"{uid}:{gid}", settings_dir)
    device.write_file(SETTINGS_PATH, settings)
    device.shell("chown", f"{uid}:{gid}", SETTINGS_PATH)
    device.shell("chmod", mode, SETTINGS_PATH)
    device.run("exec-in", f"tar -xf - -C {SAVES_PATH}", input=saves, timeout_s=300)
    require(
        device.stat(SETTINGS_PATH) == stat
        and device.read_file(SETTINGS_PATH) == settings
        and save_inventory(saved_games(device)) == save_inventory(saves),
        "Task snapshot restoration failed",
    )


def capture_build(device, inputs, mutations, folder, batch, role, clean, records):
    """Capture each screen and language once and retain eligible review PNGs."""
    build = inputs.manifest.build
    size = tuple(inputs.manifest.resolution)
    languages = {lang.code: lang.game_language for lang in inputs.manifest.languages}
    for language in LANGUAGES:
        settings = inputs.settings[language]
        device.force_stop()
        require(not device.pid(), "Unciv still running before settings write")
        device.write_file(SETTINGS_PATH, settings)
        for screen in inputs.screens(language):
            key = (screen.id, language)
            state = inputs.states[key]
            token = "i59-" + uuid.uuid4().hex
            readiness = request_screen(
                device, screen.id, token, state, 90, protocol_version=2
            )
            event = readiness.get("dump")
            require(event is not None, "Capture is missing an engine dump")
            unciv_in_foreground(device)
            device.check_cutout()
            require(
                device.size() == size and device.build() == build.version_code,
                "Device capture identity changed",
            )
            png = device.screenshot()
            require(
                png_size(png) == size and device.size() == size,
                "Invalid capture dimensions",
            )
            unciv_in_foreground(device)
            device.check_cutout()
            dump = read_dump(
                device,
                event,
                {
                    "screen": screen.id,
                    "language": languages[language],
                    "build_version_code": int(build.version_code),
                    "state_sha256": digest(canonical_bytes(state)),
                    "image_size": list(size),
                },
            )
            require(
                device.read_file(SETTINGS_PATH) == settings,
                "Settings changed during capture",
            )
            record = {
                "batch_id": batch,
                "role": role,
                "screen": screen.id,
                "language": language,
                "rgba_sha256": rgba_digest(png),
                "dump_sha256": digest(dump),
            }
            if role == "clean":
                clean[key] = (png, load_dump(dump))
            else:
                before_png, before_dump = clean[key]
                verification = verify_screen(
                    before_png,
                    png,
                    before_dump,
                    load_dump(dump),
                    mutations,
                )
                record["review_flags"] = verification.pop("review_flags")
                record["verification"] = verification
                record["patches"] = [
                    mutation["patch"]
                    for mutation in mutations
                    if any(
                        o["screen"] == screen.id and o["language"] == language
                        for o in mutation["occurrences"]
                    )
                ]
            records.append(record)
            if role == "clean" or record["verification"]["qualified"]:
                name = filename(
                    screen.id,
                    language,
                    "x".join(map(str, size)),
                    batch,
                    build.version_code,
                )
                with (folder / name).open("xb") as stream:
                    stream.write(png)
                record["png"] = name
            # Only this request's hook file is removed after it has been consumed.
            device.shell("run-as", PACKAGE, "rm", event["file"])
        device.force_stop()


def run_task(config, *, command):
    inputs = Inputs(Path(config["manifest"]), split="dev")
    plan = load_plan(Path(config["plan"]).read_bytes(), manifest=inputs.path)
    require(
        inputs.manifest.protocol_version == 2
        and plan["screen_ids"] == [screen.id for screen in inputs.screens()]
        and set(inputs.states)
        == {
            (screen, language)
            for screen in plan["screen_ids"]
            for language in LANGUAGES
        }
        and {
            recipe.id: recipe.model_dump()
            for recipe in load_recipes(Path(config["recipes"]).read_bytes()).recipes
        }
        == {identity: row["recipe"] for identity, row in plan["mutations"].items()},
        "Task plan must match the complete dev recipes and manifest",
    )
    catalog = no_symlinks(Path(config["catalog"]))
    reference, builds, builder = read_builds(
        catalog,
        config["sha256"],
        plan,
        inputs,
        ApkTools(config["sdk"], config["jdk"]),
    )
    folder = manifest_output_directory(Path(config["output_dir"]), False)
    root = manifest_output_directory(Path(config["approved_output_root"]), False)
    task = no_symlinks(Path(config["task_dir"]))
    require(
        folder.is_relative_to(root)
        and folder != root
        and root.is_relative_to(REPO_ROOT / "data/runs")
        and task.is_relative_to(Path.home() / "Developer/sandbox")
        and task != Path.home() / "Developer/sandbox"
        and catalog.parent == task,
        "Use the approved run root and a dedicated Developer sandbox task directory",
    )
    device = Device(Path(config["sdk"]) / "platform-tools/adb", config.get("serial"))
    require(
        device.serial and re.fullmatch(r"emulator-\d+", device.serial),
        "Select the approved emulator serial",
    )
    folder.mkdir(mode=0o700, parents=True, exist_ok=False)
    run = {
        "run_id": folder.name,
        "requests_sent": 0,
        "token_usage": {},
        "estimated_cost_usd": 0,
        "command": command,
        "config": config,
        "commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
        ).strip(),
        "builder_commit": builder,
        "seed": plan["seed"],
        "status": "failed",
    }
    records, clean = [], {}
    result = {
        "status": "failed",
        "restoration_verified": False,
        "labels_created": False,
    }
    try:
        assert_idle(device)
        check_build(device, inputs)
        with preserve_cleanup(device.unroot, "Unroot"):
            device.root()
            snapshot = app_snapshot(device, inputs, task / "snapshot")

            def restore_task():
                restore(device, reference, inputs, snapshot)
                result["restoration_verified"] = True

            with preserve_cleanup(restore_task, "Reference restoration"):
                control = plan["clean_build"]
                for batch in [control, *plan["batches"]]:
                    identity = batch["id"]
                    apk, build = builds[identity]
                    effective = inputs.with_build(build)
                    install(device, apk, effective)
                    capture_build(
                        device,
                        effective,
                        [plan["mutations"][i] for i in batch["recipe_ids"]],
                        folder,
                        identity,
                        "clean" if batch is control else "mutation",
                        clean,
                        records,
                    )
        result["status"] = "completed"
    except BaseException as exc:
        run["failure"] = str(exc)
        if getattr(exc, "cleanup_errors", None):
            run["cleanup_errors"] = exc.cleanup_errors
        raise
    finally:
        measurements, unqualified = [], []
        for record in records:
            if record["role"] == "clean":
                continue
            identity = {key: record[key] for key in ("batch_id", "screen", "language")}
            verification = record["verification"]
            measurements.append({**identity, **verification.pop("measurements")})
            if verification["qualification_reasons"]:
                unqualified.append(
                    {**identity, "reasons": verification["qualification_reasons"]}
                )
        matrix = occurrence_matrix(records)
        intended, qualified = Counter(), Counter()
        for row in matrix:
            kind = row["intended_class"]
            intended[kind] += row["intended_occurrences"]
            qualified[kind] += row["qualified_occurrences"]
        result.update(screenshots=records, observed_occurrence_matrix=matrix)
        run.update(
            status=result["status"],
            measurements=measurements,
            unqualified_screenshots=unqualified,
            occurrences_by_class={
                kind: {
                    "intended_occurrences": intended[kind],
                    "qualified_occurrences": qualified[kind],
                }
                for kind in sorted(intended)
            },
        )
        write_json(folder / "mutation-manifest.json", result)
        write_json(folder / "run.json", run)
    return result
