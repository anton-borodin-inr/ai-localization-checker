import hashlib
import json
import runpy
from pathlib import Path

import pytest

from l10n_checker.small_text_resume import (
    FAILED_SLOTS,
    execute_attempt,
    is_503,
    load_context,
)
from l10n_checker.vision import ProviderError, ProviderResponse


class Provider:
    name = "fake"
    model = "offline"
    sdk_version = "test"

    def __init__(self, outcome=None):
        self.outcome = outcome
        self.calls = 0
        self.settings = {}

    def generate(self, image, mime_type, prompt):
        self.calls += 1
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return ProviderResponse(text='{"findings": [], "readings": []}', raw={})


def test_all_nine_slots_have_two_attempts_and_one_global_33_cap(screenshot, tmp_path):
    provider = Provider(ProviderError("api_error", "ServerError: 503 UNAVAILABLE"))
    runs = tmp_path / "runs"
    for slot in FAILED_SLOTS:
        for attempt in (1, 2):
            result, _ = execute_attempt(
                provider,
                {"slot": slot},
                screenshot,
                runs,
                "approval",
                f"parent-{slot}",
                attempt,
            )
            assert result.metadata["requests_sent"] == 1
    assert provider.calls == 18
    ledger = json.loads((runs / "issue-10-continuation-ledger.json").read_text())
    assert (
        ledger["baseline_requests_sent"]
        + sum(r["requests_sent"] for r in ledger["attempts"])
        == 33
    )
    with pytest.raises(ValueError, match="cap reached"):
        execute_attempt(
            provider, {"slot": 2}, screenshot, runs, "approval", "parent-2", 1
        )
    assert provider.calls == 18


@pytest.mark.parametrize(
    "outcome",
    [
        None,
        ProviderError("timeout", "timeout"),
        ProviderError("rate_limited", "429"),
        ProviderError("api_error", "ServerError: 500 INTERNAL"),
    ],
)
def test_no_second_send_after_success_or_another_error(screenshot, tmp_path, outcome):
    provider = Provider(outcome)
    execute_attempt(
        provider, {"slot": 2}, screenshot, tmp_path / "runs", "approval", "parent", 1
    )
    with pytest.raises(ValueError, match="first HTTP 503"):
        execute_attempt(
            provider,
            {"slot": 2},
            screenshot,
            tmp_path / "runs",
            "approval",
            "parent",
            2,
        )
    assert provider.calls == 1


def test_interruption_cannot_be_retried_and_duplicate_attempt_is_refused(
    screenshot, tmp_path
):
    provider = Provider(RuntimeError("interrupted"))
    with pytest.raises(RuntimeError):
        execute_attempt(
            provider,
            {"slot": 2},
            screenshot,
            tmp_path / "runs",
            "approval",
            "parent",
            1,
        )
    with pytest.raises(ValueError, match="used already"):
        execute_attempt(
            provider,
            {"slot": 2},
            screenshot,
            tmp_path / "runs",
            "approval",
            "parent",
            1,
        )
    with pytest.raises(ValueError, match="first HTTP 503"):
        execute_attempt(
            provider,
            {"slot": 2},
            screenshot,
            tmp_path / "runs",
            "approval",
            "parent",
            2,
        )
    assert provider.calls == 1


def test_503_number_in_a_non_api_failure_is_not_retryable():
    assert is_503(
        {"status": "not_checked", "reason": "api_error: ServerError: 503 UNAVAILABLE"}
    )
    assert not is_503(
        {"status": "not_checked", "reason": "invalid_response: unexpected 503"}
    )
    assert not is_503(
        {"status": "not_checked", "reason": "timeout: call 503 timed out"}
    )


def test_summary_uses_first_success_instead_of_best_score():
    module = runpy.run_path(
        str(
            Path(__file__).resolve().parents[1]
            / "scripts/summarize_small_text_continuation.py"
        )
    )
    choose = module["choose_runs"]
    failed = {"slot": 2, "run_id": "original", "status": "not_checked"}
    first = {"slot": 2, "run_id": "first-success", "status": "checked", "coverage": 0.5}
    later = {"slot": 2, "run_id": "later", "status": "checked", "coverage": 1.0}
    assert choose([failed, first, later])[2]["run_id"] == "first-success"
    assert (
        choose([failed, {**failed, "run_id": "last-failure"}])[2]["run_id"]
        == "last-failure"
    )


def test_continuation_authorization_and_initial_ledger_are_hash_bound(
    tmp_path, screenshot
):
    folder = tmp_path / "docs/evidence/10"
    folder.mkdir(parents=True)
    image = tmp_path / "docs/evidence/8/final/screen.png"
    image.parent.mkdir(parents=True)
    image.write_bytes(screenshot.read_bytes())
    reference = folder / "reference-candidate.json"
    reference.write_text("reference")
    plan = {
        "task_request_cap": 15,
        "retries": 0,
        "free_tier_only": True,
        "reference_sha256": hashlib.sha256(reference.read_bytes()).hexdigest(),
        "requests": [
            {
                "slot": i,
                "max_requests": 1,
                "image": str(image.relative_to(tmp_path)),
                "image_sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
            }
            for i in range(1, 16)
        ],
    }
    (folder / "request-plan.json").write_text(json.dumps(plan))
    approval = {
        "accepted_by": "Anton",
        "status": "confirmed",
        "reference_sha256": plan["reference_sha256"],
        "plan_sha256": hashlib.sha256(
            (folder / "request-plan.json").read_bytes()
        ).hexdigest(),
    }
    (folder / "reference-approval.json").write_text(json.dumps(approval))
    baseline = {
        "slots": [
            {"slot": i, "requests_sent": 1, "run_id": f"parent-{i}"}
            for i in range(1, 16)
        ]
    }
    (folder / "ledger.json").write_text(json.dumps(baseline))
    local = tmp_path / "data/runs/issue-10-ledger.json"
    local.parent.mkdir(parents=True)
    local.write_text(json.dumps(baseline))
    original = local.parent / "parent-2/result.json"
    original.parent.mkdir(parents=True)
    original.write_text(
        json.dumps(
            {
                "status": "not_checked",
                "reason": "api_error: ServerError: 503 UNAVAILABLE",
            }
        )
    )
    continuation = {
        "accepted_by": "Anton",
        "status": "approved",
        "task_request_cap": 33,
        "additional_request_cap": 18,
        "max_new_attempts_per_slot": 2,
        "eligible_slots": list(FAILED_SLOTS),
        "retry_only_after_503": True,
        "reference_sha256": approval["reference_sha256"],
        "plan_sha256": approval["plan_sha256"],
        "initial_ledger_sha256": hashlib.sha256(
            (folder / "ledger.json").read_bytes()
        ).hexdigest(),
    }
    (folder / "continuation-approval.json").write_text(json.dumps(continuation))
    assert load_context(tmp_path, 2)[2]["slot"] == 2
    local.write_text(json.dumps({"slots": []}))
    with pytest.raises(ValueError, match="match the frozen"):
        load_context(tmp_path, 2)


def test_summary_refuses_unconfirmed_or_modified_amendment(tmp_path):
    module = runpy.run_path(
        str(
            Path(__file__).resolve().parents[1]
            / "scripts/summarize_small_text_continuation.py"
        )
    )
    read = module["amended_reference"]
    read.__globals__["FOLDER"] = tmp_path
    original = {"builds": {"clean": "pinned"}}
    original_path = tmp_path / "reference-candidate.json"
    original_path.write_text(json.dumps(original))
    old_hash = hashlib.sha256(original_path.read_bytes()).hexdigest()
    amended = {**original, "amends_reference_sha256": old_hash}
    path = tmp_path / "reference-amendment-candidate.json"
    path.write_text(json.dumps(amended))
    approval = {
        "accepted_by": "Anton",
        "status": "confirmed",
        "reference_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "amends_reference_sha256": old_hash,
    }
    approval_path = tmp_path / "reference-amendment-approval.json"
    approval_path.write_text(json.dumps(approval))
    assert read(original) == amended
    approval_path.write_text(json.dumps({**approval, "status": "pending"}))
    with pytest.raises(ValueError, match="Anton confirmation"):
        read(original)
    approval_path.write_text(json.dumps(approval))
    path.write_text(json.dumps({**amended, "changed": True}))
    with pytest.raises(ValueError, match="Anton confirmation"):
        read(original)
