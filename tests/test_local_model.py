import base64
import hashlib
import io
import json
from urllib.error import HTTPError, URLError

import pytest

from l10n_checker.local_model import ENDPOINT, MODEL, LocalVisionProvider, NoRedirect
from l10n_checker.small_text import PROMPT, file_hash
from l10n_checker.small_text_local import (
    execute_local,
    load_context,
    published_reservations_present,
)


class Opener:
    def __init__(self, outcome=None):
        self.outcome = outcome
        self.requests = []

    def open(self, request, *, timeout):
        self.requests.append((request, timeout))
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return io.BytesIO(json.dumps(self.outcome or response()).encode())


def response(content='{"findings": [], "readings": []}', finish="stop"):
    return {
        "model": MODEL,
        "choices": [{"message": {"content": content}, "finish_reason": finish}],
        "usage": {"prompt_tokens": 42, "completion_tokens": 12, "total_tokens": 54},
    }


def provider(outcome=None):
    return LocalVisionProvider(
        {"type": "object"}, {"id": MODEL}, opener=Opener(outcome)
    )


def test_request_preserves_image_prompt_schema_and_effective_settings():
    p = provider()
    result = p.generate(b"exact-png", "image/png", PROMPT)
    request, timeout = p._opener.requests[0]
    body = json.loads(request.data)
    assert request.full_url == "http://127.0.0.1:1234/v1/chat/completions"
    assert timeout == p.settings["timeout_s"] == 180
    assert "Authorization" not in request.headers
    assert len(body["messages"]) == 1
    image, text = body["messages"][0]["content"]
    assert base64.b64decode(image["image_url"]["url"].split(",")[1]) == b"exact-png"
    assert text["text"] == PROMPT
    assert body["response_format"] == p.settings["response_format"]
    for name in ("model", "temperature", "max_tokens", "stream"):
        assert body[name] == p.settings[name]
    assert "media_resolution" not in body
    assert result.usage["prompt_tokens"] == 42
    assert result.model_version is None  # alias does not establish a revision


def test_transport_disables_environment_proxies_and_redirects():
    from urllib.request import ProxyHandler

    p = LocalVisionProvider({}, {})
    assert any(isinstance(h, NoRedirect) for h in p._opener.handlers)
    # Empty ProxyHandler is omitted by urllib: no proxy_open handlers installed.
    assert not any(isinstance(h, ProxyHandler) for h in p._opener.handlers)
    with pytest.raises(HTTPError, match="Redirect refused"):
        NoRedirect().redirect_request(
            type("Request", (), {"full_url": "http://127.0.0.1:1234"})(),
            io.BytesIO(),
            302,
            "",
            {},
            "https://example.com",
        )


@pytest.mark.parametrize(
    "outcome,reason",
    [
        (TimeoutError("slow"), "timeout:"),
        (URLError("connection refused"), "api_error:"),
        (response(finish="length"), "incomplete_response:"),
        ({"model": MODEL, "choices": []}, "empty_response:"),
        ({**response(), "model": "another-model"}, "api_error:"),
        (response(content="```json\n{}\n```"), "invalid_response:"),
        (
            response(
                content='{"findings": [], "readings": [{"text_seen":"x","region":"bad"}]}'
            ),
            "invalid_response:",
        ),
    ],
)
def test_unusable_response_is_recorded_not_checked_without_retry(
    outcome, reason, screenshot, tmp_path
):
    p = provider(outcome)
    result, directory = execute_local(p, {"slot": 1}, screenshot, tmp_path, "approved")
    assert result.status == "not_checked" and result.reason.startswith(reason)
    assert result.metadata["requests_sent"] == 1
    assert len(p._opener.requests) == 1
    assert not (directory / "output.json").exists()
    with pytest.raises(ValueError, match="already reserved"):
        execute_local(p, {"slot": 1}, screenshot, tmp_path, "approved")
    assert len(p._opener.requests) == 1


def test_http_failure_counts_and_raw_diagnostic_is_preserved(screenshot, tmp_path):
    error = HTTPError(
        "http://127.0.0.1:1234", 503, "unavailable", {}, io.BytesIO(b"bad")
    )
    p = provider(error)
    result, directory = execute_local(p, {"slot": 1}, screenshot, tmp_path, "approved")
    assert result.status == "not_checked" and "HTTP 503" in result.reason
    assert result.metadata["requests_sent"] == 1
    assert json.loads((directory / "response_raw.json").read_text())["body"] == "bad"
    assert len(p._opener.requests) == 1


def test_extra_reading_confidence_is_preserved_but_not_silently_accepted(
    screenshot, tmp_path
):
    text = '{"findings": [], "readings": [{"text_seen": "Archery", "region": "center", "confidence": 1.0}]}'
    result, directory = execute_local(
        provider(response(text)), {"slot": 1}, screenshot, tmp_path, "approved"
    )
    assert result.status == "not_checked"
    assert "readings.0.confidence" in result.reason
    assert result.metadata["requests_sent"] == 1
    raw = json.loads((directory / "response_raw.json").read_text())
    assert raw["choices"][0]["message"]["content"] == text
    assert not (directory / "output.json").exists()


def test_twelve_send_cap_and_published_reservations(screenshot, tmp_path):
    p = provider()
    for slot in range(1, 13):
        result, _ = execute_local(p, {"slot": slot}, screenshot, tmp_path, "approved")
        assert result.status == "checked" and result.metadata["max_requests"] == 1
    ledger = json.loads((tmp_path / "issue-10-local-ledger.json").read_text())
    assert sum(r["requests_sent"] for r in ledger["slots"]) == 12
    with pytest.raises(ValueError, match="cap reached"):
        execute_local(p, {"slot": 13}, screenshot, tmp_path, "approved")
    assert len(p._opener.requests) == 12
    with pytest.raises(ValueError, match="cannot be reset"):
        execute_local(
            p, {"slot": 1}, screenshot, tmp_path / "fresh", "approved", ledger
        )
    assert len(p._opener.requests) == 12


def test_interrupted_local_reservation_cannot_be_reused(screenshot, tmp_path):
    p = provider(RuntimeError("interrupted"))
    with pytest.raises(RuntimeError):
        execute_local(p, {"slot": 1}, screenshot, tmp_path, "approved")
    with pytest.raises(ValueError, match="already reserved"):
        execute_local(p, {"slot": 1}, screenshot, tmp_path, "approved")
    assert len(p._opener.requests) == 1


def test_published_pending_can_complete_but_reservation_cannot_be_reset():
    pending = {
        "slot": 5,
        "run_id": "fixed",
        "reservation": 1,
        "requests_sent": None,
        "status": "reserved_or_interrupted",
    }
    completed = {**pending, "requests_sent": 1, "status": "not_checked"}
    assert published_reservations_present({"slots": [pending]}, {"slots": [completed]})
    assert not published_reservations_present(
        {"slots": [completed]}, {"slots": [pending]}
    )
    assert not published_reservations_present({"slots": [pending]}, {"slots": []})
    assert not published_reservations_present(
        {"slots": [pending]}, {"slots": [{**completed, "run_id": "replacement"}]}
    )


def test_context_checks_approval_images_and_endpoint(screenshot, tmp_path):
    folder = tmp_path / "docs/evidence/10/local-model"
    folder.mkdir(parents=True)
    source = tmp_path / "docs/evidence/8/final/screen.png"
    source.parent.mkdir(parents=True)
    source.write_bytes(screenshot.read_bytes())
    for path in (
        folder / "plan.md",
        folder / "models-before.json",
        folder.parent / "reference-amendment-candidate.json",
        folder.parent / "reference-amendment-approval.json",
    ):
        path.write_text("frozen")
    (folder.parent / "combined-summary.json").write_text('{"requests_sent":27}')
    plan = {
        "local_cap": 12,
        "baseline_gemini_requests": 27,
        "combined_actual_cap": 39,
        "retries": 0,
        "model": MODEL,
        "endpoint": ENDPOINT,
        "prompt_sha256": hashlib.sha256(PROMPT.encode()).hexdigest(),
        "requests": [
            {
                "slot": i,
                "max_requests": 1,
                "image": str(source.relative_to(tmp_path)),
                "image_sha256": file_hash(source),
            }
            for i in range(1, 13)
        ],
    }
    path = folder / "request-plan.json"
    path.write_text(json.dumps(plan))
    approval = {
        "accepted_by": "Anton",
        "status": "approved",
        "local_cap": 12,
        "combined_actual_cap": 39,
        "retries": 0,
        "request_plan_sha256": file_hash(path),
        "plan_sha256": file_hash(folder / "plan.md"),
        "reference_sha256": file_hash(
            folder.parent / "reference-amendment-candidate.json"
        ),
        "reference_approval_sha256": file_hash(
            folder.parent / "reference-amendment-approval.json"
        ),
        "metadata_sha256": file_hash(folder / "models-before.json"),
    }
    approval_path = folder / "approval.json"
    approval_path.write_text(json.dumps(approval))
    assert load_context(tmp_path, 1)[3] == source
    source.write_bytes(b"changed")
    with pytest.raises(ValueError, match="Original image changed"):
        load_context(tmp_path, 1)
    source.write_bytes(screenshot.read_bytes())
    (folder / "plan.md").write_text("changed")
    with pytest.raises(ValueError, match="Approved local input changed"):
        load_context(tmp_path, 1)
    (folder / "plan.md").write_text("frozen")
    path.write_text(json.dumps({**plan, "endpoint": "https://example.com"}))
    approval_path.write_text(
        json.dumps({**approval, "request_plan_sha256": file_hash(path)})
    )
    with pytest.raises(ValueError, match="fixed allocation"):
        load_context(tmp_path, 1)


@pytest.mark.parametrize("timeout", [400, 1800])
def test_extended_timeout_is_sent_and_recorded(timeout):
    p = LocalVisionProvider({}, {}, timeout_s=timeout, opener=Opener())
    p.generate(b"image", "image/png", PROMPT)
    assert p._opener.requests[0][1] == p.settings["timeout_s"] == timeout


def test_approved_thirteenth_send_only_repeats_initial_timeout(screenshot, tmp_path):
    first = provider(TimeoutError("slow"))
    execute_local(first, {"slot": 1}, screenshot, tmp_path, "approved")
    p = provider()
    with pytest.raises(ValueError, match="explicitly approved"):
        execute_local(p, {"slot": 1}, screenshot, tmp_path, "approved", attempt=2)
    execute_local(
        p,
        {"slot": 1},
        screenshot,
        tmp_path,
        "approved",
        attempt=2,
        extension_hash="extension",
    )
    for slot in range(2, 13):
        execute_local(
            p,
            {"slot": slot},
            screenshot,
            tmp_path,
            "approved",
            extension_hash="extension",
        )
    ledger = json.loads((tmp_path / "issue-10-local-ledger.json").read_text())
    assert sum(r["requests_sent"] for r in ledger["slots"]) == 13
    assert len(first._opener.requests) + len(p._opener.requests) == 13
    with pytest.raises(ValueError):
        execute_local(
            p,
            {"slot": 1},
            screenshot,
            tmp_path,
            "approved",
            attempt=2,
            extension_hash="extension",
        )
    with pytest.raises(ValueError, match="cap reached"):
        execute_local(
            p,
            {"slot": 13},
            screenshot,
            tmp_path,
            "approved",
            extension_hash="extension",
        )
    assert len(first._opener.requests) + len(p._opener.requests) == 13


def test_nightly_cap_allows_only_one_third_attempt_after_both_timeouts(
    screenshot, tmp_path
):
    slow = provider(TimeoutError("slow"))
    execute_local(slow, {"slot": 1}, screenshot, tmp_path, "approved")
    execute_local(
        slow,
        {"slot": 1},
        screenshot,
        tmp_path,
        "approved",
        attempt=2,
        extension_hash="400",
    )
    p = provider()
    with pytest.raises(ValueError, match="third attempt"):
        execute_local(
            p,
            {"slot": 1},
            screenshot,
            tmp_path,
            "approved",
            attempt=3,
            extension_hash="400",
        )
    execute_local(
        p,
        {"slot": 1},
        screenshot,
        tmp_path,
        "approved",
        attempt=3,
        extension_hash="400",
        nightly_hash="nightly",
    )
    for slot in range(2, 13):
        execute_local(
            p,
            {"slot": slot},
            screenshot,
            tmp_path,
            "approved",
            extension_hash="400",
            nightly_hash="nightly",
        )
    ledger = json.loads((tmp_path / "issue-10-local-ledger.json").read_text())
    assert sum(r["requests_sent"] for r in ledger["slots"]) == 14
    with pytest.raises(ValueError, match="third attempt"):
        execute_local(
            p,
            {"slot": 1},
            screenshot,
            tmp_path,
            "approved",
            attempt=3,
            extension_hash="400",
            nightly_hash="nightly",
        )
    with pytest.raises(ValueError, match="cap reached"):
        execute_local(
            p,
            {"slot": 13},
            screenshot,
            tmp_path,
            "approved",
            extension_hash="400",
            nightly_hash="nightly",
        )
    assert len(slow._opener.requests) + len(p._opener.requests) == 14
