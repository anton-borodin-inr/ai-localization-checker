import json
import shutil
import socket
import sys
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from l10n_checker import slice as pipeline
from l10n_checker import slice_cli
from l10n_checker.capture import CaptureError
from l10n_checker.deepseek import DeepSeekProvider
from l10n_checker.vision import CheckResult, new_run_id

ROOT = Path(__file__).resolve().parents[1]
FINAL = ROOT / "docs/evidence/8/final"
REFERENCE = ROOT / pipeline.REFERENCE_SOURCE
APPROVAL = REFERENCE.with_name("reference-amendment-approval.json")
MANIFEST = ROOT / "docs/evidence/8/pair-manifest.json"
INVENTORY = ROOT / "docs/evidence/12/tech-picker.json"


@pytest.fixture
def prepared(monkeypatch):
    def source(image, *_):
        ref = pipeline.read(REFERENCE)
        screen = next(s for s in ref["screens"] if Path(s["image"]).name == image.name)
        build = ref["builds"][screen["build"]]
        return (
            None,
            None,
            None,
            None,
            {
                "fork_commit": build["commit"],
                "translations": {
                    code: build["translations"][name]
                    for code, name in (("en", "English"), ("de", "German"))
                },
            },
        )

    monkeypatch.setattr(pipeline, "resolve_inputs", source)
    return pipeline.prepare(
        FINAL, FINAL, REFERENCE, APPROVAL, MANIFEST, INVENTORY, ROOT
    )


def provider(outcomes, sent):
    def respond(request):
        sent.append(json.loads(request.content))
        outcome = outcomes.pop(0)
        if isinstance(outcome, int):
            return httpx.Response(outcome)
        return httpx.Response(
            200,
            json={
                "model": "deepseek-flash",
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": json.dumps(outcome)},
                    }
                ],
                "usage": {
                    "prompt_cache_hit_tokens": 0,
                    "prompt_cache_miss_tokens": 1500,
                    "completion_tokens": 100,
                },
            },
        )

    return DeepSeekProvider("fake-test-key", transport=httpx.MockTransport(respond))


def answer(readability="readable", findings=None):
    return {
        "readability": readability,
        "unreadable_regions": ["center"] if readability == "partial" else [],
        "readability_reason": None,
        "findings": findings or [],
    }


@pytest.fixture
def baseline(monkeypatch):
    def run(image, manifest, inventory, fork, runs_dir):
        directory = runs_dir / new_run_id()
        directory.mkdir(parents=True)
        meta = {
            "image": {"name": image.name, "sha256": pipeline.digest(image)},
            "run_id": directory.name,
            "requests_sent": 0,
            "latency_s": 0.5,
        }
        result = CheckResult(status="checked", reason=None, findings=[], metadata=meta)
        pipeline.write(directory / "run.json", meta)
        pipeline.write(directory / "result.json", result.model_dump())
        return result, directory

    monkeypatch.setattr(pipeline, "run_baseline", run)


def execute(tmp_path, prepared, outcomes):
    sent = []
    session = pipeline.run_slice(
        prepared,
        REFERENCE,
        APPROVAL,
        MANIFEST,
        INVENTORY,
        ROOT,
        tmp_path / "session",
        lambda: provider(outcomes, sent),
        secrets=("fake-test-key",),
    )
    return session, sent


def test_pipeline_and_portable_offline_replay(
    tmp_path, prepared, baseline, monkeypatch
):
    # The injected human label is an input, never an expected metric manufactured
    # from a detector. Production matching is tested independently by the goldens.
    label = pipeline.read(prepared[1]["label"])["labels"][0]
    finding = {k: label[k] for k in ("defect_type", "text_seen", "region")}
    finding["confidence"] = 0.9
    session, sent = execute(
        tmp_path, prepared, [answer(), answer(findings=[finding]), answer()]
    )
    original = pipeline.read(session / "comparison.json")
    assert len(sent) == 3
    assert original["totals"]["vision"]["tp"] == 1
    assert original["totals"]["vision"]["fp"] == 0
    assert original["totals"]["baseline"]["fn"] == 1
    assert original["rows"][0]["precision"] is None
    assert original["totals"]["vision"]["requests_sent"] == 3
    for path in session.rglob("*.json"):
        assert "fake-test-key" not in path.read_text()
    moved = tmp_path / "moved"
    shutil.copytree(session, moved)

    def forbidden(*args, **kwargs):
        pytest.fail("Replay attempted detector/network access")

    monkeypatch.setattr(pipeline, "run_baseline", forbidden)
    monkeypatch.setattr(pipeline, "run_check", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(slice_cli, "os", SimpleNamespace(environ={}))
    replayed = pipeline.replay(moved / "bundle.json", moved / "replayed")
    assert replayed == original
    assert (moved / "replayed.md").read_bytes() == (
        session / "comparison.md"
    ).read_bytes()


@pytest.mark.parametrize("readability", ["partial", "unreadable"])
def test_readability_diagnostics_never_enter_metrics(
    tmp_path, prepared, baseline, readability
):
    diagnostic = {
        "defect_type": "other",
        "text_seen": "invented diagnostic",
        "region": "center",
        "confidence": 0.5,
    }
    session, _ = execute(
        tmp_path, prepared, [answer(), answer(readability, [diagnostic]), answer()]
    )
    report = pipeline.read(session / "comparison.json")
    total = report["totals"]["vision"]
    assert total["not_checked_screens"] == 1
    assert total["fn_on_not_checked"] == 1
    assert total["fn"] == total["fp"] == total["hallucinations"] == 0
    assert total["recall_checked"] is None
    assert total["recall_all"] == 0
    assert any(
        "invented diagnostic" in p.read_text()
        for p in (session / "vision").rglob("response_raw.json")
    )
    assert all(r["findings"] == 0 for r in report["rows"])


def test_failed_request_counts_and_unknown_cost_stops_later_sends(
    tmp_path, prepared, baseline
):
    session, sent = execute(tmp_path, prepared, [429])
    assert len(sent) == 1  # No transport or application retry; per-run cap 1.
    report = pipeline.read(session / "comparison.json")
    assert report["totals"]["vision"]["not_checked_screens"] == 3
    assert report["totals"]["vision"]["requests_sent"] == 1
    assert report["totals"]["vision"]["estimated_peak_usd"] is None
    ledger = pipeline.read(session.parent / "budget.json")
    assert ledger["attempts"][0]["state"] == "unresolved"
    assert Decimal(ledger["attempts"][0]["charged_usd"]) == pipeline.RESERVE_USD
    assert len(report["budget_stops"]) == 2
    with pytest.raises(ValueError, match="Unresolved"):
        execute(tmp_path, prepared, [answer()] * 3)


def test_invalid_response_is_not_clean(tmp_path, prepared, baseline):
    session, _ = execute(tmp_path, prepared, [{}, answer(), answer()])
    rows = pipeline.read(session / "comparison.json")["rows"]
    assert rows[1]["status"] == "not_checked"
    assert rows[1]["reason"].startswith("invalid_response:")
    assert rows[1]["precision"] is None


@pytest.mark.parametrize(
    "file_name", ["result.json", "run.json", "response_raw.json", "prompt_sent.txt"]
)
def test_replay_rejects_changed_run_file(tmp_path, prepared, baseline, file_name):
    session, _ = execute(tmp_path, prepared, [answer()] * 3)
    path = next((session / "vision").rglob(file_name))
    path.write_text(path.read_text() + " ")
    with pytest.raises(ValueError, match="SHA-256"):
        pipeline.replay(session / "bundle.json", session / "bad")


def test_replay_rejects_swapped_screenshot_records(tmp_path, prepared, baseline):
    session, _ = execute(tmp_path, prepared, [answer()] * 3)
    bundle = pipeline.read(session / "bundle.json")
    first, second = bundle["screens"][:2]
    first["records"]["vision"], second["records"]["vision"] = (
        second["records"]["vision"],
        first["records"]["vision"],
    )
    pipeline.write(session / "bundle.json", bundle)
    with pytest.raises(ValueError, match="provenance mismatch"):
        pipeline.replay(session / "bundle.json", session / "bad")


def test_replay_checks_raw_response_not_only_result_hash(tmp_path, prepared, baseline):
    session, _ = execute(tmp_path, prepared, [answer()] * 3)
    bundle = pipeline.read(session / "bundle.json")
    entry = bundle["screens"][0]["records"]["vision"]["result.json"]
    path = session / entry["file"]
    result = pipeline.read(path)
    result["findings"] = [
        {
            "defect_type": "other",
            "text_seen": "fabricated",
            "region": "center",
            "confidence": 0.9,
        }
    ]
    pipeline.write(path, result)
    entry["sha256"] = pipeline.digest(path)
    pipeline.write(session / "bundle.json", bundle)
    with pytest.raises(ValueError, match="findings contradict"):
        pipeline.replay(session / "bundle.json", session / "bad")


def rewrite_vision_records(session, change_metadata, change_prompt=None):
    """Rewrite every vision record with consistent hashes, as a real record has."""
    bundle = pipeline.read(session / "bundle.json")
    for screen in bundle["screens"]:
        files = screen["records"]["vision"]
        paths = {name: session / entry["file"] for name, entry in files.items()}
        metadata = pipeline.read(paths["run.json"])
        change_metadata(metadata)
        if change_prompt:
            for name, field in (
                ("prompt.txt", "prompt_sha256"),
                ("prompt_sent.txt", "sent_prompt_sha256"),
            ):
                paths[name].write_text(
                    change_prompt(paths[name].read_text("utf-8")), encoding="utf-8"
                )
                metadata[field] = pipeline.digest(paths[name])
        pipeline.write(paths["run.json"], metadata)
        result = pipeline.read(paths["result.json"])
        result["metadata"] = metadata
        pipeline.write(paths["result.json"], result)
        for name, entry in files.items():
            entry["sha256"] = pipeline.digest(paths[name])
    pipeline.write(session / "bundle.json", bundle)


def without_language_line(prompt):
    lines = prompt.splitlines(keepends=True)
    assert lines[1].startswith("The screen's intended language is ")
    return "".join(lines[:1] + lines[2:])


def as_prompt_v2(metadata):
    metadata["prompt_version"] = "v2"
    del metadata["language"]
    del metadata["prompt_template_sha256"]


def test_v3_records_replay_and_name_each_screen_language(tmp_path, prepared, baseline):
    session, sent = execute(tmp_path, prepared, [answer()] * 3)
    report = pipeline.replay(session / "bundle.json", session / "again")
    assert report["totals"]["vision"]["requests_sent"] == 3
    screens = pipeline.read(session / "bundle.json")["screens"]
    for body, screen in zip(sent, screens, strict=True):
        name = "German" if "__de__" in screen["image"] else "English"
        text = body["messages"][0]["content"][1]["text"]
        assert f"The screen's intended language is {name}.\n" in text


def test_synthetic_v2_records_still_replay(tmp_path, prepared, baseline):
    # No prompt v2 record is committed: these are v3 records rewritten to the v2 shape.
    session, _ = execute(tmp_path, prepared, [answer()] * 3)
    original = pipeline.read(session / "comparison.json")
    rewrite_vision_records(session, as_prompt_v2, without_language_line)
    report = pipeline.replay(session / "bundle.json", session / "again")
    assert report["totals"]["vision"] == original["totals"]["vision"]


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda m: m.pop("language"), "contradicts the screenshot name"),
        (lambda m: m.update(language="fr"), "contradicts the screenshot name"),
        (
            lambda m: m.update(language={"en": "de", "de": "en"}[m["language"]]),
            "contradicts the screenshot name",
        ),
        (lambda m: m.update(prompt_version="v2"), "Only prompt v3"),
        (lambda m: m.update(schema_version="v1"), "Unsupported vision record"),
        (lambda m: m.update(prompt_version="v4"), "Unsupported vision record"),
        (lambda m: m.update(prompt_version=["v3"]), "Unsupported vision record"),
    ],
    ids=[
        "v3-no-language",
        "v3-invalid-language",
        "v3-other-language",
        "v2-with-language",
        "v1-prompt-v3",
        "unknown-prompt",
        "unhashable-prompt",
    ],
)
def test_replay_rejects_inconsistent_language_records(
    tmp_path, prepared, baseline, change, message
):
    session, _ = execute(tmp_path, prepared, [answer()] * 3)
    rewrite_vision_records(session, change)
    with pytest.raises(ValueError, match=message):
        pipeline.replay(session / "bundle.json", session / "bad")


def test_replay_rejects_v3_prompt_without_the_language_line(
    tmp_path, prepared, baseline
):
    session, _ = execute(tmp_path, prepared, [answer()] * 3)
    rewrite_vision_records(session, lambda _: None, without_language_line)
    with pytest.raises(ValueError, match="does not name the language"):
        pipeline.replay(session / "bundle.json", session / "bad")


def test_preflight_rejects_file_name_without_language(tmp_path, prepared):
    shutil.copytree(FINAL, tmp_path / "images")
    (tmp_path / "images" / "a__fr__2400x1080__clean__1271001.png").write_bytes(b"png")
    with pytest.raises(CaptureError, match="no valid language"):
        pipeline.prepare(
            tmp_path / "images",
            tmp_path / "images",
            REFERENCE,
            APPROVAL,
            MANIFEST,
            INVENTORY,
            ROOT,
        )


def test_replay_cannot_overwrite_bundle(tmp_path, prepared, baseline):
    session, _ = execute(tmp_path, prepared, [answer()] * 3)
    before = (session / "bundle.json").read_bytes()
    with pytest.raises(ValueError, match="overwrite"):
        pipeline.replay(session / "bundle.json", session / "bundle")
    assert (session / "bundle.json").read_bytes() == before


@pytest.mark.parametrize("kind", ["reference", "label", "image"])
def test_preflight_rejects_modified_inputs(tmp_path, prepared, kind):
    shutil.copytree(FINAL, tmp_path / "images")
    reference = tmp_path / "reference.json"
    shutil.copyfile(REFERENCE, reference)
    if kind == "reference":
        reference.write_text(reference.read_text() + "\n")
    else:
        suffix = "*.png" if kind == "image" else "*.labels.json"
        path = next((tmp_path / "images").glob(suffix))
        path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="hash|confirmation"):
        pipeline.prepare(
            tmp_path / "images",
            tmp_path / "images",
            reference,
            APPROVAL,
            MANIFEST,
            INVENTORY,
            ROOT,
        )


def test_reference_preserves_diagnostics_and_never_invents_occurrences():
    ref = pipeline.read(REFERENCE)["screens"][0]
    texts, provenance = pipeline.reference_texts(ref)
    assert texts == [r["text_seen"] for r in ref["rows"]] + ref["numeric_diagnostics"]
    production = next(r for r in ref["rows"] if r["id"] == "production")
    assert production["assembled_full_text"] not in texts
    assert "Schrift" in texts  # Excluded from #10 reading denominator, still visible.
    assert len(provenance) == len(texts)
    ref["rows"].append(ref["rows"][0])
    assert pipeline.reference_texts(ref)[0].count(ref["rows"][0]["text_seen"]) == 2


def test_preflight_rejects_replacement_reference_even_with_matching_approval(
    tmp_path, prepared
):
    reference = tmp_path / "reference.json"
    reference.write_text(REFERENCE.read_text() + "\n")
    approval = pipeline.read(APPROVAL)
    approval["reference_sha256"] = pipeline.digest(reference)
    pipeline.write(tmp_path / "approval.json", approval)
    with pytest.raises(ValueError, match="confirmation"):
        pipeline.prepare(
            FINAL,
            FINAL,
            reference,
            tmp_path / "approval.json",
            MANIFEST,
            INVENTORY,
            ROOT,
        )


@pytest.mark.parametrize("cause", ["requests", "cost", "pending"])
def test_persistent_budget_refuses_send(tmp_path, cause):
    path = tmp_path / "budget.json"
    attempts = [{"state": "accounted", "charged_usd": "0.001"}] * 10
    if cause == "cost":
        attempts = [{"state": "accounted", "charged_usd": "0.095"}]
    elif cause == "pending":
        attempts = [{"state": "reserved", "charged_usd": "0.01"}]
    pipeline.write(path, {"attempts": attempts})
    with pytest.raises(ValueError):
        pipeline.Ledger(path).reserve("image.png")


def test_cli_requires_cap_one(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["l10n-slice", "run", "--max-requests", "2"])
    with pytest.raises(SystemExit):
        slice_cli.main()


def test_cli_replay_does_not_read_key(tmp_path, prepared, baseline, monkeypatch):
    session, _ = execute(tmp_path, prepared, [answer()] * 3)

    class NoEnvironment:
        def get(self, *_):
            pytest.fail("Replay read environment")

    monkeypatch.setattr(slice_cli, "os", SimpleNamespace(environ=NoEnvironment()))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "l10n-slice",
            "replay",
            "--bundle",
            str(session / "bundle.json"),
            "--output",
            str(tmp_path / "out"),
        ],
    )
    assert slice_cli.main() == 0


def test_committed_issue_14_v1_bundle_replays_for_detection_only(tmp_path):
    records = ROOT / "docs/evidence/14/records"
    committed = pipeline.read(records / "comparison.json")
    replayed = pipeline.replay(records / "bundle.json", tmp_path / "comparison")
    detection = (
        "tp",
        "fp",
        "fn",
        "precision",
        "recall_checked",
        "recall_all",
        "hallucinations",
        "duplicates_collapsed",
        "not_checked_screens",
        "fn_on_not_checked",
    )
    pairs = list(zip(committed["rows"], replayed["rows"], strict=True))
    pairs += [
        (committed["totals"][name], replayed["totals"][name])
        for name in committed["totals"]
    ]
    for old, new in pairs:
        assert {k: new[k] for k in detection} == {k: old[k] for k in detection}
        assert new["confusion"] is None
        assert "labels v1" in new["confusion_unavailable_reason"]
        assert "results v1" in new["confusion_unavailable_reason"]
