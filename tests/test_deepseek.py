import base64
import io
import json
from decimal import Decimal
from urllib.error import HTTPError

import pytest

from l10n_checker.capture import REPO_ROOT
from l10n_checker.deepseek import (
    CAP,
    INPUT_BOUND,
    MODEL,
    RESERVATION,
    DeepSeekProvider,
    format_prompt,
    input_bound,
    peak_cost,
)
from l10n_checker.small_text import PROMPT, ReadingOutput
from l10n_checker.small_text_deepseek import (
    diagnose_metadata,
    execute_paid,
    load_context,
)
from l10n_checker.vision import ProviderError

FAKE_KEY = "unit-test-secret-not-a-real-key"


def response(content='{"findings": [], "readings": []}', finish="stop"):
    return {
        "model": MODEL,
        "choices": [{"message": {"content": content}, "finish_reason": finish}],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "prompt_cache_hit_tokens": 20,
        },
    }


class Opener:
    def __init__(self, outcome=None, balance_error=None):
        self.outcome = outcome if outcome is not None else response()
        self.balance_error = balance_error
        self.requests = []
        self.balance_calls = 0
        self.before_post = None

    def open(self, request, *, timeout):
        self.requests.append((request, timeout))
        if request.full_url.endswith("/models"):
            value = {"data": [{"id": MODEL}]}
        elif request.full_url.endswith("/user/balance"):
            self.balance_calls += 1
            if self.balance_calls == self.balance_error:
                raise TimeoutError(FAKE_KEY)
            value = {
                "is_available": True,
                "balance_infos": [{"currency": "USD", "total_balance": "2.00"}],
            }
        else:
            if self.before_post:
                self.before_post()
            if isinstance(self.outcome, Exception):
                raise self.outcome
            value = self.outcome
        return io.BytesIO(json.dumps(value).encode())


def provider(outcome=None, **kwargs):
    return DeepSeekProvider(FAKE_KEY, opener=Opener(outcome, **kwargs))


def execute(p, screenshot, tmp_path, slot=1, published=None):
    return execute_paid(
        p,
        {"slot": slot},
        screenshot,
        tmp_path,
        "approved",
        format_prompt(ReadingOutput.model_json_schema()),
        p.settings,
        published,
    )


def test_inline_image_effective_settings_and_frozen_task_instruction():
    p = provider()
    prompt = format_prompt(ReadingOutput.model_json_schema())
    p.generate(b"exact-image", "image/png", prompt)
    req, timeout = p._opener.requests[0]
    data = json.loads(req.data)
    assert req.full_url == "https://api.deepseek.com/chat/completions"
    assert req.get_header("Authorization") == "Bearer " + FAKE_KEY
    assert timeout == 1800
    assert data["thinking"] == {"type": "disabled"}
    assert data["max_tokens"] == 8192 and data["temperature"] == 0
    assert data["response_format"] == {"type": "json_object"}
    image, text = data["messages"][0]["content"]
    assert base64.b64decode(image["image_url"]["url"].split(",")[1]) == b"exact-image"
    assert image["image_url"]["detail"] == "original"
    assert text["text"].startswith(PROMPT)
    assert "additionalProperties" in text["text"]
    assert FAKE_KEY not in json.dumps(p.settings)
    assert len(p._opener.requests) == 1


def test_request_and_money_reservations_survive_all_twelve_sends(screenshot, tmp_path):
    p = provider()
    ledger_path = tmp_path / "issue-10-deepseek-ledger.json"

    def check_reservation_before_post():
        entry = json.loads(ledger_path.read_text())["slots"][-1]
        assert entry["requests_sent"] is None and entry["reserved_usd"] == str(
            RESERVATION
        )

    p._opener.before_post = check_reservation_before_post
    for slot in range(1, 13):
        result, _, halt = execute(p, screenshot, tmp_path, slot)
        assert result.status == "checked" and halt is None
        assert result.metadata["requests_sent"] == 1
    ledger = json.loads(ledger_path.read_text())
    assert len(ledger["slots"]) == 12
    assert (
        sum(Decimal(e["reserved_usd"]) for e in ledger["slots"])
        == Decimal("0.2359296")
        < CAP
    )
    count = len(p._opener.requests)
    with pytest.raises(ValueError, match="already reserved or cap"):
        execute(p, screenshot, tmp_path, 12)
    assert len(p._opener.requests) == count
    assert sum(req.get_method() == "POST" for req, _ in p._opener.requests) == 12


@pytest.mark.parametrize(
    "outcome,reason",
    [
        (TimeoutError(FAKE_KEY), "timeout:"),
        (response(finish="length"), "incomplete_response:"),
        (response(content="unfinished{"), "invalid_response:"),
        (
            response(
                content='{"findings": [], "readings": [{"text_seen": "Example", "region": "center", "confidence": 1}]}'
            ),
            "invalid_response:",
        ),
    ],
)
def test_failures_count_once_without_output_repair(
    outcome, reason, screenshot, tmp_path
):
    p = provider(outcome)
    result, directory, _ = execute(p, screenshot, tmp_path)
    assert result.status == "not_checked" and result.reason.startswith(reason)
    assert result.metadata["requests_sent"] == 1
    assert not (directory / "output.json").exists()
    ledger = json.loads((tmp_path / "issue-10-deepseek-ledger.json").read_text())
    assert ledger["slots"][0]["reserved_usd"] == str(RESERVATION)
    assert sum(req.get_method() == "POST" for req, _ in p._opener.requests) == 1
    for path in tmp_path.rglob("*"):
        if path.is_file():
            assert FAKE_KEY.encode() not in path.read_bytes()


def test_http_error_redacts_secret_and_stops_on_auth_failure(screenshot, tmp_path):
    error = HTTPError(
        "https://api.deepseek.com/chat/completions",
        401,
        "error",
        {},
        io.BytesIO(FAKE_KEY.encode()),
    )
    p = provider(error)
    result, directory, halt = execute(p, screenshot, tmp_path)
    assert halt and result.status == "not_checked"
    assert FAKE_KEY not in (directory / "response_raw.json").read_text()
    with pytest.raises(ValueError, match="halted"):
        execute(p, screenshot, tmp_path, 2)


@pytest.mark.parametrize("balance_error,posts", [(1, 0), (2, 1)])
def test_balance_failure_stops_without_unbudgeted_retry(
    balance_error, posts, screenshot, tmp_path
):
    p = provider(balance_error=balance_error)
    if balance_error == 1:
        with pytest.raises(ValueError, match="Pre-send"):
            execute(p, screenshot, tmp_path)
    else:
        _, _, halt = execute(p, screenshot, tmp_path)
        assert halt
    with pytest.raises(ValueError, match="halted"):
        execute(p, screenshot, tmp_path, 2)
    assert sum(req.get_method() == "POST" for req, _ in p._opener.requests) == posts


def test_interrupted_and_published_reservations_cannot_be_reset(screenshot, tmp_path):
    p = provider()
    execute(p, screenshot, tmp_path)
    path = tmp_path / "issue-10-deepseek-ledger.json"
    published = json.loads(path.read_text())
    path.unlink()
    count = len(p._opener.requests)
    with pytest.raises(ValueError, match="cannot be reset"):
        execute(p, screenshot, tmp_path, 2, published)
    pending = published.copy()
    pending["slots"][0]["requests_sent"] = None
    path.write_text(json.dumps(pending))
    with pytest.raises(ValueError, match="Interrupted"):
        execute(p, screenshot, tmp_path, 2)
    assert len(p._opener.requests) == count


def test_usage_cost_and_bounds():
    assert peak_cost(
        {"prompt_tokens": 100, "prompt_cache_hit_tokens": 20, "completion_tokens": 50}
    ) == Decimal("0.00008412")
    assert peak_cost(None) is None
    assert peak_cost({"prompt_tokens": True, "completion_tokens": 3}) is None
    with pytest.raises(ValueError, match="reserved token bound"):
        peak_cost({"prompt_tokens": INPUT_BOUND + 1, "completion_tokens": 1})
    with pytest.raises(ValueError, match="input bound"):
        input_bound("a" * 8193)


def test_money_guard_and_settings_refuse_before_network(
    monkeypatch, screenshot, tmp_path
):
    from l10n_checker import small_text_deepseek as experiment

    p = provider()
    monkeypatch.setattr(experiment, "CAP", Decimal("0.01"))
    with pytest.raises(ValueError, match="exceeds USD"):
        execute(p, screenshot, tmp_path)
    assert not p._opener.requests
    with pytest.raises(ValueError, match="settings"):
        execute_paid(p, {"slot": 1}, screenshot, tmp_path, "approved", "json", {})
    assert not p._opener.requests


def test_balance_below_reservation_prevents_generation(screenshot, tmp_path):
    p = provider()
    p.balance = lambda: Decimal("0.001")
    with pytest.raises(ValueError, match="insufficient"):
        execute(p, screenshot, tmp_path)
    assert not any(req.get_method() == "POST" for req, _ in p._opener.requests)


def test_tampered_reservation_does_not_release_budget(screenshot, tmp_path):
    p = provider()
    execute(p, screenshot, tmp_path)
    path = tmp_path / "issue-10-deepseek-ledger.json"
    ledger = json.loads(path.read_text())
    ledger["slots"][0]["reserved_usd"] = "0"
    path.write_text(json.dumps(ledger))
    count = len(p._opener.requests)
    with pytest.raises(ValueError, match="cannot be changed"):
        execute(p, screenshot, tmp_path, 2)
    assert len(p._opener.requests) == count


def test_only_approved_inputs_and_credentials_required_without_reading_secrets():
    _, _, request, image, prompt = load_context(REPO_ROOT, 1)
    assert request["slot"] == 1 and image.name.endswith("1271001.png")
    assert input_bound(prompt) == INPUT_BOUND
    with pytest.raises(ValueError, match="missing"):
        DeepSeekProvider("")
    with pytest.raises(ValueError, match="endpoint"):
        provider()._request("/other")
    with pytest.raises(ProviderError, match="Unexpected response model"):
        provider({**response(), "model": "unapproved"}).generate(
            b"png", "image/png", "json"
        )


def test_metadata_diagnosis_is_read_only_and_preserves_errors(tmp_path):
    class MissingModel(Opener):
        def open(self, request, *, timeout):
            self.requests.append((request, timeout))
            return io.BytesIO(b'{"data": [{"id": "text-only-model"}]}')

    p = DeepSeekProvider(FAKE_KEY, opener=MissingModel())
    record = diagnose_metadata(p, tmp_path)
    assert record["generation_requests_sent"] == 0
    assert record["error"]["raw"]["available_models"] == ["text-only-model"]
    assert len(p._opener.requests) == 1
    assert p._opener.requests[0][0].get_method() == "GET"
    with pytest.raises(ValueError, match="already reserved"):
        diagnose_metadata(p, tmp_path)
    assert len(p._opener.requests) == 1


def test_tls_verification_and_preflight_recovery_do_not_reset_sends(
    screenshot, tmp_path
):
    import ssl
    from urllib.request import HTTPSHandler

    from l10n_checker.local_model import NoRedirect

    p = DeepSeekProvider(FAKE_KEY)
    handler = next(h for h in p._opener.handlers if isinstance(h, HTTPSHandler))
    assert handler._context.verify_mode == ssl.CERT_REQUIRED
    assert handler._context.check_hostname
    assert any(isinstance(h, NoRedirect) for h in p._opener.handlers)
    path = tmp_path / "issue-10-deepseek-ledger.json"
    path.write_text(
        json.dumps(
            {
                "approval_sha256": "approved",
                "max_requests": 12,
                "max_usd": "0.25",
                "slots": [],
                "discovery": [],
                "halt_reason": "Initial model discovery failed; zero generation sends",
            }
        )
    )
    p = provider()
    result, _, halt = execute_paid(
        p,
        {"slot": 1},
        screenshot,
        tmp_path,
        "approved",
        format_prompt(ReadingOutput.model_json_schema()),
        p.settings,
        resume_preflight=True,
    )
    assert result.status == "checked" and halt is None
    ledger = json.loads(path.read_text())
    assert ledger["preflight_recovery"]["prior_halt_reason"]
    assert len(ledger["slots"]) == 1
    with pytest.raises(ValueError, match="original zero-send"):
        execute_paid(
            p,
            {"slot": 2},
            screenshot,
            tmp_path,
            "approved",
            "json",
            p.settings,
            resume_preflight=True,
        )
