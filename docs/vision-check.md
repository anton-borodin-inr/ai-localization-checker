# Check one screenshot with DeepSeek

`l10n-check` sends one PNG to the vision model and returns either validated
findings (`checked`) or `not_checked` with a reason. Response readability is
validated before findings can enter the result (D-013, D-031).

## Interface

- `l10n_checker.vision` holds response schema v1 (`SCHEMA_VERSION = "v1"`),
  the detector prompt (`PROMPT_VERSION = "v1"`), `CheckResult`,
  the per-run request cap and the run recorder. It does not talk to any API.
- `l10n_checker.deepseek` is the only module that talks to the DeepSeek API
  (D-034). It uses httpx.
- A finding has `defect_type` (`truncated_text`, `overlap`, `untranslated`,
  `other`), `text_seen`, `region` on a 3×3 grid (`top-left` … `bottom-right`,
  `center`) and `confidence` in 0..1 (D-018).

## Labeling and readability

Prompt v1 takes its defect rules from [labeling.md](labeling.md), without
screen-specific examples: scroll clipping is not a defect when scrolling
reveals the full content; an ellipsis is a defect only when the full text is
not visible elsewhere on the same screenshot; a raw key is `untranslated` and
a broken placeholder is `other`; region uses the centre of the text's bounding
box. The prompt also explains that readability concerns text inside the visible
viewport, not hidden scroll content or icons. Scroll clipping alone does not
make the visible text unreadable.

Every response requires all four fields, including an explicit null when no
readability reason is supplied:

```json
{
  "readability": "readable",
  "unreadable_regions": [],
  "readability_reason": null,
  "findings": []
}
```

| Readability | Required regions | Result |
|---|---|---|
| `readable` | empty list | `checked` with the findings |
| `partial` | at least one valid 3×3 cell | `not_checked`, no result findings |
| `unreadable` | empty list or valid 3×3 cells | `not_checked`, no result findings |

`readability_reason` is a short string or null. Wrong types, unknown values,
missing or extra fields, and inconsistent readability/regions are rejected as
`invalid_response`, without coercion or repair. The finding objects retain
their D-018 fields and validation.

For a valid `partial` or `unreadable` response, the reason is
`unreadable_text: <readability>, <JSON region list>, <reason or null>`.
The complete response, including any partial findings, remains in
`response_raw.json` as diagnostic evidence. Those findings never enter
`CheckResult.findings` or `result.json` findings. An empty list on an unreadable
screen never means "no defects".

## Request settings (D-034)

`POST https://api.deepseek.com/chat/completions` with model `deepseek-flash`,
non-thinking mode (`thinking: disabled`), temperature 0, `max_tokens` 4096,
`response_format` `json_object`, no streaming. The PNG is sent unchanged as a
base64 data URL with image `detail: original`. The timeout is 120 s
(`--timeout`). httpx makes no retries, follows no redirects and ignores proxy
and `.netrc` settings from the environment (`trust_env` off).

JSON object mode guarantees JSON but does not enforce a schema. The detector
prompt is therefore sent unchanged, followed by a format wrapper
(`deepseek-json-object-v2`) that appends the `ModelOutput` JSON Schema. A change
to the wrapper text or appended schema bumps `WRAPPER_VERSION`; a change to the prompt bumps
`PROMPT_VERSION`.

## When a screen is not checked

`checked` with an empty list is the only way to say "no defects". These give
`not_checked` with the reason and no findings (D-013):

| Situation | Reason |
|---|---|
| httpx timeout | `timeout` |
| HTTP 429 | `rate_limited` |
| any other HTTP status, connection error, or a body that is not a JSON object | `api_error` |
| no choices, or empty message content | `empty_response` |
| `finish_reason` other than `stop` (for example `length`) | `incomplete_response` |
| content that is not valid JSON, has extra or missing fields, or breaks the schema | `invalid_response` |
| validated `partial` or `unreadable` text | `unreadable_text: <readability>, <regions>, <reason>` |
| the per-run request cap refuses the request | `request_cap_reached` |

The response is never repaired, stripped of Markdown or trimmed to pass
validation.

## Request cap

`--max-requests` (default 1) caps the requests of one run. A single retry after
HTTP 429 counts as a request, so it happens only with `--max-requests 2` or more.
The task budget in requests and USD (D-035) is tracked across runs: every
request shows up in `data/runs/*/run.json` as `requests_sent`.

## Run record

Every run writes `data/runs/<run_id>/` (`run_id` is `YYYYMMDDTHHMMSSZ-<hex>`):

- `run.json`: provider, requested model and the model name the API returns
  (`model_version`; the API returns only the alias, no immutable revision),
  `system_fingerprint`, client version, schema, prompt and wrapper versions with
  the sha256 of the prompt and of the text sent, all request settings, image
  path, sha256, size in bytes and pixels, the cap and `requests_sent`, attempts
  with outcome and latency, token usage (prompt, completion, cache hit and miss)
  and `estimated_cost`; validated `readability`, `unreadable_regions` and
  `readability_reason` (all null if no response validated);
- `prompt.txt`: the detector prompt;
- `prompt_sent.txt`: the exact text sent (prompt plus wrapper);
- `response_raw.json`: the raw API response, or the HTTP status and body of an
  error response (only when one was received);
- `result.json`: the `CheckResult`.

`estimated_cost` is computed from the returned usage and the tariff snapshot in
`deepseek.py` (`TARIFF`: source URL, date, peak rates and the off-peak
multiplier). It gives `peak_usd` (conservative) and `off_peak_usd`. It is an
estimate, not a billing receipt; update the snapshot when the published tariff
changes.

The API key is never written: it is only in the request header, and every
written file and error message also passes through redaction.

## Live call

The key comes from `DEEPSEEK_API_KEY` in `.env` (gitignored; see
`.env.example`). The account uses a small prepaid balance, which is the hard
spending ceiling.

```bash
uv run --env-file .env l10n-check --image docs/evidence/8/final/tech-picker__de__2400x1080__injected__1271002.png --max-requests 1
```

Expected output: the run folder, then `checked: N finding(s)` (exit code 0) or
`not_checked: <reason>` (exit code 2). Exit code 1 means nothing was sent (no
key, bad image or runs folder outside `data/`).

The issue #32 confirmation run (three slice screenshots, one request each) is in
[evidence/32/report.md](evidence/32/report.md).
The paired prompt/schema v1 confirmation is in
[evidence/35/report.md](evidence/35/report.md), with a frozen prompt and matching
image hashes. Three screenshots support observations only, not aggregate
quality claims.

## Verify offline

```bash
uv run pytest
```

Tests use a fake provider or a fake DeepSeek server (`httpx.MockTransport`);
they make no network calls.

## History

Issues #3 and #10 used Gemini (D-017, superseded by D-034). Those run records
and evidence stay unchanged under `docs/evidence/` and on the archive branch
`feat/10-small-text-experiment`.
