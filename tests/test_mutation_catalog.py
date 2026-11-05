"""Catalog boundaries use real bytes, never fabricated signing evidence."""

import importlib
import importlib.util
import io
import zipfile
from pathlib import Path

import pytest

from l10n_checker.capture import CaptureError
from l10n_checker.screen_manifest import digest
from l10n_checker.text_dump import canonical_bytes


def api():
    assert importlib.util.find_spec("l10n_checker.mutation_catalog") is not None, (
        "Catalog reader missing"
    )
    return importlib.import_module("l10n_checker.mutation_catalog")


def test_graph_checks_every_nested_reference_and_retains_verified_bytes(tmp_path):
    raw = b"translation bytes\n"
    (tmp_path / "leaf").write_bytes(raw)
    leaf = {"path": "leaf", "bytes": len(raw), "sha256": digest(raw)}
    record = canonical_bytes({"translations": [leaf]})
    (tmp_path / "record.json").write_bytes(record)
    ref = {"path": "record.json", "bytes": len(record), "sha256": digest(record)}
    graph = api().HashGraph(tmp_path)
    assert graph.read(ref) == record
    assert graph.read(leaf) == raw
    assert len(graph.files) == 2
    (tmp_path / "leaf").write_bytes(b"modified")
    with pytest.raises(CaptureError, match="changed|hash"):
        graph.recheck()


@pytest.mark.parametrize(
    "kind", ["escape", "absolute", "symlink", "size", "hash", "extra", "bool_size"]
)
def test_invalid_reference_rejected(tmp_path, kind):
    (tmp_path / "leaf").write_bytes(b"x")
    ref = {"path": "leaf", "bytes": 1, "sha256": digest(b"x")}
    if kind == "escape":
        ref["path"] = "../outside"
    elif kind == "absolute":
        ref["path"] = str(tmp_path / "leaf")
    elif kind == "symlink":
        (tmp_path / "link").symlink_to(tmp_path / "leaf")
        ref["path"] = "link"
    elif kind == "size":
        ref["bytes"] = 2
    elif kind == "hash":
        ref["sha256"] = "0" * 64
    elif kind == "extra":
        ref["unused"] = 1
    else:
        ref["bytes"] = True
    with pytest.raises(CaptureError):
        api().HashGraph(tmp_path).read(ref)


def test_literal_patch_bytes_and_no_accumulation():
    file = "android/assets/jsons/translations/English.properties"
    original = {file: b"# retained\r\n? = \r\nMining = \r\n"}
    patches = [
        {
            "file": file,
            "operation": "replace",
            "key": "?",
            "original": "",
            "replacement": "Help",
        },
        {
            "file": file,
            "operation": "add",
            "key": "+",
            "original": None,
            "replacement": "Increase",
        },
    ]
    expected = b"# retained\r\n? = Help\r\nMining = \r\n+ = Increase\r\n"
    assert api().apply_patches(original, patches)[file] == expected
    assert api().apply_patches(original, patches)[file] == expected
    patches[0]["original"] = "wrong"
    with pytest.raises(CaptureError, match="original"):
        api().apply_patches(original, patches)


def test_native_certificate_parser_rejects_ambiguity():
    text = "Signer #1 certificate SHA-256 digest: " + "a" * 64 + "\n"
    assert api().certificate(text) == "a" * 64
    with pytest.raises(CaptureError):
        api().certificate(text + text.replace("#1", "#2"))


def test_sdk37_v2_signer_certificate_format():
    text = (
        "Number of signers: 1\nV2 Signer: certificate SHA-256 digest: "
        + "b" * 64
        + "\n"
    )
    assert api().certificate(text) == "b" * 64
    with pytest.raises(CaptureError):
        api().certificate(text.replace("signers: 1", "signers: 2"))


def test_normalization_changes_only_one_version_attribute():
    text = "  A: android:versionCode(0x0101021b)=(type 0x10)0x1\n  A: android:debuggable=true\n"
    normalized = api().normalize_manifest(text)
    assert "debuggable=true" in normalized
    assert "<allocated-versionCode>" in normalized
    with pytest.raises(CaptureError):
        api().normalize_manifest(text + text)


def test_apk_translation_bytes_not_only_inventory_hashes():
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as z:
        z.writestr("assets/jsons/translations/English.properties", b"? = Help\n")
    name = "android/assets/jsons/translations/English.properties"
    with pytest.raises(CaptureError, match="translation"):
        api().apk_payloads(stream.getvalue(), {name: b"? = Wrong\n"})


def test_duplicate_apk_members_rejected():
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as z:
        z.writestr("a", b"x")
        with pytest.warns(UserWarning):
            z.writestr("a", b"x")
    with pytest.raises(CaptureError, match="Duplicate"):
        api().apk_payloads(stream.getvalue(), {})


def synthetic_catalog(tmp_path):
    from test_mutation_plan import MANIFEST, inputs

    from l10n_checker.mutation_cli import build_requests
    from l10n_checker.mutation_plan import create_plan
    from l10n_checker.screen_manifest import json_bytes

    inventory = tmp_path / "inventory"
    inventory.mkdir()
    kwargs = inputs(inventory)
    plan = create_plan(**kwargs)
    translations = {name: b"Mining = \n" for name in api().TRANSLATIONS}

    def apk(code, texts):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as z:
            z.writestr("AndroidManifest.xml", code.encode())
            z.writestr("classes.dex", b"synthetic-not-a-signed-apk")
            for name, raw in texts.items():
                z.writestr(name.removeprefix("android/"), raw)
        return stream.getvalue()

    def store(name, raw):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        return {"path": name, "bytes": len(raw), "sha256": digest(raw)}

    reference_raw = apk("1271048", translations)
    manifest = json_bytes(MANIFEST.read_bytes())
    manifest["build"]["apk_sha256"] = digest(reference_raw)
    authority = tmp_path / "authority/screens.json"
    authority.parent.mkdir()
    authority.write_bytes(canonical_bytes(manifest))
    authority.with_name("split.json").write_bytes(
        MANIFEST.with_name("split.json").read_bytes()
    )
    plan["source_manifest_sha256"] = digest(authority.read_bytes())
    requests = build_requests(plan)
    files = {
        name: store("builder/" + name, b"synthetic-test-only")
        for name in (
            "l10n_apk_builder.py",
            "l10n_builder_runtime.py",
            "l10n-builder.init.gradle",
        )
    }
    builder = digest(
        canonical_bytes({name: ref["sha256"] for name, ref in files.items()})
    )
    pin = {name: digest(raw) for name, raw in translations.items()}
    toolchain = store("toolchain.json", canonical_bytes({"test_fixture": True}))
    data = {
        "catalog_version": 1,
        "source_commit": manifest["build"]["fork_commit"],
        "source_tree": "a" * 40,
        "checker_commit": api().CHECKER_COMMIT,
        "builder": {
            "content_sha256": builder,
            "files": files,
            "git_head": "a" * 40,
            "worktree_dirty": True,
        },
        "inputs": {
            name: store("inputs/" + name + ".json", raw)
            for name, raw in {
                "plan": canonical_bytes(plan),
                "requests": canonical_bytes(requests),
                "manifest": authority.read_bytes(),
                "split": authority.with_name("split.json").read_bytes(),
                "recipes": kwargs["recipes"].read_bytes(),
            }.items()
        },
        "reference": {
            "version_code": "1271048",
            "apk": store("reference.apk", reference_raw),
        },
        "signing": {
            "reference_certificate_sha256": "b" * 64,
            "builder_certificate_sha256": "b" * 64,
            "reference_apk_sha256": digest(reference_raw),
        },
        "installation": api().INSTALLATION,
        "qualification": {
            "stage": "built_unqualified",
            "production_ready": False,
            "device_verification": "not_run_part_c",
            "labels_created": False,
        },
        "source_inventory": store("source-inventory.json", canonical_bytes(pin)),
        "source_assets": store(
            "source-assets.json",
            canonical_bytes(
                {
                    name.removeprefix("android/"): checksum
                    for name, checksum in pin.items()
                }
            ),
        ),
        "source_translations": {
            name: store("original/" + Path(name).name, raw)
            for name, raw in translations.items()
        },
        "toolchain": toolchain,
        "empty_control_id": plan["clean_build"]["id"],
        "artifacts": [],
    }
    for request in requests["requests"]:
        identity = digest(
            canonical_bytes(
                {
                    "identity_version": 1,
                    "source_commit": data["source_commit"],
                    "patch_set_sha256": request["patch_set_sha256"],
                    "builder_sha256": builder,
                    "toolchain_sha256": toolchain["sha256"],
                    "certificate_sha256": "b" * 64,
                }
            )
        )
        code = str(1800000000 + int(identity, 16) % 100000000)
        expected = api().apply_patches(translations, request["patches"])
        raw = apk(code, expected)
        prefix = "batches/" + request["id"] + "/"
        payloads = api().apk_payloads(raw, expected)
        payload_ref = store(prefix + "payloads.json", canonical_bytes(payloads))
        normalized = store(prefix + "manifest.txt", b"normalized")
        record = {
            "record_version": 1,
            "request": request,
            "build_identity_sha256": identity,
            "build": {
                **manifest["build"],
                "version_code": code,
                "apk_sha256": digest(raw),
            },
            "certificate_sha256": "b" * 64,
            "apk": store(prefix + "app.apk", raw),
            "translations": {
                name: {
                    "source_sha256": pin[name],
                    "file": store(prefix + Path(name).name, value),
                }
                for name, value in expected.items()
            },
            "zip_payloads": payload_ref,
            "normalized_manifest": normalized,
            "source_audits": [
                {
                    "files_verified": len(pin),
                    "expected_inventory_sha256": digest(
                        canonical_bytes(
                            {
                                **pin,
                                **{
                                    name: digest(value)
                                    for name, value in expected.items()
                                },
                            }
                        )
                    ),
                }
            ]
            * 2,
            "reproducibility": {
                "passes": 2,
                "apk_byte_identical": True,
                "translation_files_byte_identical": True,
                "pass_1_apk_sha256": digest(raw),
                "pass_2_apk_sha256": digest(raw),
                "pass_2_zip_payloads": payload_ref,
                "pass_2_normalized_manifest": normalized,
                "different_zip_entries": [],
            },
            "reused_from_catalog_sha256": None,
        }
        data["artifacts"].append(
            {
                "id": request["id"],
                "record": store(prefix + "record.json", canonical_bytes(record)),
            }
        )
    path = tmp_path / "catalog.json"
    path.write_bytes(canonical_bytes(data))

    class SyntheticTools:
        def inspect(self, path):
            with zipfile.ZipFile(path) as z:
                return {
                    "certificate_sha256": "b" * 64,
                    "version_code": z.read("AndroidManifest.xml").decode(),
                    "normalized_manifest": b"normalized",
                }

    return (
        path,
        {
            "manifest": authority,
            "recipes": kwargs["recipes"],
            "tools": SyntheticTools(),
            "builder_sha256": builder,
        },
        data,
        store,
    )


def test_reader_matches_authoritative_plan_and_actual_translation_bytes(tmp_path):
    assert hasattr(api(), "read_catalog"), "Catalog plan binding missing"
    path, kwargs, data, _ = synthetic_catalog(tmp_path)
    result = api().read_catalog(path, digest(path.read_bytes()), **kwargs)
    assert len(result.records) == len(data["artifacts"]) == 2
    assert result.control["request"]["patches"] == []


@pytest.mark.parametrize(
    "kind",
    [
        "request",
        "translation",
        "identity",
        "signature",
        "installation",
        "extra_record",
        "false_repro",
    ],
)
def test_reader_rejects_semantic_tampering_after_rehash(tmp_path, kind):
    assert hasattr(api(), "read_catalog"), "Catalog semantic verification missing"
    from l10n_checker.screen_manifest import json_bytes

    path, kwargs, data, store = synthetic_catalog(tmp_path)
    entry = data["artifacts"][-1]
    record = json_bytes((tmp_path / entry["record"]["path"]).read_bytes())
    if kind == "request":
        record["request"]["patches"][0]["replacement"] = "unapproved"
    elif kind == "translation":
        name = api().TRANSLATIONS[0]
        record["translations"][name]["file"] = store(
            "forged.txt", b"Mining = forgery\n"
        )
    elif kind == "identity":
        record["build_identity_sha256"] = "0" * 64
    elif kind == "signature":
        record["certificate_sha256"] = "0" * 64
    elif kind == "installation":
        data["installation"] = {**data["installation"], "uninstall_allowed": True}
    elif kind == "extra_record":
        data["artifacts"].append(entry)
    else:
        record["reproducibility"]["apk_byte_identical"] = False
    entry["record"] = store(entry["record"]["path"], canonical_bytes(record))
    path.write_bytes(canonical_bytes(data))
    with pytest.raises(CaptureError):
        api().read_catalog(path, digest(path.read_bytes()), **kwargs)
