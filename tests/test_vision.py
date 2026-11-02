import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from l10n_checker.capture import CaptureError
from l10n_checker.vision import (
    LANGUAGE_LINE,
    PROMPT_TEMPLATE,
    PROMPT_VERSION,
    SCHEMA_VERSION,
    CheckResult,
    CheckResultV1,
    Finding,
    FindingV1,
    ModelOutput,
    ProviderError,
    ProviderResponse,
    RequestBudget,
    build_prompt,
    load_check_result,
    result_schema_version,
    run_check,
    screenshot_language,
)

FINDING = {
    "defect_type": "truncated_text",
    "text_seen": "Start new ga...",
    "region": "center",
    "confidence": 0.8,
}


def model_output(findings=None, **extra):
    return json.dumps(
        {
            "readability": "readable",
            "unreadable_regions": [],
            "readability_reason": None,
            "findings": [] if findings is None else findings,
            **extra,
        }
    )


class FakeProvider:
    name = "fake"
    model = "fake-model"
    sdk_version = "0"
    wrapper_version = None

    def __init__(self, *outcomes):
        self.settings = {"temperature": 0}
        self.outcomes = list(outcomes)
        self.calls = 0
        self.prompts = []

    def wrap_prompt(self, prompt):
        return prompt

    def estimate_cost(self, usage):
        return None

    def generate(self, image, mime_type, prompt):
        self.calls += 1
        self.prompts.append(prompt)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return ProviderResponse(
            text=outcome,
            raw={"text": outcome},
            model_version="fake-model-001",
            usage={"total_token_count": 10},
        )


def check(provider, screenshot, tmp_path, max_requests=1):
    return run_check(
        provider,
        screenshot,
        tmp_path / "runs",
        RequestBudget(max_requests),
        retry_delay_s=0,
    )


def test_findings_are_validated(screenshot, tmp_path):
    result, _ = check(FakeProvider(model_output([FINDING])), screenshot, tmp_path)
    assert result.status == "checked"
    assert result.findings == [Finding(**FINDING)]
    assert result.reason is None


def test_explicit_empty_list_is_the_only_no_defects(screenshot, tmp_path):
    result, _ = check(FakeProvider(model_output()), screenshot, tmp_path)
    assert result.status == "checked"
    assert result.findings == []


@pytest.mark.parametrize(
    ("outcomes", "max_requests", "reason"),
    [
        ([ProviderError("timeout", "read timed out")], 1, "timeout"),
        ([ProviderError("api_error", "500 INTERNAL")], 1, "api_error"),
        ([ProviderError("rate_limited", "429")] * 2, 2, "rate_limited"),
        ([ProviderError("empty_response", "no candidates")], 1, "empty_response"),
        (
            [ProviderError("incomplete_response", "MAX_TOKENS")],
            1,
            "incomplete_response",
        ),
        (["   "], 1, "empty_response"),
        (['{"findings": [ '], 1, "invalid_response"),
        (["not json"], 1, "invalid_response"),
        (['{"items": []}'], 1, "invalid_response"),
        (
            [model_output([{**FINDING, "region": "middle"}])],
            1,
            "invalid_response",
        ),
        (
            [model_output([{**FINDING, "confidence": 1.5}])],
            1,
            "invalid_response",
        ),
        (
            [model_output([{**FINDING, "defect_type": "typo"}])],
            1,
            "invalid_response",
        ),
    ],
)
def test_failures_are_not_checked(screenshot, tmp_path, outcomes, max_requests, reason):
    result, run_dir = check(FakeProvider(*outcomes), screenshot, tmp_path, max_requests)
    assert result.status == "not_checked"
    assert result.findings == []
    assert result.reason.startswith(reason)
    saved = json.loads((run_dir / "result.json").read_text())
    assert saved["status"] == "not_checked"
    assert saved["findings"] == []


def test_single_retry_on_rate_limit(screenshot, tmp_path):
    provider = FakeProvider(ProviderError("rate_limited", "429"), model_output())
    result, _ = check(provider, screenshot, tmp_path, max_requests=2)
    assert result.status == "checked"
    assert provider.calls == 2
    assert [a["outcome"] for a in result.metadata["attempts"]] == ["rate_limited", "ok"]


def test_no_retry_beyond_one(screenshot, tmp_path):
    provider = FakeProvider(*[ProviderError("rate_limited", "429")] * 3)
    result, _ = check(provider, screenshot, tmp_path, max_requests=5)
    assert result.status == "not_checked"
    assert provider.calls == 2


def test_cap_refuses_the_retry(screenshot, tmp_path):
    provider = FakeProvider(ProviderError("rate_limited", "429"), model_output())
    result, _ = check(provider, screenshot, tmp_path, max_requests=1)
    assert result.status == "not_checked"
    assert provider.calls == 1
    assert result.metadata["requests_sent"] == 1


def test_cap_refuses_any_request(screenshot, tmp_path):
    provider = FakeProvider(model_output())
    result, _ = check(provider, screenshot, tmp_path, max_requests=0)
    assert result.status == "not_checked"
    assert result.reason.startswith("request_cap_reached")
    assert provider.calls == 0


def test_budget_take_refuses_beyond_cap():
    budget = RequestBudget(2)
    budget.take()
    budget.take()
    with pytest.raises(Exception, match="request cap of 2 reached"):
        budget.take()
    assert budget.used == 2


@pytest.mark.parametrize(
    ("status", "findings", "reason"),
    [
        ("not_checked", [Finding(**FINDING)], "timeout"),
        ("not_checked", [], None),
        ("checked", [], "timeout"),
    ],
)
def test_result_invariant(status, findings, reason):
    with pytest.raises(ValidationError):
        CheckResult(status=status, findings=findings, reason=reason, metadata={})


def test_run_record(screenshot, tmp_path):
    _, run_dir = check(FakeProvider(model_output()), screenshot, tmp_path)
    assert run_dir.parent == tmp_path / "runs"
    assert sorted(p.name for p in run_dir.iterdir()) == [
        "prompt.txt",
        "prompt_sent.txt",
        "response_raw.json",
        "result.json",
        "run.json",
    ]
    prompt = build_prompt("en")
    assert (run_dir / "prompt.txt").read_text() == prompt
    assert (run_dir / "prompt_sent.txt").read_text() == prompt
    run = json.loads((run_dir / "run.json").read_text())
    assert run["prompt_version"] == PROMPT_VERSION
    assert run["prompt_sha256"] == hashlib.sha256(prompt.encode()).hexdigest()
    assert run["sent_prompt_sha256"] == run["prompt_sha256"]
    assert run["wrapper_version"] is None
    assert run["image"]["bytes"] == screenshot.stat().st_size
    assert run["model"] == "fake-model"
    assert run["model_version"] == "fake-model-001"
    assert run["schema_version"] == SCHEMA_VERSION
    assert run["settings"] == {"temperature": 0}
    assert run["usage"] == {"total_token_count": 10}
    assert run["image"]["width"] == 4 and run["image"]["height"] == 2
    assert run["attempts"][0]["outcome"] == "ok"
    assert "latency_s" in run["attempts"][0]


def test_run_record_without_response(screenshot, tmp_path):
    _, run_dir = check(
        FakeProvider(ProviderError("timeout", "t")), screenshot, tmp_path
    )
    assert not (run_dir / "response_raw.json").exists()
    assert (run_dir / "run.json").exists() and (run_dir / "result.json").exists()


V1_RECORD = (
    Path(__file__).resolve().parents[1]
    / "docs/evidence/45/run-records/20261021T191152Z-72ce18/result.json"
)


def test_committed_v1_record_still_loads_with_v1_classes():
    text = V1_RECORD.read_text(encoding="utf-8")
    result = load_check_result(text)
    assert type(result) is CheckResultV1
    assert result.status == "checked"
    assert {type(f) for f in result.findings} == {FindingV1}
    assert {f.defect_type for f in result.findings} == {"overlap"}
    with pytest.raises(ValidationError):
        CheckResult.model_validate_json(text)


@pytest.mark.parametrize("name", ["overlap", "untranslated"])
def test_v2_model_output_rejects_v1_class_names(name):
    payload = {
        "readability": "readable",
        "unreadable_regions": [],
        "readability_reason": None,
        "findings": [{**FINDING, "defect_type": name}],
    }
    with pytest.raises(ValidationError):
        ModelOutput.model_validate_json(json.dumps(payload))


def test_sent_schema_lists_only_v2_classes():
    schema = json.dumps(ModelOutput.model_json_schema())
    for name in ("overflow", "wrong_language", "truncated_text", "other"):
        assert f'"{name}"' in schema
    for name in ("overlap", "untranslated"):
        assert f'"{name}"' not in schema


@pytest.mark.parametrize(
    ("metadata", "expected"),
    [
        ({"schema_version": "v1"}, 1),
        ({"schema_version": "v2"}, 2),
        ({"schema_version": 2}, 2),
        ({}, 1),
    ],
    ids=["vision-v1", "vision-v2", "baseline-v2", "baseline-before-d046"],
)
def test_result_schema_version(metadata, expected):
    assert result_schema_version(metadata) == expected


@pytest.mark.parametrize(
    "version", ["v3", 3, True, None, 2.0, 1.0, "2", [], {}, ["v2"]]
)
def test_unknown_result_schema_version_is_rejected(version):
    with pytest.raises(ValueError):
        result_schema_version({"schema_version": version})


# sha256 of the prompt v2 text at cf26da5, the commit before prompt v3.
PROMPT_V2_SHA256 = "0220d7afee936d30e037dfdead65adf5430bbf38a3fae8a9ade3f9ce2b1fb795"


@pytest.mark.parametrize(
    ("code", "name"), [("en", "English"), ("de", "German")], ids=["en", "de"]
)
def test_prompt_without_the_language_line_is_prompt_v2(code, name):
    line = f"The screen's intended language is {name}.\n"
    prompt = build_prompt(code)
    assert prompt.count(line) == 1
    assert prompt.splitlines(keepends=True)[1] == line
    assert hashlib.sha256(prompt.replace(line, "").encode()).hexdigest() == (
        PROMPT_V2_SHA256
    )


def test_template_has_only_the_language_field():
    assert LANGUAGE_LINE == "The screen's intended language is {language}.\n"
    assert PROMPT_TEMPLATE.count("{") == PROMPT_TEMPLATE.count("}") == 1


@pytest.mark.parametrize(
    ("code", "name"), [("en", "English"), ("de", "German")], ids=["en", "de"]
)
def test_file_name_language_is_sent_and_recorded(screenshot, tmp_path, code, name):
    image = tmp_path / f"main-menu__{code}__4x2__original__1.png"
    image.write_bytes(screenshot.read_bytes())
    provider = FakeProvider(model_output())
    _, run_dir = check(provider, image, tmp_path)
    assert provider.prompts == [build_prompt(code)]
    assert f"The screen's intended language is {name}.\n" in provider.prompts[0]
    run = json.loads((run_dir / "run.json").read_text())
    assert run["language"] == code
    assert run["prompt_sha256"] == (
        hashlib.sha256(provider.prompts[0].encode()).hexdigest()
    )
    assert run["prompt_template_sha256"] == (
        hashlib.sha256(PROMPT_TEMPLATE.encode()).hexdigest()
    )
    result = json.loads((run_dir / "result.json").read_text())
    assert result["metadata"]["language"] == code


def test_only_the_rendered_hash_differs_between_languages(screenshot, tmp_path):
    runs = []
    for code in ("en", "de"):
        image = tmp_path / f"main-menu__{code}__4x2__original__1.png"
        image.write_bytes(screenshot.read_bytes())
        _, run_dir = check(FakeProvider(model_output()), image, tmp_path)
        runs.append(json.loads((run_dir / "run.json").read_text()))
    assert runs[0]["prompt_template_sha256"] == runs[1]["prompt_template_sha256"]
    assert runs[0]["prompt_sha256"] != runs[1]["prompt_sha256"]


BAD_NAMES = [
    "x.png",
    "main-menu__en.png",
    "main-menu__en__4x2__original.png",
    "main-menu__en__4x2__original__1__extra.png",
    "main-menu____4x2__original__1.png",
    "main-menu__fr__4x2__original__1.png",
    "main-menu__DE__4x2__original__1.png",
    "main-menu__de__4x2__original__1.PNG",
    "main-menu__de__4x2__original__1.jpg",
]


@pytest.mark.parametrize("name", BAD_NAMES)
def test_screenshot_language_rejects_invalid_names(name):
    with pytest.raises(CaptureError):
        screenshot_language(Path(name))


@pytest.mark.parametrize("name", BAD_NAMES)
def test_invalid_language_fails_before_any_request(screenshot, tmp_path, name):
    image = tmp_path / name
    image.write_bytes(screenshot.read_bytes())
    provider = FakeProvider(model_output())
    with pytest.raises(CaptureError):
        check(provider, image, tmp_path)
    assert provider.calls == 0
    assert not (tmp_path / "runs").exists()
