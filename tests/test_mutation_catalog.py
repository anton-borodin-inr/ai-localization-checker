"""Catalog boundaries use real bytes, never fabricated signing evidence."""

import importlib
import importlib.util
import io
import zipfile

import pytest

from l10n_checker.capture import CaptureError


def api():
    assert importlib.util.find_spec("l10n_checker.mutation_catalog") is not None, (
        "Catalog reader missing"
    )
    return importlib.import_module("l10n_checker.mutation_catalog")


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
