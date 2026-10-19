import hashlib
import json

import pytest

from l10n_checker.gemini import GeminiProvider, response_schema
from l10n_checker.small_text import (
    PROMPT,
    ReadingOutput,
    exclusive_ledger,
    execute_slot,
    validate_inputs,
)
from l10n_checker.vision import ModelOutput, ProviderError, ProviderResponse


class Provider:
    name = "fake"
    model = "offline"
    sdk_version = "test"

    def __init__(self, outcome=None):
        self.settings = {}
        self.outcome = outcome
        self.calls = 0

    def generate(self, image, mime_type, prompt):
        self.calls += 1
        assert prompt == PROMPT
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return ProviderResponse(
            text=self.outcome or '{"findings": [], "readings": []}', raw={}
        )


@pytest.mark.parametrize(
    "outcome",
    [None, ProviderError("rate_limited", "429"), ProviderError("timeout", "timeout")],
)
def test_budget_survives_fifteen_separate_invocations(screenshot, tmp_path, outcome):
    runs = tmp_path / "runs"
    provider = Provider(outcome)
    for slot in range(1, 16):
        result, directory = execute_slot(
            provider, {"slot": slot}, screenshot, runs, "plan"
        )
        assert result.metadata["requests_sent"] == 1
        assert (directory / "experiment.json").is_file()
    assert provider.calls == 15
    with pytest.raises(ValueError, match="cap reached"):
        execute_slot(provider, {"slot": 16}, screenshot, runs, "plan")
    with pytest.raises(ValueError, match="already reserved"):
        execute_slot(provider, {"slot": 1}, screenshot, runs, "plan")
    ledger = json.loads((runs / "issue-10-ledger.json").read_text())
    assert sum(s["requests_sent"] for s in ledger["slots"]) == 15
    assert provider.calls == 15


def test_crash_reservation_is_not_reusable(screenshot, tmp_path):
    provider = Provider(RuntimeError("simulated process interruption"))
    runs = tmp_path / "runs"
    with pytest.raises(RuntimeError):
        execute_slot(provider, {"slot": 1}, screenshot, runs, "plan")
    ledger = json.loads((runs / "issue-10-ledger.json").read_text())
    assert ledger["slots"][0]["reservation"] == 1
    assert ledger["slots"][0]["requests_sent"] is None
    with pytest.raises(ValueError, match="already reserved"):
        execute_slot(provider, {"slot": 1}, screenshot, runs, "plan")
    assert provider.calls == 1


def test_concurrent_or_stale_lock_fails_closed(tmp_path):
    path = tmp_path / "runs/issue-10-ledger.json"
    with exclusive_ledger(path), pytest.raises(FileExistsError), exclusive_ledger(path):
        pytest.fail("must not acquire a second lock")


def test_bad_experimental_response_is_not_checked(screenshot, tmp_path):
    provider = Provider(
        '{"findings": [], "readings": [{"text_seen": "x", "region": "invalid"}]}'
    )
    result, directory = execute_slot(
        provider, {"slot": 1}, screenshot, tmp_path / "runs", "p"
    )
    assert result.status == "not_checked"
    assert result.reason.startswith("invalid_response")
    assert not (directory / "output.json").exists()


def test_experiment_saves_readings_without_changing_production_schema(
    screenshot, tmp_path
):
    original = response_schema()
    text = '{"findings": [], "readings": [{"text_seen": "Archer", "region": "bottom-left"}]}'
    result, directory = execute_slot(
        Provider(text), {"slot": 1}, screenshot, tmp_path / "runs", "p"
    )
    assert result.status == "checked"
    assert (
        json.loads((directory / "output.json").read_text())["readings"][0]["text_seen"]
        == "Archer"
    )
    assert "readings" not in ModelOutput.model_fields
    assert response_schema() == original


def test_ultra_is_sent_per_part_and_recorded_from_that_setting():
    from google.genai import types

    class Models:
        def generate_content(self, **request):
            self.request = request
            return types.GenerateContentResponse(
                candidates=[
                    types.Candidate(
                        content=types.Content(
                            parts=[types.Part(text='{"findings": [], "readings": []}')]
                        ),
                        finish_reason="STOP",
                    )
                ]
            )

    class Client:
        models = Models()

    provider = GeminiProvider(
        "offline",
        client=Client(),
        output_model=ReadingOutput,
        media_resolution=types.PartMediaResolutionLevel.MEDIA_RESOLUTION_ULTRA_HIGH,
    )
    provider.generate(b"png", "image/png", PROMPT)
    request = provider._client.models.request
    assert (
        request["contents"][0].media_resolution.level.value
        == "MEDIA_RESOLUTION_ULTRA_HIGH"
    )
    assert request["config"].media_resolution is None
    assert (
        provider.settings["media_resolution"]
        == request["contents"][0].media_resolution.level.value
    )
    assert provider.settings["media_resolution_scope"] == "part"
    assert provider.settings["sdk_retry_attempts"] == 1
    assert provider.settings["response_schema"] == response_schema(ReadingOutput)


def test_reference_approval_is_hash_bound(tmp_path):
    evidence = tmp_path / "docs/evidence/10"
    evidence.mkdir(parents=True)
    reference = evidence / "reference-candidate.json"
    reference.write_text("reference")
    image = tmp_path / "docs/evidence/8/final/screen.png"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"image")
    plan = {
        "task_request_cap": 15,
        "retries": 0,
        "free_tier_only": True,
        "reference_sha256": hashlib.sha256(reference.read_bytes()).hexdigest(),
        "requests": [
            {
                "slot": n,
                "image": str(image.relative_to(tmp_path)),
                "image_sha256": hashlib.sha256(b"image").hexdigest(),
                "max_requests": 1,
            }
            for n in range(1, 16)
        ],
    }
    plan_path = evidence / "request-plan.json"
    plan_path.write_text(json.dumps(plan))
    approval_path = evidence / "reference-approval.json"
    approval = {
        "accepted_by": "Anton",
        "status": "confirmed",
        "reference_sha256": plan["reference_sha256"],
        "plan_sha256": hashlib.sha256(plan_path.read_bytes()).hexdigest(),
    }
    approval_path.write_text(json.dumps(approval))
    assert validate_inputs(tmp_path, plan_path, approval_path, 1)[1] == image
    (evidence / "ledger.json").write_text(
        json.dumps({"slots": [{"slot": n} for n in range(1, 16)]})
    )
    with pytest.raises(ValueError, match="exhausted in the published ledger"):
        validate_inputs(tmp_path, plan_path, approval_path, 1)
    reference.write_text("edited after approval")
    with pytest.raises(ValueError, match="confirmation"):
        validate_inputs(tmp_path, plan_path, approval_path, 1)
