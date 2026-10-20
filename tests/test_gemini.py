import ast
import json
import logging
import sys
from pathlib import Path

import httpx
import pytest
from google.genai import errors, types

from l10n_checker import cli
from l10n_checker.gemini import DEFAULT_MODEL, GeminiProvider, response_schema
from l10n_checker.vision import ProviderError, RequestBudget, run_check

KEY = "test-key-DO-NOT-LEAK"
SRC = Path(__file__).resolve().parents[1] / "src" / "l10n_checker"


def response(text='{"findings": []}', finish="STOP", block=None):
    return types.GenerateContentResponse(
        candidates=[
            types.Candidate(
                content=types.Content(role="model", parts=[types.Part(text=text)]),
                finish_reason=finish,
            )
        ]
        if finish
        else [],
        prompt_feedback=types.GenerateContentResponsePromptFeedback(block_reason=block)
        if block
        else None,
        model_version="gemini-3.6-flash-001",
        usage_metadata=types.GenerateContentResponseUsageMetadata(
            prompt_token_count=1300, candidates_token_count=12, total_token_count=1312
        ),
    )


def api_error(cls, code, status):
    # The key is planted in the error text to prove that it is redacted.
    body = {"error": {"code": code, "status": status, "message": f"bad key {KEY}"}}
    return cls(code, body)


FAILURES = {
    "timeout": httpx.ReadTimeout(f"timed out for {KEY}"),
    "rate_limited": api_error(errors.ClientError, 429, "RESOURCE_EXHAUSTED"),
    "server_error": api_error(errors.ServerError, 500, "INTERNAL"),
    "deadline": api_error(errors.ServerError, 504, "DEADLINE_EXCEEDED"),
    "forbidden": api_error(errors.ClientError, 403, "PERMISSION_DENIED"),
    "connect_error": httpx.ConnectError(f"cannot connect {KEY}"),
    "unexpected": RuntimeError(f"unexpected {KEY}"),
}
FAILURE_KINDS = {
    "timeout": "timeout",
    "rate_limited": "rate_limited",
    "server_error": "api_error",
    "deadline": "timeout",
    "forbidden": "api_error",
    "connect_error": "api_error",
    "unexpected": "api_error",
}
RESPONSES = {
    "empty_text": response(text=""),
    "blocked": response(finish=None, block="PROHIBITED_CONTENT"),
    "no_candidates": response(finish=None),
    "max_tokens": response(text='{"findings": [', finish="MAX_TOKENS"),
    "invalid_json": response(text="not json"),
}
RESPONSE_KINDS = {
    "empty_text": "empty_response",
    "blocked": "empty_response",
    "no_candidates": "empty_response",
    "max_tokens": "incomplete_response",
}


class FakeModels:
    def __init__(self, outcome):
        self.outcome = outcome
        self.requests = []

    def generate_content(self, **kwargs):
        self.requests.append(kwargs)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


class FakeClient:
    def __init__(self, outcome):
        self.models = FakeModels(outcome)


def provider(outcome):
    return GeminiProvider(KEY, client=FakeClient(outcome))


def test_request_uses_structured_output():
    p = provider(response())
    p.generate(b"png", "image/png", "prompt")
    request = p._client.models.requests[0]
    assert request["model"] == DEFAULT_MODEL
    assert request["config"].response_mime_type == "application/json"
    assert request["config"].response_schema == response_schema()
    assert request["config"].temperature == 0
    image, prompt = request["contents"]
    assert (
        image.inline_data.data == b"png" and image.inline_data.mime_type == "image/png"
    )
    assert prompt == "prompt"


def test_success_is_parsed():
    result = provider(response()).generate(b"png", "image/png", "p")
    assert result.text == '{"findings": []}'
    assert result.model_version == "gemini-3.6-flash-001"
    assert result.usage["total_token_count"] == 1312
    assert "sdk_http_response" not in result.raw


@pytest.mark.parametrize("name", list(FAILURES))
def test_exceptions_are_mapped(name):
    with pytest.raises(ProviderError) as info:
        provider(FAILURES[name]).generate(b"png", "image/png", "p")
    assert info.value.kind == FAILURE_KINDS[name]
    assert KEY not in str(info.value)


@pytest.mark.parametrize("name", list(RESPONSE_KINDS))
def test_unusable_responses_are_mapped(name):
    with pytest.raises(ProviderError) as info:
        provider(RESPONSES[name]).generate(b"png", "image/png", "p")
    assert info.value.kind == RESPONSE_KINDS[name]


def test_real_client_has_timeout_and_no_sdk_retries():
    http = GeminiProvider(KEY, timeout_s=30)._client._api_client._http_options
    assert http.timeout == 30_000
    assert http.retry_options.attempts == 1


def test_default_timeout_is_180_s():
    p = GeminiProvider(KEY)
    assert p._client._api_client._http_options.timeout == 180_000
    assert p.settings["timeout_s"] == 180


def test_only_the_adapter_imports_the_sdk():
    importers = set()
    for path in SRC.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            if any(n == "google" or n.startswith("google.") for n in names):
                importers.add(path.name)
    assert importers == {"gemini.py"}


@pytest.mark.parametrize("name", ["success", *FAILURES, *RESPONSES])
def test_key_never_leaks(name, screenshot, tmp_path, capsys, caplog, monkeypatch):
    caplog.set_level(logging.DEBUG)
    outcome = response() if name == "success" else {**FAILURES, **RESPONSES}[name]
    monkeypatch.setenv("GEMINI_API_KEY", KEY)
    monkeypatch.setattr(
        cli, "make_provider", lambda name, key, timeout: provider(outcome)
    )
    monkeypatch.setattr(cli, "output_directory", lambda path: path)
    runs = tmp_path / "runs"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "l10n-check",
            "--image",
            str(screenshot),
            "--runs-dir",
            str(runs),
            "--max-requests",
            "2",
            "--provider",
            "gemini",
        ],
    )
    monkeypatch.setattr("l10n_checker.vision.time.sleep", lambda s: None)
    code = cli.check_main()
    assert code == (0 if name == "success" else 2)

    files = [p for p in runs.rglob("*") if p.is_file()]
    assert files
    for path in files:
        assert KEY not in path.read_text(), path.name
    output = capsys.readouterr()
    assert KEY not in output.out + output.err
    assert KEY not in caplog.text
    # The exception text passed to the run is redacted too.
    result = json.loads(next(runs.rglob("result.json")).read_text())
    assert KEY not in (result["reason"] or "")


def test_run_check_redacts_secrets_in_written_files(screenshot, tmp_path):
    p = provider(response(text=f'{{"findings": [], "x": "{KEY}"}}'))
    result, run_dir = run_check(
        p, screenshot, tmp_path / "runs", RequestBudget(1), secrets=(KEY,)
    )
    assert result.status == "not_checked"
    for path in run_dir.iterdir():
        assert KEY not in path.read_text()


def test_request_body_is_accepted_by_the_api_schema(screenshot):
    """The real SDK serializes the request; the API rejects additionalProperties."""
    sent = []

    def handler(request):
        sent.append(json.loads(request.content))
        body = response().model_dump(mode="json", exclude_none=True, by_alias=True)
        return httpx.Response(200, json=body)

    p = GeminiProvider(KEY)
    p._client._api_client._httpx_client = httpx.Client(
        transport=httpx.MockTransport(handler)
    )
    p.generate(screenshot.read_bytes(), "image/png", "prompt")
    config = sent[0]["generationConfig"]
    schema = json.dumps(config.get("responseSchema") or config["responseJsonSchema"])
    for unsupported in ("additional", "$ref", "$defs"):
        assert unsupported not in schema.lower().replace("_", "")
    assert '"findings"' in schema and "bottom-right" in schema
    assert config["mediaResolution"] == "MEDIA_RESOLUTION_HIGH"


def test_media_resolution_is_recorded_in_settings():
    assert GeminiProvider(KEY).settings["media_resolution"] == "MEDIA_RESOLUTION_HIGH"


def test_default_recorded_settings_match_request_config():
    p = GeminiProvider(KEY)
    for name in (
        "temperature",
        "max_output_tokens",
        "response_mime_type",
        "response_schema",
    ):
        assert p.settings[name] == getattr(p._config, name)
    assert p.settings["media_resolution"] == p._config.media_resolution.value
    assert (
        p.settings["sdk_retry_attempts"]
        == p._http_options.retry_options.attempts
        == p._client._api_client._http_options.retry_options.attempts
    )
    assert isinstance(p.settings["temperature"], float)


@pytest.mark.parametrize(
    "media_resolution",
    [
        types.MediaResolution.MEDIA_RESOLUTION_LOW,
        types.MediaResolution.MEDIA_RESOLUTION_MEDIUM,
    ],
)
def test_recorded_media_resolution_follows_request_config(
    media_resolution, screenshot, tmp_path
):
    p = GeminiProvider(
        KEY, client=FakeClient(response()), media_resolution=media_resolution
    )
    result, run_dir = run_check(p, screenshot, tmp_path / "runs", RequestBudget(1))

    assert result.status == "checked"
    request = p._client.models.requests[0]
    assert request["config"].media_resolution == media_resolution
    recorded = json.loads((run_dir / "run.json").read_text())
    assert recorded["settings"]["media_resolution"] == media_resolution.value
