# Current amendment: overnight-oriented local calls

Anton subsequently asked to increase the timeout because final runs are intended
to execute overnight and speed is not a quality criterion. He explicitly
approved **14 local sends total**, including both German clean timeouts and
one final repeat of that input. New calls use **1800 s**; the already running
injected original retained its recorded 400 s. See `nightly-extension.json`.
The combined actual maximum is **41 = 27 Gemini + 14 local**. No other input is
retried and no fourth German clean attempt is allowed. All previous plans and
run records remain historical. The notes below describe earlier amendments.

# Local comparison execution notes

Anton approved `plan.md` and its separate hash-bound `approval.json` before the first local call. The initial allocation was 12 distinct inputs, timeout 180 s, no retries. After run `20261019T203555Z-2b7451` timed out, he requested 300–400 s and explicitly authorized 13 total local sends: retain that timeout, repeat the first input once, then run the remaining eleven inputs. `timeout-extension.json` records the amendment; calls made during that amendment used **400 s**. Gemini remains frozen at 27 sends. The then-approved combined maximum was **40**. These changes were approved before the repeat; neither failed sends nor their latencies disappear from the Report.

The initial plan/approval/ledger/summary/verification snapshots remain historical. The local source inputs, frozen prompt/schema, amended reference, metrics and server model/settings remain unchanged apart from the approved client timeout. Actual private/local source and crop files are reused by hash. The API receives a new one-message conversation for every request; no previous response or reference is sent.

Commands, with D-019's source path and a writable cache on this machine:

```bash
PYTHONPATH=src UV_CACHE_DIR=/private/tmp/issue10-uv-cache uv run --no-sync l10n-small-text-local --slot 1 --attempt 2 --max-requests 1
PYTHONPATH=src UV_CACHE_DIR=/private/tmp/issue10-uv-cache uv run --no-sync l10n-small-text-local --slot 2 --max-requests 1
PYTHONPATH=src uv run --no-sync python scripts/summarize_small_text_local.py
```

Slots 1–12 are enumerated in `request-plan.json`. Under the first extension only slot 1 could have attempt 2, with an initial completed timeout. The later overnight amendment above additionally authorizes slot 1 attempt 3. No other slot is repeated, no fourth attempt is allowed, and there is no automatic retry. Durable reservations are protected by the same task lock as the Gemini experiment. The published local ledger prevents reset in a fresh checkout. Used examples must not be rerun.

`LocalVisionProvider` uses standard-library urllib against the hardcoded `http://127.0.0.1:1234/v1/chat/completions`; proxies and redirects are disabled. It does not load an environment file or credentials. Payload: the original image as an inline PNG, unchanged experiment prompt, temperature 0, max_tokens 8192, stream false, and JSON schema copied from the original Gemini request. The same Pydantic model validates the result. No JSON repair, truncation cleanup, model fallback, resizing or prompt tuning. The machine's loaded model metadata is captured before the experiment; an alias/quantization does not establish a weight revision or equivalence of internal image processing. The longer local timeout is an explicit difference from Gemini's 180 s.

Ordinary coverage uses the confirmed amended reference (16/20/20). Reference text is not sent to Qwen. Selected comparison results use the first validated response per input, otherwise the last failure; all attempts remain in request/latency totals. Incomplete crop groups retain unavailable complete coverage and separately labeled partial evidence. Failed/unrun inputs are not clean results. Every validated reading/finding needs visual review before a hallucination or region conclusion is claimed.

## Initial timeout diagnostic

The request-specific server-log excerpt starts after the request body, excluding unrelated requests and inline image data. It shows prompt processing reached 100% about 13 s after the request. At 180 s the client disconnected and the server stopped generation. The server's cancelled prediction contains **69 repeated `Schluss` objects**, plus an unfinished JSON content string. The server logged finish_reason stop despite the client cancellation and incomplete content; this is not an HTTP response received/validated by the harness. The client run stays `not_checked`, with unavailable coverage, region, hallucination and usage metrics. The logged usage is server-side diagnostics only. This observation does not prove why repetition occurred or whether a different model/runtime/setup would avoid it.

Relevant official interface documentation, consulted before implementation:

- [LM Studio image-capable OpenAI-compatible endpoints](https://lmstudio.ai/docs/developer/openai-compat)
- [LM Studio structured JSON-schema output, including MLX](https://lmstudio.ai/docs/developer/openai-compat/structured-output)

The first `uv sync --offline` could not find hatchling in the selected cache. A network-enabled `uv sync` then succeeded, building only this project with its existing dependencies. An unused import caught by the initial Ruff run was removed before the first generation. Later checks are recorded separately with their actual results.
