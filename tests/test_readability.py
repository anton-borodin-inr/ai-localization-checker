"""Issue #35 contracts, exercised through the real adapter with no network."""

import json

import httpx
import pytest
from pydantic import ValidationError

from l10n_checker.deepseek import WRAPPER_VERSION, DeepSeekProvider
from l10n_checker.vision import (
    PROMPT,
    PROMPT_VERSION,
    SCHEMA_VERSION,
    Finding,
    ModelOutput,
    RequestBudget,
    run_check,
)

FINDING = {
    "defect_type": "truncated_text",
    "text_seen": "Start new ga...",
    "region": "center",
    "confidence": 0.8,
}


def output(readability="readable", regions=None, reason=None, findings=None):
    return {
        "readability": readability,
        "unreadable_regions": [] if regions is None else regions,
        "readability_reason": reason,
        "findings": [] if findings is None else findings,
    }


def check(payload, screenshot, tmp_path):
    raw = {
        "model": "deepseek-flash",
        "choices": [
            {
                "message": {"content": json.dumps(payload)},
                "finish_reason": "stop",
            }
        ],
    }
    provider = DeepSeekProvider(
        "offline-test-key",
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=raw)),
    )
    return run_check(provider, screenshot, tmp_path / "runs", RequestBudget(1))


@pytest.mark.parametrize("findings", [[], [FINDING]], ids=["clean", "finding"])
def test_readable_is_checked(screenshot, tmp_path, findings):
    result, run_dir = check(output(findings=findings), screenshot, tmp_path)
    assert result.status == "checked"
    assert result.reason is None
    assert result.findings == [Finding(**finding) for finding in findings]
    run = json.loads((run_dir / "run.json").read_text())
    assert run["readability"] == "readable"
    assert run["unreadable_regions"] == []
    assert run["readability_reason"] is None


@pytest.mark.parametrize(
    ("readability", "regions", "reason"),
    [
        ("partial", ["top"], "Small visible text cannot be read"),
        ("unreadable", [], "Text cannot be read"),
        ("unreadable", ["left"], None),
    ],
    ids=["partial", "unreadable-no-regions", "unreadable-with-region"],
)
def test_unreadable_text_is_not_checked(
    screenshot, tmp_path, readability, regions, reason
):
    payload = output(readability, regions, reason)
    result, run_dir = check(payload, screenshot, tmp_path)
    reason_text = "null" if reason is None else reason
    assert result.reason == (
        f"unreadable_text: {readability}, {json.dumps(regions)}, {reason_text}"
    )
    assert result.status == "not_checked"
    assert result.findings == []
    run = json.loads((run_dir / "run.json").read_text())
    assert run["readability"] == readability
    assert run["unreadable_regions"] == regions
    assert run["readability_reason"] == reason


@pytest.mark.parametrize("readability", ["partial", "unreadable"])
def test_partial_observations_are_diagnostics_only(screenshot, tmp_path, readability):
    payload = output(readability, ["top"], "Some text cannot be read", [FINDING])
    result, run_dir = check(payload, screenshot, tmp_path)
    # A v0 rejection for extra fields must not masquerade as this new contract.
    assert result.reason.startswith(f"unreadable_text: {readability},")
    assert result.status == "not_checked"
    assert result.findings == []
    saved = json.loads((run_dir / "result.json").read_text())
    assert saved["status"] == "not_checked"
    assert saved["findings"] == []
    raw = json.loads((run_dir / "response_raw.json").read_text())
    assert json.loads(raw["choices"][0]["message"]["content"]) == payload


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (output("readable", ["top"]), "readable requires empty unreadable_regions"),
        (output("partial"), "partial requires at least one unreadable region"),
    ],
    ids=["readable-with-regions", "partial-without-regions"],
)
def test_readability_consistency_is_validated(screenshot, tmp_path, payload, message):
    with pytest.raises(ValidationError) as exc:
        ModelOutput.model_validate_json(json.dumps(payload))
    assert any(
        error["msg"] == f"Value error, {message}" for error in exc.value.errors()
    )
    result, _ = check(payload, screenshot, tmp_path)
    assert result.reason == f"invalid_response: response: Value error, {message}"
    assert result.status == "not_checked"
    assert result.findings == []


@pytest.mark.parametrize(
    "field", ["readability", "unreadable_regions", "readability_reason"]
)
def test_readability_fields_are_required(screenshot, tmp_path, field):
    payload = output()
    del payload[field]
    with pytest.raises(ValidationError) as exc:
        ModelOutput.model_validate_json(json.dumps(payload))
    assert any(
        error["loc"] == (field,) and error["type"] == "missing"
        for error in exc.value.errors()
    )
    result, _ = check(payload, screenshot, tmp_path)
    assert result.reason == f"invalid_response: {field}: Field required"
    assert result.status == "not_checked"
    assert result.findings == []


@pytest.mark.parametrize(
    ("field", "value", "location", "error_type"),
    [
        ("readability", "unknown", ("readability",), "literal_error"),
        ("readability", None, ("readability",), "literal_error"),
        ("unreadable_regions", None, ("unreadable_regions",), "list_type"),
        (
            "unreadable_regions",
            ["middle"],
            ("unreadable_regions", 0),
            "literal_error",
        ),
        ("readability_reason", 123, ("readability_reason",), "string_type"),
    ],
    ids=[
        "unknown-readability",
        "null-readability",
        "null-regions",
        "bad-cell",
        "numeric-reason",
    ],
)
def test_readability_values_are_strict(
    screenshot, tmp_path, field, value, location, error_type
):
    payload = {**output(), field: value}
    with pytest.raises(ValidationError) as exc:
        ModelOutput.model_validate_json(json.dumps(payload))
    assert any(
        error["loc"] == location and error["type"] == error_type
        for error in exc.value.errors()
    )
    result, _ = check(payload, screenshot, tmp_path)
    assert result.status == "not_checked"
    assert result.reason.startswith("invalid_response:")
    assert result.findings == []


@pytest.mark.parametrize(
    "rule",
    [
        "when the full content becomes visible by scrolling",
        "when the full text is not visible anywhere else on the same screenshot",
        "a raw string key or identifier that is not text in any language is other",
        "a broken placeholder (shown literally or wrongly substituted) is other",
        "shown because its translation is missing is wrong_language",
        "outside the bounds of its own label or field",
        "including source-language fallback and foreign text in an active translation file",
        "where each text stays inside its own bounds, is other, not overflow",
        "Text too small to read is reported through readability, not as a finding",
        "contains the centre of the text's bounding box",
        "Scroll clipping alone does not make the visible text partial or unreadable",
    ],
    ids=[
        "scroll",
        "ellipsis",
        "raw-key",
        "placeholder",
        "missing-translation",
        "overflow-own-bounds",
        "wrong-language-scope",
        "widget-collision",
        "small-text",
        "region-centre",
        "visible-readability",
    ],
)
def test_prompt_carries_labeling_and_readability_rules(rule):
    assert rule in PROMPT


@pytest.mark.parametrize(
    ("actual", "expected"),
    [
        (PROMPT_VERSION, "v2"),
        (SCHEMA_VERSION, "v2"),
        (WRAPPER_VERSION, "deepseek-json-object-v3"),
    ],
    ids=["prompt", "schema", "wrapper"],
)
def test_v2_versions_are_recordable(actual, expected):
    assert actual == expected
