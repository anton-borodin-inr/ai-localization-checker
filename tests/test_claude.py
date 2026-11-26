import base64
import json
from decimal import Decimal

import httpx
import pytest

from l10n_checker.claude import (
    API_VERSION,
    CONSERVATIVE_INPUT_TOKENS,
    EFFORT,
    MAX_TOKENS,
    MODEL,
    TARIFF,
    ClaudeProvider,
    claude_schema,
    estimate_cost,
)
from l10n_checker.vision import RequestBudget, build_prompt, run_check

KEY = "test-claude-key-DO-NOT-LEAK"
RETURNED_MODEL = "claude-sonnet-5-5-20261001"
FINDING = {
    "defect_type": "overflow",
    "text_seen": "Hilfe",
    "region": "bottom-left",
    "confidence": 0.95,
}
USAGE = {
    "input_tokens": 4200,
    "output_tokens": 120,
    "cache_creation_input_tokens": 0,
    "cache_read_input_tokens": 0,
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


def message(content, stop_reason="end_turn", **extra):
    if isinstance(content, str):
        blocks = [{"type": "text", "text": content}]
    else:
        blocks = content
    return {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "model": RETURNED_MODEL,
        "content": blocks,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": USAGE,
        **extra,
    }


class FakeServer:
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
    provider = ClaudeProvider(KEY, transport=httpx.MockTransport(server))
    return run_check(
        provider,
        screenshot,
        tmp_path / "runs",
        RequestBudget(max_requests),
        secrets=(KEY,),
        retry_delay_s=0,
    )


def test_success(screenshot, tmp_path):
    server = FakeServer(message(model_output([FINDING])))
    result, run_dir = check(server, screenshot, tmp_path)
    assert result.status == "checked"
    assert [f.model_dump() for f in result.findings] == [FINDING]
    run = json.loads((run_dir / "run.json").read_text())
    assert run["provider"] == "claude"
    assert run["model"] == MODEL
    assert run["model_version"] == RETURNED_MODEL
    assert run["wrapper_version"] is None
    assert run["usage"] == USAGE
    assert run["requests_sent"] == 1
    assert run["attempts"][0]["outcome"] == "ok"
    assert Decimal(run["estimated_cost"]["usd"]) == Decimal("0.0096")


def test_request_payload_and_settings(screenshot, tmp_path):
    server = FakeServer(message(model_output()))
    _, run_dir = check(server, screenshot, tmp_path)
    (request,) = server.requests
    assert request.method == "POST"
    assert str(request.url) == "https://api.anthropic.com/v1/messages"
    assert request.headers["x-api-key"] == KEY
    assert request.headers["anthropic-version"] == API_VERSION
    body = json.loads(request.content)
    assert body["model"] == MODEL
    assert body["max_tokens"] == MAX_TOKENS
    assert body["stream"] is False
    assert body["thinking"] == {"type": "between_tools"}
    assert body["output_config"] == {
        "effort": EFFORT,
        "format": {"type": "json_schema", "schema": claude_schema()},
    }
    for removed in ("temperature", "top_p", "top_k"):
        assert removed not in body
    image_part, text_part = body["messages"][0]["content"]
    assert image_part["type"] == "image"
    assert image_part["source"]["type"] == "base64"
    assert image_part["source"]["media_type"] == "image/png"
    assert base64.b64decode(image_part["source"]["data"]) == screenshot.read_bytes()
    prompt = build_prompt("en")
    assert text_part == {"type": "text", "text": prompt}
    assert (run_dir / "prompt.txt").read_text() == prompt
    assert (run_dir / "prompt_sent.txt").read_text() == prompt
    settings = json.loads((run_dir / "run.json").read_text())["settings"]
    assert settings["anthropic_version"] == API_VERSION
    assert settings["thinking"] == {"type": "between_tools"}
    assert settings["output_config"]["effort"] == EFFORT
    assert settings["output_config"]["format"]["type"] == "json_schema"
    assert settings["transport_retries"] == 0


def test_claude_schema_inlines_defs_and_drops_numeric_bounds():
    schema = claude_schema()
    dumped = json.dumps(schema)
    assert "$defs" not in dumped
    assert "$ref" not in dumped
    assert '"minimum"' not in dumped
    assert '"maximum"' not in dumped
    assert schema["additionalProperties"] is False
    finding_schema = schema["properties"]["findings"]["items"]
    assert finding_schema["additionalProperties"] is False
    assert finding_schema["properties"]["defect_type"]["enum"] == [
        "overflow",
        "wrong_language",
        "truncated_text",
        "other",
    ]


@pytest.mark.parametrize(
    ("outcome", "reason"),
    [
        (message(model_output(), stop_reason="refusal"), "refusal"),
        (message([], stop_reason="refusal"), "refusal"),
        (message('{"findings": [', stop_reason="max_tokens"), "incomplete_response"),
        (message(model_output(), stop_reason="pause_turn"), "incomplete_response"),
        (message(model_output(), stop_reason=None), "incomplete_response"),
        (message([]), "empty_response"),
        (
            message([{"type": "thinking", "thinking": model_output([FINDING])}]),
            "empty_response",
        ),
        (message([{"type": "text", "text": "   "}]), "empty_response"),
        (
            message([{"type": "text", "text": "{"}, {"type": "text", "text": "}"}]),
            "incomplete_response",
        ),
        (message("not json"), "invalid_response"),
        (message(f"```json\n{model_output()}\n```"), "invalid_response"),
        (message(model_output([{**FINDING, "confidence": 1.5}])), "invalid_response"),
        (message(model_output([{**FINDING, "extra": 1}])), "invalid_response"),
        (message(model_output(unreadable_regions=["top"])), "invalid_response"),
        (httpx.ReadTimeout("read timed out"), "timeout"),
        (httpx.ConnectError("connection refused"), "api_error"),
        (httpx.Response(400, text="bad request"), "api_error"),
        (httpx.Response(429, text="rate limited"), "rate_limited"),
        (httpx.Response(529, text="overloaded"), "api_error"),
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


@pytest.mark.parametrize(
    ("outcome", "reason"),
    [
        (message([], stop_reason="refusal"), "refusal"),
        (message("{", stop_reason="max_tokens"), "incomplete_response"),
        (message([]), "empty_response"),
        (message("not json"), "invalid_response"),
    ],
)
def test_rejected_response_keeps_usage_cost_and_model(
    screenshot, tmp_path, outcome, reason
):
    result, run_dir = check(FakeServer(outcome), screenshot, tmp_path)
    assert result.status == "not_checked"
    assert result.reason.startswith(reason)
    run = json.loads((run_dir / "run.json").read_text())
    assert run["model_version"] == RETURNED_MODEL
    assert run["usage"] == USAGE
    assert Decimal(run["estimated_cost"]["usd"]) == Decimal("0.0096")


def test_cost_estimate_and_worst_case_reserve():
    # 4200 * 2.00 + 120 * 10.00 = 8400 + 1200 = 9600 per million = 0.0096 USD
    cost = estimate_cost(USAGE)
    assert Decimal(cost["usd"]) == Decimal("0.0096")
    assert Decimal(cost["peak_usd"]) == Decimal("0.0096")
    assert cost["tariff"] == TARIFF

    cached = estimate_cost(
        {
            "input_tokens": 1000,
            "output_tokens": 100,
            "cache_creation_input_tokens": 2000,
            "cache_read_input_tokens": 3000,
        }
    )
    # (1000*2 + 100*10 + 2000*2.5 + 3000*0.1) / 1e6 = 8300 / 1e6 = 0.0083
    assert Decimal(cached["usd"]) == Decimal("0.0083")

    for bad in (
        None,
        {},
        {"input_tokens": -1, "output_tokens": 1},
        {"input_tokens": True, "output_tokens": 1},
    ):
        assert estimate_cost(bad) is None

    provider = ClaudeProvider(KEY, transport=httpx.MockTransport(FakeServer()))
    expected_reserve = (
        Decimal(CONSERVATIVE_INPUT_TOKENS) * Decimal("2.00")
        + Decimal(MAX_TOKENS) * Decimal("10.00")
    ) / Decimal(1_000_000)
    assert provider.worst_case_reserve_usd() == expected_reserve == Decimal("0.066912")


def test_key_is_never_written(screenshot, tmp_path):
    echo = httpx.Response(401, text=f"bad key {KEY}")
    _, run_dir = check(FakeServer(echo), screenshot, tmp_path)
    for path in run_dir.iterdir():
        assert KEY not in path.read_text()
