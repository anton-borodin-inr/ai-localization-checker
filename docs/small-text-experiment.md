# Small-text resolution experiment (issue 10)

This is an experiment on the issue 8 technology picker, not a production
detector or an implementation of issue 13's defect metrics. It measures whether
visible translation units are transcribed, while also collecting draft-v0
findings. Ordinary readings are not defects. A valid structured response is
`checked`; it does not establish that every visible word was readable. An
unreadability status is proposed separately, not finalized in code here.

## Frozen inputs

`evidence/10/reference-candidate.json` is assembled from English and German
translation files at the exact build commits in issue 8's pair manifest.
`scripts/prepare_small_text_reference.py` verifies the APK hashes, each packaged
translation against source bytes, the versionCode, and screenshot hashes.
Source keys, values, line numbers, substitutions and visible spans are recorded.
English empty values fall back to source keys. This narrow assembler is not a
general Unciv translation engine. It imports no provider and uses no model output.

Anton confirmed the strings, primary/diagnostic split, regions and comparison
examples in chat before the first call. `reference-approval.json` binds this
confirmation to hashes of the reference and request plan. The reference retains
its historical candidate status; the separate approval is authoritative.
The existing issue 8 human defect labels are untouched.

Primary denominators: German clean **16**, English clean **20**, German injected
**18**. Fully visible units and visible horizontal prefixes are primary;
vertical viewport clips are diagnostic. English Writing is outside the frame;
German Schrift is a top-edge diagnostic. German clean's last description line
is vertically clipped. German injected has no Close/Research buttons. Standalone
numeric counters and icons do not inflate text coverage. Only visible Production
text is scored, not its hidden continuation.

## Options and budget

| Option | Screens | Calls per screen | Total |
|---|---:|---:|---:|
| Original, HIGH | 3 | 1 | 3 |
| Original, ULTRA_HIGH | 3 | 1 | 3 |
| Three crops, HIGH | 3 | 3 | 9 |
| Total | | | 15 |

The requested model remains D-017's `gemini-3.6-flash`, temperature 0, timeout
180 seconds. No SDK retries, manual retries or probes. A failed request consumes
its slot. All live commands require `--max-requests 1 --free-tier-key`; the latter
acknowledges the caller's free-tier constraint, not an API verification of billing.
The same free-tier key configured for the project is used; there is no paid or
Vertex fallback.

`GeminiProvider.media_resolution` remains the parameter from issue 11. HIGH is
the existing global setting. The SDK has ULTRA_HIGH on `PartMediaResolutionLevel`:
it is sent on the image part with no global override, and the effective value,
scope and API version are recorded from the request objects. This follows
[Google's per-part resolution documentation](https://ai.google.dev/gemini-api/docs/generate-content/media-resolution).
No SDK upgrade or raw HTTP workaround is needed.

Each call has its own recorded run id. `data/runs/issue-10-ledger.json` reserves
a slot durably before sending. Exclusive locking prevents concurrent runs. A
failed/interrupted reservation is never reusable, and changing the approved
plan does not reset the ledger. A stale lock requires investigation, not removal
by the runner. There are at most 15 reservations for the entire task, not per
process. Successful records contain exact `requests_sent`; interrupted records
retain an unknown actual count and a conservative reservation of one.
The published ledger also blocks fresh checkouts from restarting the spent
budget. This completed issue cannot be rerun by creating an empty `data/` folder.

```bash
uv run --env-file .env l10n-small-text --slot 1 --max-requests 1 --free-tier-key
```

Slots 1–15 are fully enumerated in `evidence/10/request-plan.json`. This command
refuses a previously used slot. Do not run this example again after the task has
spent its budget. On this Mac, the existing hidden editable-hook issue (D-019)
requires `PYTHONPATH=src` for CLI invocations; pytest already has its source path.

## Provider-independent crops

`l10n_checker.tiling` imports Pillow, not a provider SDK. Pillow is the one added
dependency: it decodes PNGs and writes exact pixel crops. There is no resizing,
upscaling, drawing or mutation of the original image. Tests compare crop pixels
and source bytes; preparation records original and crop hashes.

| Crop | Original pixel rectangle, right/bottom exclusive |
|---|---|
| tree-left | (0, 0, 1320, 920) |
| tree-right | (1080, 0, 2400, 920) |
| description | (0, 900, 2400, 1080) |

The bottom panel keeps its full width to avoid splitting sentences. Its wide
aspect ratio is an experimental limitation; no improvement is assumed. A local
3×3 cell may intersect several original cells: mapping retains all candidates
instead of inventing a precise text position. Crop-edge fragments are not new
localization defects. Crop context can affect findings, so their results are
diagnostic and do not establish detector superiority.

## Output and comparison

The isolated `issue-10-reading-v1` response adds `readings` (`text_seen`, local
`region`) alongside the existing findings. Every option uses the same fixed
prompt and response schema. The reference is never sent to the model. The
production `ModelOutput`, finding fields, prompt and defaults are unchanged.
The experiment saves validated readings in `output.json` in each run folder.

Exact comparison normalizes NFC and whitespace, excluding icons/bullets but
preserving case, accents and punctuation. Fuzzy comparison also treats Unicode
ellipsis as three dots, uses SequenceMatcher (autojunk off) at 0.90, and compares
spans of 0.8–1.25 reference length. Units shorter than eight characters require
exact text. Anton-confirmed examples are in `tests/golden/small_text_cases.json`.

Each reference unit counts once even if multiple tiles repeat it. A longer
reference unit such as Research Archery does not cover the separate tree label
Archery merely by containing that word. As required by D-026, unique text is
compared independently of its predicted region; region errors are diagnosed
separately. Regions disambiguate identical reference units. A missing unit,
reading error, invented text and hidden continuation are distinct audit outcomes.
Unmatched text is not automatically declared a hallucination.

```bash
PYTHONPATH=src uv run python scripts/summarize_small_text.py
```

This offline command publishes normalized copies of run artifacts and an
aggregate under `docs/evidence/10/`. Local originals stay under `data/runs/`.
It checks ledger counts and settings against the plan. Summary tables give
coverage, image tokens (only when the API supplies an IMAGE breakdown), latency,
status, each run id and requests sent. Failed variants have unavailable coverage;
partial tile evidence remains explicitly separate. No zero-token estimate or
zero-defect result is substituted for failure. Classification of questionable
readings and findings is documented against the approved reference and original
screenshots in the Report; this does not create new defect labels.
