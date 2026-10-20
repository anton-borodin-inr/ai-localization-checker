import hashlib
import json

import pytest
from pydantic import ValidationError

from l10n_checker.vision import (
    PROMPT,
    PROMPT_VERSION,
    SCHEMA_VERSION,
    CheckResult,
    Finding,
    ProviderError,
    ProviderResponse,
    RequestBudget,
    run_check,
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

    def wrap_prompt(self, prompt):
        return prompt

    def estimate_cost(self, usage):
        return None

    def generate(self, image, mime_type, prompt):
        self.calls += 1
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
    assert (run_dir / "prompt.txt").read_text() == PROMPT
    assert (run_dir / "prompt_sent.txt").read_text() == PROMPT
    run = json.loads((run_dir / "run.json").read_text())
    assert run["prompt_version"] == PROMPT_VERSION
    assert run["prompt_sha256"] == hashlib.sha256(PROMPT.encode()).hexdigest()
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
