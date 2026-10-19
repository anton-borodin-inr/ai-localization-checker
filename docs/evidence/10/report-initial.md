# Issue 10 Report: small text, resolution and tiling

**Comparison incomplete because 9 of 15 requests returned HTTP 503 UNAVAILABLE.** The budget is exhausted: **15 / 15 requests**, no retries or probes. Six responses are valid. Failed requests remain `not_checked`; their coverage and token usage are unavailable. Independent PR review and Anton's final conclusions are pending.

## What changed

- Built a candidate reference from the exact source commits for builds 1271001 and 1271002. Verified APK hashes and both packaged translation files against source bytes, then verified screenshot hashes. Anton confirmed the reference, regions and comparison examples before the first live call; its hash was frozen separately from detector output.
- Added provider-independent, pixel-preserving PNG crops with source/rectangle/hash provenance. **Added Pillow to decode PNGs and write exact pixel crops.** Original images stay untouched; no resize or upscaling.
- Added the isolated `l10n-small-text` experiment and `issue-10-reading-v1` response: ordinary `readings` plus unchanged draft-v0 findings. The production finding model, prompt and HIGH default remain unchanged. `GeminiProvider.media_resolution` from #11 is reused; ULTRA_HIGH goes on the image part and its effective value/scope are recorded from the request objects.
- Added fifteen persistent single-request slots, exclusive locking, pre-send reservations and refusal to reuse failed/interrupted slots. The published ledger also prevents a fresh checkout from restarting this issue's budget.
- Published normalized run copies, an aggregate, result review and verification receipts. Original local records remain under `data/runs/`. Updated D-028 live-call guidance in `docs/vision-check.md`.

The fixed protocol and reproduction commands are in [small-text-experiment.md](../../small-text-experiment.md). Inputs: [reference](reference-candidate.json), [approval](reference-approval.json), [request plan](request-plan.json). The candidate file keeps its historical pre-approval status; the separate hash-bound approval is authoritative.

## Results

The denominator is the approved set of fully visible translation units plus visible horizontal prefixes: German clean 16, English clean 20, German injected 18. Case and accents are preserved. Exact/fuzzy rules and confirmed examples were fixed before calls. Ordinary coverage is not defect recall. Unique text is evaluated independently of region; a research button cannot substitute for a distinct tree label (D-026).

| Input | Option | Status | Exact | Fuzzy | Invented strings | Image tokens | Latency (s) |
|---|---|---|---:|---:|---|---:|---:|
| German clean 1271001 | HIGH | checked | 16/16 (100%) | 16/16 (100%) | 0 | 1078 | 17.785 |
| German clean 1271001 | ULTRA_HIGH | checked | 16/16 (100%) | 16/16 (100%) | 0 | 2170 | 16.959 |
| German clean 1271001 | 3 tiles, HIGH | not_checked | unavailable | unavailable | unavailable; partial responses: 0 | unavailable | 19.056 |
| English clean 1271001 | HIGH | not_checked | unavailable | unavailable | unavailable | unavailable | 7.355 |
| English clean 1271001 | ULTRA_HIGH | checked | 20/20 (100%) | 20/20 (100%) | 0 | 2170 | 12.138 |
| English clean 1271001 | 3 tiles, HIGH | not_checked | unavailable | unavailable | unavailable; partial responses: 0 | unavailable | 18.808 |
| German injected 1271002 | HIGH | not_checked | unavailable | unavailable | unavailable | unavailable | 30.537 |
| German injected 1271002 | ULTRA_HIGH | not_checked | unavailable | unavailable | unavailable | unavailable | 13.126 |
| German injected 1271002 | 3 tiles, HIGH | not_checked | unavailable | unavailable | unavailable; partial responses: 0 | unavailable | 20.180 |

Latency is the sum of recorded request-attempt latencies, including failed requests; it excludes deliberate pauses between calls. Image tokens come only from the API's IMAGE breakdown. Successful HIGH originals used 1078 tokens; successful left crops used 1080; successful ULTRA_HIGH originals used 2170. The known image-token sum is 8658 across six successful calls; usage for nine failed calls is unknown, so 8658 is not an all-call total.

**Clipped diagnostics:** German clean HIGH and ULTRA_HIGH each transcribed Schrift (1/1), but omitted the four vertically clipped description components (0/4). Combined diagnostic coverage is 1/5 exact and fuzzy for each. Those bottom-line fragments were explicitly excluded from primary coverage before calls, not removed after seeing results. English ULTRA_HIGH transcribed all seven fully visible description units, including the long Temple of Artemis line. Therefore 16/16 does not mean that every partially clipped German character was read.

**Partial tiles:** Each three-tile variant has one successful left tile and two 503 failures. Each successful left tile reads four primary units exactly: Agriculture, Animal Husbandry, Archery and Mining (German equivalents on German images). These are partial observations, not 25%, 20% or 22% whole-screen model scores. All three aggregate tile variants remain `not_checked` and have unavailable complete coverage and total image-token usage.

**Invented strings:** Visual review of all 95 returned readings in the six successful responses found 0 invented strings, 0 reading errors and 0 hidden-text completions. Ordinary numeric counters and omitted/represented icons were reviewed separately; icons and standalone counters do not increase primary text coverage. There are no model readings to assess from the nine failed calls. The review is by the coding agent against the pre-call reference and originals; it does not create or alter human defect labels. See [result-review.json](result-review.json) and the per-reading audit in [run-summary.json](run-summary.json).

## Every finding and its region

There is exactly one finding across the six valid responses. The remaining five valid responses have empty findings. API failures are not empty checked results.

| Run | Finding | Text | Region check |
|---|---|---|---|
| 20261019T173557Z-167f1f | truncated_text, confidence 0.95 | Bergbau und Erzgew... | **Local region incorrect:** returned bottom; visible text centre ≈(890,701) lies in bottom-right of the 1320×920 left crop. The original reference region is center. Mapping the returned coarse cell gives left/center/bottom-left/bottom, so a unique original region cannot be inferred. |

The text identifies the existing human Mining label from issue 8; no new label was derived from this result. The original screenshot shows the full injected name nowhere else, as required by D-023. The title centre is just right of the crop's x=880 column boundary, illustrating why mapping the centre of a coarse model cell would invent precision. This finding is diagnostic evidence from an incomplete tile variant, not a successful whole-screen detection or an estimate of recall. D-026 supersedes issue 10's historical D-009 matching-weight reference; no matching weights were changed.

## How it was verified

- `uv sync`: successful; google-genai stayed at 2.31.0. Pillow is the only added dependency.
- `UV_CACHE_DIR=/private/tmp/issue10-uv-cache uv run --no-sync pytest`: **204 passed, 1 skipped, 1 warning** after the last code change. The skipped device test requires `--run-device` and a prepared emulator; device tests were not run because capture/device code was not changed. The warning is the existing google-genai/Python 3.14 deprecated `_UnionGenericAlias` usage.
- `uv run --no-sync ruff check .`, `uv run --no-sync ruff format --check .` (with the same workspace cache): passed. `git diff --check`: passed. Executed commands, exit codes and normalized outputs are in [checks/](checks/commands.json).
- Offline tests cover actual crop pixels and source preservation, persistent budget across fifteen separate invocations including 429/timeouts, interrupted reservations, concurrent locks, stale reference hashes, exhausted published ledgers, experimental validation, ULTRA_HIGH request/record parity, confirmed comparison examples and overlap aggregation. Existing production tests still pass.
- Rebuilt the reference offline into `data/issue-10/reference-reproduction.json`: byte-identical to the approved candidate. All three original screenshot hashes remain unchanged. All nine crop images were compared pixel for pixel with their original rectangles. All fifteen prompts and response schemas have one respective hash; all attempts have request cap 1 and exactly one request. See [verification.json](verification.json).
- Live calls used only the project's commands under D-028 with its configured free-tier key loaded by `uv run --env-file`; the agent did not read, print or copy `.env`, environment values or the key. No hold-out input was accessed. No paid or Vertex fallback was implemented. Calls were sequential, with 20-second pauses in the remaining-slot batch. The real 503 results were preserved rather than retried.
- CLI invocations used `PYTHONPATH=src` for the existing Mac editable-hook issue in D-019. An initial sandbox cache-access failure was resolved with a writable workspace-specific UV cache. Neither was a provider request. Independent PR review: **pending**, not claimed as completed.

## Deviations from the task

The planned three options were executed within their exact allocations. The full quality comparison is unavailable because of nine 503 responses; no replacement requests, model changes or budget extensions were made. The only finding comes from partial tile evidence. An isolated experimental transcription response was necessary because production findings alone cannot measure ordinary-text readability; production schema finalization and prompt tuning remain outside this task. The prompt was fixed before the first call and unchanged across all fifteen runs.

## Decisions proposed

- **D-029:** add an explicit visible-text readability result; partial/unreadable maps to `not_checked`. Schema fields and mapping are proposed only, not implemented in production.
- **D-030:** provisionally retain D-014 capture resolution and the current HIGH default; do not integrate tiling from this evidence. The paired German clean case shows equal primary coverage at roughly twice the image tokens for ULTRA_HIGH, but this is not enough to rank the options across both languages or the injected control.
- **D-031:** keep build-pinned, human-confirmed transcription coverage separate from D-026 defect recall and classification; preserve clipped diagnostics and unavailable failed variants.

No Accepted decision was superseded. All three new entries have status Proposed; final acceptance and conclusions remain Anton's.

## Open questions for Anton

Accept or revise D-029–D-031 after independent review. Decide whether the unavailable comparisons merit a separate follow-up with a new explicit budget; issue 10 itself has no requests remaining. Review and merge are not performed by the author.

## API usage

**Free tier only. Total requests_sent: 15 / 15.** HIGH originals: 3; ULTRA_HIGH originals: 3; HIGH tiles: 9. Every run has `max_requests = 1`, `requests_sent = 1`, one attempt, and no retry. Six checked responses; nine `503 UNAVAILABLE` responses. Requested model: gemini-3.6-flash; successful API model_version values are recorded per run. Local original run folders are `data/runs/<run_id>/`; links below point to committed normalized copies.

| Slot | Run id | Input / option | requests_sent | Result | Image tokens | Latency (s) |
|---:|---|---|---:|---|---:|---:|
| 1 | [20261019T155009Z-c8f4d4](runs/20261019T155009Z-c8f4d4/run.json) | German clean 1271001 / HIGH | 1 | checked | 1078 | 17.785 |
| 2 | [20261019T155114Z-4069a3](runs/20261019T155114Z-4069a3/run.json) | English clean 1271001 / HIGH | 1 | not_checked: 503 | unavailable | 7.355 |
| 3 | [20261019T173042Z-7a7529](runs/20261019T173042Z-7a7529/run.json) | German injected 1271002 / HIGH | 1 | not_checked: 503 | unavailable | 30.537 |
| 4 | [20261019T173133Z-0a453a](runs/20261019T173133Z-0a453a/run.json) | German clean 1271001 / ULTRA_HIGH | 1 | checked | 2170 | 16.959 |
| 5 | [20261019T173210Z-e38a73](runs/20261019T173210Z-e38a73/run.json) | English clean 1271001 / ULTRA_HIGH | 1 | checked | 2170 | 12.138 |
| 6 | [20261019T173243Z-5f30b8](runs/20261019T173243Z-5f30b8/run.json) | German injected 1271002 / ULTRA_HIGH | 1 | not_checked: 503 | unavailable | 13.126 |
| 7 | [20261019T173316Z-fa3f49](runs/20261019T173316Z-fa3f49/run.json) | German clean 1271001 / 3 tiles, HIGH / tree-left | 1 | checked | 1080 | 11.192 |
| 8 | [20261019T173348Z-43d1be](runs/20261019T173348Z-43d1be/run.json) | German clean 1271001 / 3 tiles, HIGH / tree-right | 1 | not_checked: 503 | unavailable | 5.177 |
| 9 | [20261019T173414Z-276a84](runs/20261019T173414Z-276a84/run.json) | German clean 1271001 / 3 tiles, HIGH / description | 1 | not_checked: 503 | unavailable | 2.687 |
| 10 | [20261019T173437Z-64098c](runs/20261019T173437Z-64098c/run.json) | English clean 1271001 / 3 tiles, HIGH / tree-left | 1 | checked | 1080 | 8.851 |
| 11 | [20261019T173506Z-08aaf7](runs/20261019T173506Z-08aaf7/run.json) | English clean 1271001 / 3 tiles, HIGH / tree-right | 1 | not_checked: 503 | unavailable | 2.972 |
| 12 | [20261019T173530Z-fd16bc](runs/20261019T173530Z-fd16bc/run.json) | English clean 1271001 / 3 tiles, HIGH / description | 1 | not_checked: 503 | unavailable | 6.985 |
| 13 | [20261019T173557Z-167f1f](runs/20261019T173557Z-167f1f/run.json) | German injected 1271002 / 3 tiles, HIGH / tree-left | 1 | checked | 1080 | 9.193 |
| 14 | [20261019T173627Z-803dbd](runs/20261019T173627Z-803dbd/run.json) | German injected 1271002 / 3 tiles, HIGH / tree-right | 1 | not_checked: 503 | unavailable | 3.878 |
| 15 | [20261019T173651Z-398056](runs/20261019T173651Z-398056/run.json) | German injected 1271002 / 3 tiles, HIGH / description | 1 | not_checked: 503 | unavailable | 7.109 |
| **Total** | **15 runs** | **3 + 3 + 9** | **15** | **6 checked / 9 not_checked** | **all-call total unavailable** | |

[Ledger](ledger.json), [aggregate and per-reading audit](run-summary.json), [verification receipt](verification.json). Published copies normalize only the checkout prefix in paths; they do not imply commands were rerun. Local originals are preserved.

## Changed files

The list below covers every repository file in this task, including generated run artifacts and check logs. Work drafts and local runtime outputs are outside the Git diff.

<details>
<summary>All changed repository files</summary>

- `.gitignore`
- `docs/decisions.md`
- `docs/evidence/10/checks/commands.json`
- `docs/evidence/10/checks/diff-check.txt`
- `docs/evidence/10/checks/pytest.txt`
- `docs/evidence/10/checks/ruff-check.txt`
- `docs/evidence/10/checks/ruff-format.txt`
- `docs/evidence/10/ledger.json`
- `docs/evidence/10/reference-approval.json`
- `docs/evidence/10/reference-candidate.json`
- `docs/evidence/10/report.md`
- `docs/evidence/10/request-plan.json`
- `docs/evidence/10/result-review.json`
- `docs/evidence/10/run-summary.json`
- `docs/evidence/10/runs/20261019T155009Z-c8f4d4/experiment.json`
- `docs/evidence/10/runs/20261019T155009Z-c8f4d4/output.json`
- `docs/evidence/10/runs/20261019T155009Z-c8f4d4/prompt.txt`
- `docs/evidence/10/runs/20261019T155009Z-c8f4d4/response_raw.json`
- `docs/evidence/10/runs/20261019T155009Z-c8f4d4/result.json`
- `docs/evidence/10/runs/20261019T155009Z-c8f4d4/run.json`
- `docs/evidence/10/runs/20261019T155114Z-4069a3/experiment.json`
- `docs/evidence/10/runs/20261019T155114Z-4069a3/prompt.txt`
- `docs/evidence/10/runs/20261019T155114Z-4069a3/result.json`
- `docs/evidence/10/runs/20261019T155114Z-4069a3/run.json`
- `docs/evidence/10/runs/20261019T173042Z-7a7529/experiment.json`
- `docs/evidence/10/runs/20261019T173042Z-7a7529/prompt.txt`
- `docs/evidence/10/runs/20261019T173042Z-7a7529/result.json`
- `docs/evidence/10/runs/20261019T173042Z-7a7529/run.json`
- `docs/evidence/10/runs/20261019T173133Z-0a453a/experiment.json`
- `docs/evidence/10/runs/20261019T173133Z-0a453a/output.json`
- `docs/evidence/10/runs/20261019T173133Z-0a453a/prompt.txt`
- `docs/evidence/10/runs/20261019T173133Z-0a453a/response_raw.json`
- `docs/evidence/10/runs/20261019T173133Z-0a453a/result.json`
- `docs/evidence/10/runs/20261019T173133Z-0a453a/run.json`
- `docs/evidence/10/runs/20261019T173210Z-e38a73/experiment.json`
- `docs/evidence/10/runs/20261019T173210Z-e38a73/output.json`
- `docs/evidence/10/runs/20261019T173210Z-e38a73/prompt.txt`
- `docs/evidence/10/runs/20261019T173210Z-e38a73/response_raw.json`
- `docs/evidence/10/runs/20261019T173210Z-e38a73/result.json`
- `docs/evidence/10/runs/20261019T173210Z-e38a73/run.json`
- `docs/evidence/10/runs/20261019T173243Z-5f30b8/experiment.json`
- `docs/evidence/10/runs/20261019T173243Z-5f30b8/prompt.txt`
- `docs/evidence/10/runs/20261019T173243Z-5f30b8/result.json`
- `docs/evidence/10/runs/20261019T173243Z-5f30b8/run.json`
- `docs/evidence/10/runs/20261019T173316Z-fa3f49/experiment.json`
- `docs/evidence/10/runs/20261019T173316Z-fa3f49/output.json`
- `docs/evidence/10/runs/20261019T173316Z-fa3f49/prompt.txt`
- `docs/evidence/10/runs/20261019T173316Z-fa3f49/response_raw.json`
- `docs/evidence/10/runs/20261019T173316Z-fa3f49/result.json`
- `docs/evidence/10/runs/20261019T173316Z-fa3f49/run.json`
- `docs/evidence/10/runs/20261019T173348Z-43d1be/experiment.json`
- `docs/evidence/10/runs/20261019T173348Z-43d1be/prompt.txt`
- `docs/evidence/10/runs/20261019T173348Z-43d1be/result.json`
- `docs/evidence/10/runs/20261019T173348Z-43d1be/run.json`
- `docs/evidence/10/runs/20261019T173414Z-276a84/experiment.json`
- `docs/evidence/10/runs/20261019T173414Z-276a84/prompt.txt`
- `docs/evidence/10/runs/20261019T173414Z-276a84/result.json`
- `docs/evidence/10/runs/20261019T173414Z-276a84/run.json`
- `docs/evidence/10/runs/20261019T173437Z-64098c/experiment.json`
- `docs/evidence/10/runs/20261019T173437Z-64098c/output.json`
- `docs/evidence/10/runs/20261019T173437Z-64098c/prompt.txt`
- `docs/evidence/10/runs/20261019T173437Z-64098c/response_raw.json`
- `docs/evidence/10/runs/20261019T173437Z-64098c/result.json`
- `docs/evidence/10/runs/20261019T173437Z-64098c/run.json`
- `docs/evidence/10/runs/20261019T173506Z-08aaf7/experiment.json`
- `docs/evidence/10/runs/20261019T173506Z-08aaf7/prompt.txt`
- `docs/evidence/10/runs/20261019T173506Z-08aaf7/result.json`
- `docs/evidence/10/runs/20261019T173506Z-08aaf7/run.json`
- `docs/evidence/10/runs/20261019T173530Z-fd16bc/experiment.json`
- `docs/evidence/10/runs/20261019T173530Z-fd16bc/prompt.txt`
- `docs/evidence/10/runs/20261019T173530Z-fd16bc/result.json`
- `docs/evidence/10/runs/20261019T173530Z-fd16bc/run.json`
- `docs/evidence/10/runs/20261019T173557Z-167f1f/experiment.json`
- `docs/evidence/10/runs/20261019T173557Z-167f1f/output.json`
- `docs/evidence/10/runs/20261019T173557Z-167f1f/prompt.txt`
- `docs/evidence/10/runs/20261019T173557Z-167f1f/response_raw.json`
- `docs/evidence/10/runs/20261019T173557Z-167f1f/result.json`
- `docs/evidence/10/runs/20261019T173557Z-167f1f/run.json`
- `docs/evidence/10/runs/20261019T173627Z-803dbd/experiment.json`
- `docs/evidence/10/runs/20261019T173627Z-803dbd/prompt.txt`
- `docs/evidence/10/runs/20261019T173627Z-803dbd/result.json`
- `docs/evidence/10/runs/20261019T173627Z-803dbd/run.json`
- `docs/evidence/10/runs/20261019T173651Z-398056/experiment.json`
- `docs/evidence/10/runs/20261019T173651Z-398056/prompt.txt`
- `docs/evidence/10/runs/20261019T173651Z-398056/result.json`
- `docs/evidence/10/runs/20261019T173651Z-398056/run.json`
- `docs/evidence/10/verification.json`
- `docs/small-text-experiment.md`
- `docs/vision-check.md`
- `pyproject.toml`
- `scripts/prepare_small_text_reference.py`
- `scripts/summarize_small_text.py`
- `src/l10n_checker/gemini.py`
- `src/l10n_checker/reading_metrics.py`
- `src/l10n_checker/small_text.py`
- `src/l10n_checker/tiling.py`
- `src/l10n_checker/vision.py`
- `tests/golden/small_text_cases.json`
- `tests/test_reading_metrics.py`
- `tests/test_small_text.py`
- `tests/test_tiling.py`
- `uv.lock`

</details>
