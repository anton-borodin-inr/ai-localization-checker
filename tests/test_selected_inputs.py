"""Selection precedes payload reads; effective builds never edit authority."""

from pathlib import Path

import pytest

from l10n_checker.capture import CaptureError
from l10n_checker.screen_manifest import Inputs, digest, json_bytes
from l10n_checker.screen_split import load_split
from l10n_checker.text_dump import canonical_bytes

MANIFEST = Path(__file__).resolve().parents[1] / "fixtures/stage2/screens-v2.json"


def test_selected_inputs_read_only_dev_payloads(monkeypatch):
    model = json_bytes(MANIFEST.read_bytes())
    partition = load_split(
        MANIFEST.with_name("split.json"), [s["id"] for s in model["screens"]]
    )
    forbidden = {
        MANIFEST.parent / ref["path"]
        for screen in model["screens"]
        if screen["id"] not in partition.dev
        for ref in [*screen["language_states"].values(), {"path": screen["state"]}]
    }
    forbidden |= {
        MANIFEST.parent / item["path"]
        for item in model["fixtures"]
        if item["name"] != "issue-8-pair"
    }
    original = Path.read_bytes
    reads = []

    def read(path):
        assert path not in forbidden, "unselected payload read"
        reads.append(path)
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", read)
    inputs = Inputs(MANIFEST, split="dev")
    assert {s.id for s in inputs.screens()} == set(partition.dev)
    assert len(inputs.states) == 10
    assert set(inputs.fixtures) == {"issue-8-pair"}
    assert inputs.source_manifest_sha256 == inputs.sha256
    assert not forbidden.intersection(reads)


def test_invalid_selection_fails_before_any_payload(monkeypatch):
    original = Path.read_bytes

    def read(path):
        assert path.name in {"screens-v2.json", "split.json"}
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", read)
    with pytest.raises(CaptureError, match="Screen IDs"):
        Inputs(MANIFEST, screen_ids=["not-a-screen"])


def test_effective_build_preserves_authority_and_root():
    original = MANIFEST.read_bytes()
    inputs = Inputs(MANIFEST, split="dev")
    build = {
        **inputs.manifest.build.model_dump(),
        "version_code": "1888080431",
        "apk_sha256": "f" * 64,
    }
    effective = inputs.with_build(build)
    expected = json_bytes(original)
    expected["build"] = build
    assert effective.manifest_bytes == canonical_bytes(expected)
    assert effective.sha256 == digest(effective.manifest_bytes)
    assert effective.source_manifest_sha256 == digest(original)
    assert effective.root == inputs.root
    assert effective.capture_selection(["en", "de"]) == inputs.capture_selection(
        ["en", "de"]
    )
    assert effective.fixtures == inputs.fixtures
    assert inputs.manifest.build.version_code == "1271048"
    assert MANIFEST.read_bytes() == original


def test_effective_build_rejects_source_change():
    inputs = Inputs(MANIFEST, split="dev")
    build = {**inputs.manifest.build.model_dump(), "fork_commit": "0" * 40}
    with pytest.raises(CaptureError, match="source"):
        inputs.with_build(build)
