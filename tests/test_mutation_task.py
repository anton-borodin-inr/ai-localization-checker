"""Exercise the production runner offline with synthetic captures."""

import io
import tarfile
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from test_mutation_verify import png
from test_text_dump import dump_for, element

from l10n_checker import mutation_cli, mutation_task
from l10n_checker.capture import CaptureError
from l10n_checker.screen_manifest import digest, json_bytes
from l10n_checker.text_dump import canonical_bytes


@pytest.mark.parametrize(
    "output,success",
    [
        (b"Performing Streamed Install\nSuccess", True),
        (b"Performing Streamed Install\nFailure [INSTALL_FAILED_INVALID_APK]", False),
    ],
)
def test_install_requires_success_as_the_last_nonempty_line(
    tmp_path, monkeypatch, output, success
):
    apk = tmp_path / "task.apk"
    apk.write_bytes(b"task APK")
    build = SimpleNamespace(apk_sha256=digest(apk.read_bytes()))
    inputs = SimpleNamespace(manifest=SimpleNamespace(build=build))
    device = Mock()
    device.run.return_value = output + b"\n\n"
    check_build = Mock()
    monkeypatch.setattr(mutation_task, "check_build", check_build)

    if success:
        mutation_task.install(device, apk, inputs)
        check_build.assert_called_once_with(device, inputs)
    else:
        with pytest.raises(CaptureError, match="APK installation failed"):
            mutation_task.install(device, apk, inputs)
        check_build.assert_not_called()
    device.run.assert_called_once_with("install", "-r", "-d", str(apk), timeout_s=300)


@pytest.mark.parametrize(
    "malformed", [None, "empty", "garbage", "empty-tar", "missing-eof"]
)
def test_saved_games_validates_the_transferred_archive(malformed):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w") as archive:
        member = tarfile.TarInfo("./save")
        member.size = 4
        archive.addfile(member, io.BytesIO(b"save"))
    complete = stream.getvalue()
    raw = {
        None: complete,
        "empty": b"",
        "garbage": b"garbage",
        "empty-tar": b"\0" * 10240,
        "missing-eof": complete[:1024],
    }[malformed]

    def run(*args, timeout_s):
        assert args == (
            "exec-out",
            "tar",
            "-cf",
            "-",
            "-C",
            mutation_task.SAVES_PATH,
            ".",
        )
        assert timeout_s == 300
        return raw

    device = SimpleNamespace(run=run)
    if malformed is None:
        assert mutation_task.saved_games(device) == complete
    else:
        with pytest.raises((CaptureError, tarfile.TarError)):
            mutation_task.saved_games(device)


def test_run_captures_once_and_continues_after_rejecting_a_screenshot(
    tmp_path, monkeypatch
):
    screen = SimpleNamespace(id="tech-picker")
    languages = {"en": "English", "de": "German"}
    base_manifest = SimpleNamespace(
        build=SimpleNamespace(version_code="1271045"),
        resolution=[100, 60],
        protocol_version=2,
        languages=[
            SimpleNamespace(code=code, game_language=name)
            for code, name in languages.items()
        ],
    )

    def inputs(build="1271045"):
        return SimpleNamespace(
            path=tmp_path / "manifest",
            manifest=SimpleNamespace(
                **{**vars(base_manifest), "build": SimpleNamespace(version_code=build)}
            ),
            settings={"en": b"en", "de": b"de"},
            states={(screen.id, code): {} for code in languages},
            screens=lambda language=None: [screen],
            with_build=inputs,
        )

    mutations = {}
    for language in languages:
        recipe = {
            "id": language,
            "key": "City",
            "original": "Stadt" if language == "de" else "City",
            "replacement": "Ville",
            "operation": "replace",
            "intended_class": "wrong_language",
        }
        mutations[language] = {
            "recipe": recipe,
            "patch": {"replacement": "Ville"},
            "occurrences": [
                {
                    "actor_path": "target",
                    "input_text": recipe["original"],
                    "screen": screen.id,
                    "language": language,
                }
            ],
        }

    plan = {
        "screen_ids": [screen.id],
        "mutations": mutations,
        "clean_build": {"id": "control", "recipe_ids": []},
        "batches": [{"id": "batch", "recipe_ids": list(mutations)}],
        "seed": 59,
    }
    installs, frames, cleanup = [], [], []

    class Device:
        serial = "emulator-5554"

        def force_stop(self):
            pass

        def pid(self):
            return ""

        def write_file(self, _path, payload):
            self.settings = payload

        def read_file(self, _path):
            return self.settings

        def check_cutout(self):
            pass

        def size(self):
            return (100, 60)

        def build(self):
            return installs[-1]

        def screenshot(self):
            frames.append((self.build(), self.settings.decode()))
            if self.build() == "1271046":
                return png([((99, 59), (18, 20, 30, 250))])
            return png()

        def shell(self, *_args):
            pass

        def root(self):
            cleanup.append("root")

        def unroot(self):
            cleanup.append("unroot")

    def read_dump(device, _event, expected):
        lang = device.settings.decode()
        mutated = device.build() == "1271046"
        target = (
            "Ville"
            if mutated and lang == "de"
            else mutations[lang]["recipe"]["original"]
        )
        other = element("Sidebar", "sidebar")
        if mutated:
            other = element("Side...", "sidebar", bounds=[12, 20, 90, 40])
        dump = dump_for(
            size=[100, 60],
            language=languages[lang],
            elements=[
                element(
                    target,
                    "target",
                    input_text=target,
                    source_key=None,
                    ellipsis_applied=False,
                ),
                other,
            ],
        )
        if mutated:
            dump["viewport"] = [1, 0, 100, 60]
        assert dump["language"] == expected["language"]
        return canonical_bytes(dump)

    monkeypatch.setattr(mutation_task, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(mutation_task, "Inputs", lambda path, split: inputs())
    monkeypatch.setattr(mutation_task, "load_plan", lambda *args, **kwargs: plan)
    monkeypatch.setattr(
        mutation_task,
        "load_recipes",
        lambda _raw: SimpleNamespace(
            recipes=[
                SimpleNamespace(id=k, model_dump=lambda row=row: row["recipe"])
                for k, row in mutations.items()
            ]
        ),
    )
    monkeypatch.setattr(
        mutation_task,
        "read_builds",
        lambda *args: (
            "reference",
            {"control": ("clean", "1271045"), "batch": ("mutated", "1271046")},
            "a" * 40,
        ),
    )
    monkeypatch.setattr(mutation_task, "Device", lambda *_: Device())
    monkeypatch.setattr(
        mutation_task.subprocess, "check_output", lambda *a, **kw: "abc"
    )
    monkeypatch.setattr(mutation_task, "assert_idle", lambda device: None)
    monkeypatch.setattr(mutation_task, "check_build", lambda device, inputs: None)
    monkeypatch.setattr(mutation_task, "app_snapshot", lambda *args: "prepared")
    monkeypatch.setattr(
        mutation_task, "restore", lambda *args: cleanup.append("restore")
    )
    monkeypatch.setattr(
        mutation_task,
        "install",
        lambda device, apk, effective: installs.append(
            effective.manifest.build.version_code
        ),
    )
    monkeypatch.setattr(mutation_task, "unciv_in_foreground", lambda device: None)
    monkeypatch.setattr(
        mutation_task,
        "request_screen",
        lambda *args, **kwargs: {"dump": {"file": "dump"}},
    )
    monkeypatch.setattr(mutation_task, "read_dump", read_dump)
    (tmp_path / "plan").touch()
    (tmp_path / "recipes").touch()
    task = tmp_path / "Developer/sandbox/task"
    root = tmp_path / "data/runs"
    output = root / "run"
    config = {
        "manifest": tmp_path / "manifest",
        "plan": tmp_path / "plan",
        "recipes": tmp_path / "recipes",
        "catalog": task / "builds.json",
        "task_dir": task,
        "approved_output_root": root,
        "output_dir": output,
        "serial": "emulator-5554",
        "sdk": tmp_path,
        "jdk": tmp_path,
        "sha256": "b" * 64,
    }
    arguments = ["run"]
    for key, value in config.items():
        arguments.extend((f"--{key.replace('_', '-')}", str(value)))
    assert mutation_cli.main(arguments) == 0
    assert cleanup == ["root", "restore", "unroot"]
    assert installs == ["1271045", "1271046"]
    assert frames == [(build, language) for build in installs for language in languages]
    manifest = json_bytes((output / "mutation-manifest.json").read_bytes())
    assert manifest["status"] == "completed"
    assert manifest["restoration_verified"] and not manifest["labels_created"]
    rejected, retained = manifest["screenshots"][2:]
    assert rejected["language"] == "en" and "png" not in rejected
    assert not rejected["verification"]["qualified"]
    assert retained["language"] == "de" and retained["verification"]["qualified"]
    assert retained["review_flags"][0]["actor_path"] == "sidebar"
    assert (output / retained["png"]).is_file()
    assert len(list(output.glob("*.png"))) == 3
    assert not list(output.glob("split-*.json"))

    run = json_bytes((output / "run.json").read_bytes())
    assert run["status"] == "completed"
    assert run["unqualified_screenshots"] == [
        {
            "batch_id": "batch",
            "screen": screen.id,
            "language": "en",
            "reasons": rejected["verification"]["qualification_reasons"],
        }
    ]
    assert run["unqualified_screenshots"][0]["reasons"][0]["reason"] == (
        "Intended translation not visible"
    )
    assert run["occurrences_by_class"] == {
        "wrong_language": {"intended_occurrences": 2, "qualified_occurrences": 1}
    }
    assert run["measurements"] == [
        {
            "batch_id": "batch",
            "screen": screen.id,
            "language": language,
            "outside_mask_pixels": {
                "different_pixels": 1,
                "max_channel_deltas": [8, 0, 0, 5],
            },
            "moved_or_resized_unmutated_groups": 1,
        }
        for language in languages
    ]


@pytest.mark.parametrize("include_standalone", [False, True])
def test_build_list_can_include_an_unused_standalone_apk(
    tmp_path, monkeypatch, include_standalone
):
    def write_apk(name):
        path = tmp_path / (name + ".apk")
        with zipfile.ZipFile(path, "w") as apk:
            for entry in mutation_task.TRANSLATIONS:
                apk.writestr(entry.removeprefix("android/"), b"Key = Value\n")
        return {"file": path.name, "sha256": digest(path.read_bytes())}

    reference, control = write_apk("reference"), write_apk("control")
    builds = {"control": control}
    if include_standalone:
        builds["standalone"] = {"file": "absent.apk", "sha256": "0" * 64}
    source = "a" * 40
    raw = canonical_bytes(
        {
            "source_commit": source,
            "builder_commit": "b" * 40,
            "reference": reference,
            "artifacts": builds,
        }
    )
    path = tmp_path / "builds.json"
    path.write_bytes(raw)
    monkeypatch.setattr(
        mutation_task,
        "build_requests",
        lambda _plan: {
            "requests": [
                {"id": "control", "role": "clean", "patches": []},
                {"id": "standalone", "role": "calibration"},
            ]
        },
    )
    inputs = SimpleNamespace(
        manifest=SimpleNamespace(
            build=SimpleNamespace(
                model_dump=lambda: {
                    "version_code": "1",
                    "apk_sha256": reference["sha256"],
                }
            )
        )
    )

    def inspect(apk):
        return {
            "version_code": {"reference.apk": "1", "control.apk": "2"}[apk.name],
            "certificate_sha256": "same-key",
            "normalized_manifest": b"same-payload",
        }

    tools = SimpleNamespace(inspect=inspect)
    _, artifacts, _ = mutation_task.read_builds(
        path, digest(raw), {"fork_commit": source}, inputs, tools
    )
    assert set(artifacts) == {"control"}

    bad = canonical_bytes(
        {
            **json_bytes(raw),
            "artifacts": {**builds, "unknown": control},
        }
    )
    path.write_bytes(bad)
    with pytest.raises(CaptureError, match="Build list differs from plan"):
        mutation_task.read_builds(
            path, digest(bad), {"fork_commit": source}, inputs, tools
        )
