import base64
import json
from decimal import Decimal

import httpx
import pytest

from l10n_checker.deepseek import (
    MAX_TOKENS,
    MODEL,
    WRAPPER_VERSION,
    DeepSeekProvider,
    estimate_cost,
    schema_text,
)
from l10n_checker.vision import PROMPT, ModelOutput, RequestBudget, run_check

KEY = "test-key-DO-NOT-LEAK"
FINDING = {
    "defect_type": "truncated_text",
    "text_seen": "Bergbau und Erzgew...",
    "region": "left",
    "confidence": 0.9,
}
USAGE = {
    "prompt_tokens": 1500,
    "completion_tokens": 100,
    "total_tokens": 1600,
    "prompt_cache_hit_tokens": 500,
    "prompt_cache_miss_tokens": 1000,
}


def completion(content, finish_reason="stop", **extra):
    return {
        "id": "x",
        "object": "chat.completion",
        "model": MODEL,
        "system_fingerprint": "fp-1",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": finish_reason,
            }
        ],
        "usage": USAGE,
        **extra,
    }


class FakeServer:
    """Answers every request with the next outcome; records what was sent."""

    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        if isinstance(outcome, httpx.Response):
            return outcome
        return httpx.Response(200, json=outcome)


def check(server, screenshot, tmp_path, max_requests=1):
    provider = DeepSeekProvider(KEY, transport=httpx.MockTransport(server))
    result, run_dir = run_check(
        provider,
        screenshot,
        tmp_path / "runs",
        RequestBudget(max_requests),
        secrets=(KEY,),
        retry_delay_s=0,
    )
    return result, run_dir


def test_success(screenshot, tmp_path):
    server = FakeServer(completion(json.dumps({"findings": [FINDING]})))
    result, run_dir = check(server, screenshot, tmp_path)
    assert result.status == "checked"
    assert [f.model_dump() for f in result.findings] == [FINDING]
    run = json.loads((run_dir / "run.json").read_text())
    assert run["provider"] == "deepseek"
    assert run["model"] == MODEL
    assert run["model_version"] == MODEL
    assert run["system_fingerprint"] == "fp-1"
    assert run["wrapper_version"] == WRAPPER_VERSION
    assert run["usage"] == USAGE
    assert run["requests_sent"] == 1
    assert run["attempts"][0]["outcome"] == "ok"
    assert run["image"]["bytes"] == screenshot.stat().st_size


def test_request_payload_and_settings(screenshot, tmp_path):
    server = FakeServer(completion('{"findings": []}'))
    _, run_dir = check(server, screenshot, tmp_path)
    (request,) = server.requests
    assert request.method == "POST"
    assert str(request.url) == "https://api.deepseek.com/chat/completions"
    assert request.headers["authorization"] == f"Bearer {KEY}"
    body = json.loads(request.content)
    assert body["model"] == MODEL
    assert body["temperature"] == 0
    assert body["max_tokens"] == MAX_TOKENS
    assert body["stream"] is False
    assert body["thinking"] == {"type": "disabled"}
    assert body["response_format"] == {"type": "json_object"}
    image_part, text_part = body["messages"][0]["content"]
    assert image_part["image_url"]["detail"] == "original"
    url = image_part["image_url"]["url"]
    assert url.startswith("data:image/png;base64,")
    assert base64.b64decode(url.split(",", 1)[1]) == screenshot.read_bytes()
    # The detector prompt is sent unchanged, followed by the format wrapper.
    assert text_part["text"].startswith(PROMPT)
    assert text_part["text"].endswith(schema_text())
    assert (run_dir / "prompt.txt").read_text() == PROMPT
    assert (run_dir / "prompt_sent.txt").read_text() == text_part["text"]
    settings = json.loads((run_dir / "run.json").read_text())["settings"]
    assert settings["image_detail"] == "original"
    assert settings["transport_retries"] == 0
    assert settings["timeout_s"] == 120


def test_wrapper_schema_is_the_model_output_schema():
    assert json.loads(schema_text()) == ModelOutput.model_json_schema()


@pytest.mark.parametrize(
    ("outcome", "reason"),
    [
        (completion("not json"), "invalid_response"),
        (completion('```json\n{"findings": []}\n```'), "invalid_response"),
        (
            completion(json.dumps({"findings": [{**FINDING, "note": "x"}]})),
            "invalid_response",
        ),
        (completion(json.dumps({"findings": [], "extra": 1})), "invalid_response"),
        (
            completion(json.dumps({"findings": [{"text_seen": "x"}]})),
            "invalid_response",
        ),
        (completion("{}"), "invalid_response"),
        (completion(""), "empty_response"),
        (completion(None), "empty_response"),
        ({**completion("{}"), "choices": []}, "empty_response"),
        (completion('{"findings": [', finish_reason="length"), "incomplete_response"),
        (completion('{"findings": []}', finish_reason=None), "incomplete_response"),
        (httpx.ReadTimeout("read timed out"), "timeout"),
        (httpx.ConnectError("connection refused"), "api_error"),
        (httpx.Response(500, text="internal"), "api_error"),
        (httpx.Response(402, text="Insufficient Balance"), "api_error"),
        (httpx.Response(429, text="slow down"), "rate_limited"),
        (httpx.Response(200, text="<html>"), "api_error"),
        (httpx.Response(200, json=[1]), "api_error"),
    ],
)
def test_failures_are_not_checked(screenshot, tmp_path, outcome, reason):
    result, run_dir = check(FakeServer(outcome), screenshot, tmp_path)
    assert result.status == "not_checked"
    assert result.findings == []
    assert result.reason.startswith(reason)
    assert json.loads((run_dir / "run.json").read_text())["requests_sent"] == 1


def test_invalid_output_is_kept_raw_not_repaired(screenshot, tmp_path):
    content = json.dumps({"findings": [{**FINDING, "note": "x"}]})
    _, run_dir = check(FakeServer(completion(content)), screenshot, tmp_path)
    raw = json.loads((run_dir / "response_raw.json").read_text())
    assert raw["choices"][0]["message"]["content"] == content


def test_http_error_body_is_recorded(screenshot, tmp_path):
    server = FakeServer(httpx.Response(500, text="internal"))
    _, run_dir = check(server, screenshot, tmp_path)
    raw = json.loads((run_dir / "response_raw.json").read_text())
    assert raw == {"http_status": 500, "body": "internal"}


def test_cap_reached_sends_nothing(screenshot, tmp_path):
    server = FakeServer()
    result, run_dir = check(server, screenshot, tmp_path, max_requests=0)
    assert result.status == "not_checked"
    assert result.reason.startswith("request_cap_reached")
    assert server.requests == []
    assert json.loads((run_dir / "run.json").read_text())["requests_sent"] == 0


def test_rate_limit_is_not_retried_with_cap_one(screenshot, tmp_path):
    server = FakeServer(httpx.Response(429), completion('{"findings": []}'))
    result, _ = check(server, screenshot, tmp_path)
    assert result.reason.startswith("rate_limited")
    assert len(server.requests) == 1


def test_key_is_never_written(screenshot, tmp_path):
    echo = httpx.Response(401, text=f"bad key {KEY}")
    _, run_dir = check(FakeServer(echo), screenshot, tmp_path)
    for path in run_dir.iterdir():
        assert KEY not in path.read_text()


def test_cost_estimate():
    cost = estimate_cost(USAGE)
    # 500 * 0.006 + 1000 * 0.30 + 100 * 1.20 = 3 + 300 + 120 = 423 per million
    assert Decimal(cost["peak_usd"]) == Decimal("0.000423")
    assert Decimal(cost["off_peak_usd"]) == Decimal("0.0002115")
    assert cost["tariff"]["verified_date"] == "2026-10-20"


@pytest.mark.parametrize(
    "usage",
    [None, {}, {**USAGE, "completion_tokens": -1}, {**USAGE, "completion_tokens": "1"}],
)
def test_cost_unknown_without_usable_usage(usage):
    assert estimate_cost(usage) is None


def test_cost_is_recorded(screenshot, tmp_path):
    _, run_dir = check(FakeServer(completion('{"findings": []}')), screenshot, tmp_path)
    run = json.loads((run_dir / "run.json").read_text())
    assert Decimal(run["estimated_cost"]["peak_usd"]) == Decimal("0.000423")
