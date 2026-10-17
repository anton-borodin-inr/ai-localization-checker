# Check one screenshot with Gemini

Issue #3 adds a provider-agnostic check: one PNG goes in, and the result is
either validated findings (`checked`) or `not_checked` with a reason. No prompt
tuning, tiling, metrics or matching yet.

## Interface

- `l10n_checker.vision` holds the draft v0 finding schema (`SCHEMA_VERSION =
  "v0-draft"`, finalized in Stage 1), `CheckResult`, the per-run request cap and
  the run recorder. It does not import any provider SDK.
- `l10n_checker.gemini` is the only module that imports `google.genai`.
- A finding has `defect_type` (`truncated_text`, `overlap`, `untranslated`,
  `other`), `text_seen`, `region` on a 3×3 grid (`top-left` … `bottom-right`,
  `center`) and `confidence` in 0..1.
- The model response is requested as structured output (JSON with the schema)
  and validated again locally.
- Model and request settings follow D-017: `gemini-3.6-flash`, temperature 0,
  `media_resolution` `MEDIA_RESOLUTION_HIGH`, all recorded in `run.json`.

`checked` with an empty list is the only way to say "no defects". A timeout, an
API error (including HTTP 429), a blocked or empty response, an incomplete
response (`finish_reason` other than `STOP`), invalid JSON, a response that does
not match the schema, or a request refused by the cap gives `not_checked` with
the reason and no findings (D-013).

## Request cap

`--max-requests` (default 1) caps the requests of one run. A single retry after
HTTP 429 counts as a request, so it happens only with `--max-requests 2` or more.
The SDK's own retries are disabled. The task budget (at most 10 live requests on
the free tier) is tracked by hand: every request shows up in
`data/runs/*/run.json` as `requests_sent`.

## Run record

Every run writes `data/runs/<run_id>/` (`run_id` is `YYYYMMDDTHHMMSSZ-<hex>`):

- `run.json`: provider, requested model id and the `model_version` returned by
  the API, SDK version, schema version, generation settings, image path, sha256
  and size, cap, attempts with outcome and latency, token usage;
- `prompt.txt`: the exact prompt;
- `response_raw.json`: the raw API response without HTTP headers (only when one
  was received);
- `result.json`: the `CheckResult`.

The API key is never written: the provider does not expose it, and every written
file and every error message passes through redaction as a second guard.

## Live call (Anton)

The key comes from `GEMINI_API_KEY` in `.env` (gitignored; see `.env.example`).
Free tier only: Google may use free-tier inputs to improve its products, which
is acceptable for screenshots of an open-source game.

```bash
uv run --env-file .env l10n-check --image data/issue-2/main-menu__en__2400x1080__original__1271.png --max-requests 2
```

`--timeout` (default 180 s) is also sent to the server as `X-Server-Timeout`;
a server-side `504 DEADLINE_EXCEEDED` is reported as `timeout`. At 60 s the
first live call on the 2400×1080 main menu hit that deadline.

Expected output: the run folder, then `checked: N finding(s)` (exit code 0) or
`not_checked: <reason>` (exit code 2). Exit code 1 means nothing was sent (no
key, bad image or runs folder outside `data/`).

Check that the key is not in the record:

```bash
uv run --env-file .env python -c "import os,pathlib,sys; k=os.environ['GEMINI_API_KEY']; hits=[p for p in pathlib.Path(sys.argv[1]).rglob('*') if p.is_file() and k in p.read_text()]; print('key found in', hits) if hits else print('key not found')" data/runs/<run_id>
```

If a model does not answer at all, `scripts/gemini_probe.py list` checks the key
and the model list without generating, and `scripts/gemini_probe.py text
[model]` sends one text-only request (it counts toward the budget).

## Verify offline

```bash
uv run pytest
```

Tests use a fake provider or a fake Gemini client; they make no network calls.
