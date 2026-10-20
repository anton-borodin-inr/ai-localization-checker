# Issue 10 Report: small text, resolution and tiling

**Comparison incomplete: 27 sends produced 8 checked responses, 14 HTTP 503s and 5 HTTP 429s.** The authorized continuation recovered two responses. Total **requests_sent = 27 / 33**, including every failure. No eligible retries remain under the approved policy; six unused sends do not authorize retrying a 429 or a success. Independent PR review and Anton's final conclusions are pending.

**Reference correction:** the agent initially omitted two visible injected controls and briefly misclassified their returned text as invented during continuation review. Reinspection of the unchanged original and build 1271002 translations corrected that mistake. Anton confirmed both strings and denominator **18 → 20 after all calls**. The original reference and scores remain intact; amended scores are separate. No defect labels or thresholds changed.

## What changed

- Built visible-string references from exact source commits for builds 1271001/1271002. Verified APK hashes, packaged/source translation bytes and screenshot hashes. Anton confirmed the initial reference and comparison examples before the first call. The separately confirmed amendment adds `Schließen` (bottom-left) and `Bogenschießen erforschen` (bottom-right); `(0/24)` remains numeric diagnostics. The discrepancy was noticed during output review, but the correction uses original pixels and source entries, not model-derived ground truth.
- Added provider-independent exact PNG crops with original/rectangle/hash provenance. **Pillow is the added dependency, to decode PNGs and write pixel-preserving crops.** No resizing, upscaling or source mutation.
- Added an isolated readings+findings experiment with frozen `issue-10-reading-v1` prompt/schema. Production finding schema, prompt and HIGH defaults remain unchanged. Reused #11's `GeminiProvider.media_resolution`; ULTRA_HIGH is per image part with effective scope recorded from request objects.
- Added locked, durable pre-send reservations for the initial 15 slots and separately authorized conditional continuation. Each run uses `--max-requests 1`; SDK retries are disabled. A second new attempt requires the first new attempt to return HTTP 503. Initial successes are never repeated.
- Published all 27 normalized run records, both ledgers, original/amended comparisons, visual audits and verification receipts. Local originals remain under `data/runs/`. One branch and PR #29 cover the task.

Protocol/reproduction: [small-text-experiment.md](../../small-text-experiment.md). Initial inputs: [reference](reference-candidate.json), [approval](reference-approval.json), [plan](request-plan.json). Continuation: [authorization](continuation-approval.json), [per-option plan](continuation-request-plan.json). Correction: [amendment](reference-amendment-candidate.json), [post-call confirmation](reference-amendment-approval.json). Candidate status inside reference files is historical; separate hash-bound approvals are authoritative.

## Results

Primary denominators: German clean **16**, English clean **20**, German injected **20 amended / 18 original**. Fully visible units and horizontal visible prefixes are primary; vertical viewport clips remain diagnostic. Exact/fuzzy rules and examples were frozen before calls and unchanged. Coverage measures transcription, not defect recall. Unique text is compared independently of region; a research control cannot substitute for a distinct tree label (D-026).

For each original slot, the aggregate selects its **first validated response**, otherwise its last failure. Selection never uses the best score. Selected tokens/latency describe that response only; all-attempt requests/latency include every failure. Incomplete three-crop variants have unavailable complete metrics.

| Input | Option | Status | Exact | Fuzzy | Invented strings | Selected image tokens | Selected latency (s) | All requests | All-attempt latency (s) |
|---|---|---|---:|---:|---|---:|---:|---:|---:|
| German clean 1271001 | HIGH | checked | 16/16 (100%) | 16/16 (100%) | 0 | 1078 | 17.785 | 1 | 17.785 |
| German clean 1271001 | ULTRA_HIGH | checked | 16/16 (100%) | 16/16 (100%) | 0 | 2170 | 16.959 | 1 | 16.959 |
| German clean 1271001 | 3 tiles, HIGH | not_checked | unavailable | unavailable | unavailable; 0 in returned readings | unavailable | unavailable | 5 | 29.354 |
| English clean 1271001 | HIGH | not_checked | unavailable | unavailable | unavailable | unavailable | unavailable | 3 | 20.801 |
| English clean 1271001 | ULTRA_HIGH | checked | 20/20 (100%) | 20/20 (100%) | 0 | 2170 | 12.138 | 1 | 12.138 |
| English clean 1271001 | 3 tiles, HIGH | not_checked | unavailable | unavailable | unavailable; 0 in returned readings | unavailable | unavailable | 5 | 20.204 |
| German injected 1271002 | HIGH | not_checked | unavailable | unavailable | unavailable | unavailable | unavailable | 3 | 53.381 |
| German injected 1271002 | ULTRA_HIGH | checked | 20/20 (100%) | 20/20 (100%) | 0 | 2170 | 11.493 | 3 | 35.217 |
| German injected 1271002 | 3 tiles, HIGH | not_checked | unavailable | unavailable | unavailable; 0 in returned readings | unavailable | unavailable | 5 | 21.401 |

Injected ULTRA_HIGH has **20/20 amended** versus **18/18 original** coverage; both are retained in [combined-summary.json](combined-summary.json). The two added controls were correctly transcribed. [run-summary.json](run-summary.json) remains the unchanged initial 15-call snapshot; [report-initial.md](report-initial.md) preserves its initial Report byte for byte. The amended reference must not be described as wholly correct before calls.

**Clipped diagnostics:** German clean original HIGH and ULTRA_HIGH each read Schrift (1/1), but omit four vertically clipped description components (0/4): diagnostic coverage 1/5. The recovered description crop reads all four bottom-line components, while Schrift is outside that crop. The partial tiles therefore observe 4/5 diagnostic units. These components were excluded from primary scoring before calls and remain excluded. English and injected German ULTRA_HIGH read all seven fully visible description units. The hidden German Production continuation is not a reference string.

**Partial tiles:** German clean's successful left and recovered description crops observe nine primary units from the 16-unit whole-screen reference. Its right crop remains unavailable (503 then 429). English clean and injected German have only successful left crops, each observing four primary units. These are partial observations, not complete coverage or recall estimates. All three tile variants remain `not_checked`.

**Invented strings:** coding-agent visual review of all **130 readings in eight checked responses** found 0 invented strings, 0 reading errors and 0 hidden completions, including the two real controls omitted from the initial reference. Numeric counters/icons were reviewed separately and do not increase primary coverage. Failed calls have no readings to assess. [Initial review](result-review.json), [continuation review](continuation-result-review.json) and the combined per-reading audit preserve the evidence; they do not create human defect labels.

Image tokens come only from the API IMAGE breakdown: checked HIGH original 1078, each checked ULTRA_HIGH original 2170, each checked left crop 1080, recovered description crop 1098. The known successful-call sum is **11926**. Usage for 19 failed calls is unknown, so all-call token usage is unavailable. Latency sums recorded provider attempts, excluding deliberate pauses and local preparation.

## Every finding and its region

Two findings refer to different views of the same pre-existing human Mining label. The other six checked responses have empty findings. Failures are not empty checked results; these findings do not estimate population recall.

| Run | Finding | Text | Region check |
|---|---|---|---|
| 20261019T173557Z-167f1f | truncated_text, confidence 0.95 | Bergbau und Erzgew... | **Local region incorrect:** returned bottom; visible text centre ≈(890,701) is bottom-right in the 1320×920 left crop. Returned-cell mapping gives left/center/bottom-left/bottom, so no unique original region can be inferred. Expected original: center. Partial tile evidence only. |
| 20261019T175806Z-ac6b2d | truncated_text, confidence 0.95 | Bergbau und Erzgew... | **Correct:** full-image ULTRA_HIGH returns center, matching original pixels and the existing human label; no crop mapping. |

No new label was derived. The full injected Mining name is unavailable elsewhere on the screenshot (D-023). D-026 supersedes issue 10's historical D-009 matching-weight reference; no production matching weights or goldens changed. Coarse-cell mapping retains ambiguity instead of inventing exact positions.

## How it was verified

- Initial `uv sync` succeeded; continuation `uv sync --offline` registered the new command without new dependencies. google-genai stayed 2.31.0. Pillow is the task's only added dependency.
- After the final code change: `UV_CACHE_DIR=/private/tmp/issue10-uv-cache uv run --no-sync pytest`: **214 passed, 1 skipped, 1 warning**. The skipped device test needs `--run-device` and a prepared emulator; device tests were not run because capture/device code is unchanged. The warning is existing google-genai/Python 3.14 deprecated `_UnionGenericAlias` use.
- `uv run --no-sync ruff check .`, `uv run --no-sync ruff format --check .` with that cache, and `git diff --check`: passed. Real outputs/exit codes: [continuation checks](checks-continuation/commands.json), with unchanged [initial checks](checks/commands.json).
- Offline tests cover exact crop pixels/source preservation; task locking/durable reservations; 33-total cap with fake responses; duplicate/out-of-order/interrupted attempts; no second send after success, 429, timeout or 500; strict 503 eligibility; stale hashes; first-success selection independent of quality; hash-bound human reference amendments. Existing production tests pass.
- Rebuilt references offline from pinned sources/APKs. `--legacy-initial-reference` reproduces the original candidate byte for byte; the corrected default reproduces amendment rows by screenshot/unit id (row order differs). Packaged translations/build identifiers match. Original screenshot hashes are unchanged; all nine crop pixel buffers equal their source rectangles.
- Verified all **72 original public run files**, initial reference/approval/plan/ledger/summary/review/verification and initial Report preservation against the initial commit. Continuation image bytes, model, SDK, settings, prompt/schema match their parent requests. All 27 runs have one request, one attempt and cap 1. Every second new attempt follows a completed new 503. No pending/interrupted calls. [Continuation verification](continuation-verification.json), [initial verification](verification.json).
- Live calls used project commands under D-028, the configured free-tier key loaded with `uv run --env-file`, and `PYTHONPATH=src` for D-019. No agent read/print/copy of `.env`, environment values or key; no paid/Vertex/model fallback or hold-out input. Calls were sequential, with continuation waits of 45 s before conditional second attempts and 20 s between original slots.
- Independent PR review: **pending**; no self-approval or merge.

## Deviations from the task

Provider errors prevent the full comparison. Anton explicitly extended 15 → 33 before continuation; failures were never reclassified as unsent. Twelve new sends finished all attempts eligible under the conditional policy. The original reference-selection mistake was corrected after output review and Anton's post-call confirmation; both versions and scores are disclosed. Labels, comparison rules and model inputs were unchanged.

A separate transcription response is needed because production findings do not measure ordinary readability. Production schema finalization/prompt tuning remain out of scope. All 27 calls used the same prompt/schema.

## Decisions proposed

- **D-029:** explicit visible-text readability result; partial/unreadable → `not_checked`. Production mapping/fields are proposed only.
- **D-030:** provisionally retain D-014 capture and HIGH. German clean has equal primary coverage at roughly twice the image tokens for ULTRA_HIGH. ULTRA_HIGH recovers the injected control and a crop reads clipped diagnostics, but HIGH counterparts/complete tiles are unavailable. The evidence cannot rank all options across languages.
- **D-031:** separate build-pinned human-confirmed transcription coverage from D-026 defect recall; preserve clipped diagnostics, unavailable variants and explicitly versioned later corrections.

No Accepted decision was superseded. All three entries remain Proposed; final acceptance/conclusions belong to Anton.

## Open questions for Anton

Accept/revise D-029–D-031 after independent review. Continuation is finished under its approved stopping rules; further live comparison needs new authorization. Author has not approved or merged the PR.

## API usage

**Free tier only. Total requests_sent: 27 / 33 (15 initial + 12 new).** Initial allocation: HIGH 3, ULTRA_HIGH 3, tiles 9. Before continuation, additional ceilings were fixed at HIGH +4, ULTRA_HIGH +2, tiles +12; combined ceilings **7 + 5 + 21 = 33**. Actual totals: **HIGH 7, ULTRA_HIGH 5, tiles 15**. Each send has its own run id, cap 1, requests_sent 1, one attempt, no SDK retry.

| Phase | Requests | Checked | HTTP 503 | HTTP 429 |
|---|---:|---:|---:|---:|
| Initial | 15 | 6 | 9 | 0 |
| Continuation | 12 | 2 | 5 | 5 |
| **Total** | **27** | **8** | **14** | **5** |

429 messages name `generativelanguage.googleapis.com/generate_content_free_tier_requests`, `GenerateRequestsPerDayPerProjectPerModel-FreeTier`, limit **20**, model `gemini-3.6-flash`, with a roughly 13-hour retry delay. This establishes a server-reported daily quota error, not exactly which earlier 503s consumed Google's quota. One description call succeeded after the first 429; no probe/extra retry investigated this behavior. Each remaining eligible slot received its authorized first attempt; a 429 immediately stopped that slot.

Slots 2/3 used two new 503 attempts; slot 6 used 503 then success; slot 9 succeeded on its first new attempt. Slots 8/11/12/14/15 returned 429 on their first new attempt, so no second send. No eligible attempt remains despite six unused sends. Requested model and returned successful model_version are recorded per run.

| Slot | Phase | Run id | Input / option | requests_sent | Result | Image tokens | Latency (s) |
|---:|---|---|---|---:|---|---:|---:|
| 1 | initial | [20261019T155009Z-c8f4d4](runs/20261019T155009Z-c8f4d4/run.json) | German clean 1271001 / HIGH | 1 | checked | 1078 | 17.785 |
| 2 | initial | [20261019T155114Z-4069a3](runs/20261019T155114Z-4069a3/run.json) | English clean 1271001 / HIGH | 1 | not_checked: 503 | unavailable | 7.355 |
| 3 | initial | [20261019T173042Z-7a7529](runs/20261019T173042Z-7a7529/run.json) | German injected 1271002 / HIGH | 1 | not_checked: 503 | unavailable | 30.537 |
| 4 | initial | [20261019T173133Z-0a453a](runs/20261019T173133Z-0a453a/run.json) | German clean 1271001 / ULTRA_HIGH | 1 | checked | 2170 | 16.959 |
| 5 | initial | [20261019T173210Z-e38a73](runs/20261019T173210Z-e38a73/run.json) | English clean 1271001 / ULTRA_HIGH | 1 | checked | 2170 | 12.138 |
| 6 | initial | [20261019T173243Z-5f30b8](runs/20261019T173243Z-5f30b8/run.json) | German injected 1271002 / ULTRA_HIGH | 1 | not_checked: 503 | unavailable | 13.126 |
| 7 | initial | [20261019T173316Z-fa3f49](runs/20261019T173316Z-fa3f49/run.json) | German clean 1271001 / 3 tiles, HIGH / tree-left | 1 | checked | 1080 | 11.192 |
| 8 | initial | [20261019T173348Z-43d1be](runs/20261019T173348Z-43d1be/run.json) | German clean 1271001 / 3 tiles, HIGH / tree-right | 1 | not_checked: 503 | unavailable | 5.177 |
| 9 | initial | [20261019T173414Z-276a84](runs/20261019T173414Z-276a84/run.json) | German clean 1271001 / 3 tiles, HIGH / description | 1 | not_checked: 503 | unavailable | 2.687 |
| 10 | initial | [20261019T173437Z-64098c](runs/20261019T173437Z-64098c/run.json) | English clean 1271001 / 3 tiles, HIGH / tree-left | 1 | checked | 1080 | 8.851 |
| 11 | initial | [20261019T173506Z-08aaf7](runs/20261019T173506Z-08aaf7/run.json) | English clean 1271001 / 3 tiles, HIGH / tree-right | 1 | not_checked: 503 | unavailable | 2.972 |
| 12 | initial | [20261019T173530Z-fd16bc](runs/20261019T173530Z-fd16bc/run.json) | English clean 1271001 / 3 tiles, HIGH / description | 1 | not_checked: 503 | unavailable | 6.985 |
| 13 | initial | [20261019T173557Z-167f1f](runs/20261019T173557Z-167f1f/run.json) | German injected 1271002 / 3 tiles, HIGH / tree-left | 1 | checked | 1080 | 9.193 |
| 14 | initial | [20261019T173627Z-803dbd](runs/20261019T173627Z-803dbd/run.json) | German injected 1271002 / 3 tiles, HIGH / tree-right | 1 | not_checked: 503 | unavailable | 3.878 |
| 15 | initial | [20261019T173651Z-398056](runs/20261019T173651Z-398056/run.json) | German injected 1271002 / 3 tiles, HIGH / description | 1 | not_checked: 503 | unavailable | 7.109 |
| 2 | new 1 | [20261019T175423Z-8354cf](runs/20261019T175423Z-8354cf/run.json) | English clean 1271001 / HIGH | 1 | not_checked: 503 | unavailable | 7.993 |
| 2 | new 2 | [20261019T175516Z-23e620](runs/20261019T175516Z-23e620/run.json) | English clean 1271001 / HIGH | 1 | not_checked: 503 | unavailable | 5.453 |
| 3 | new 1 | [20261019T175542Z-9c1ca8](runs/20261019T175542Z-9c1ca8/run.json) | German injected 1271002 / HIGH | 1 | not_checked: 503 | unavailable | 10.807 |
| 3 | new 2 | [20261019T175638Z-acebf2](runs/20261019T175638Z-acebf2/run.json) | German injected 1271002 / HIGH | 1 | not_checked: 503 | unavailable | 12.037 |
| 6 | new 1 | [20261019T175710Z-34269b](runs/20261019T175710Z-34269b/run.json) | German injected 1271002 / ULTRA_HIGH | 1 | not_checked: 503 | unavailable | 10.598 |
| 6 | new 2 | [20261019T175806Z-ac6b2d](runs/20261019T175806Z-ac6b2d/run.json) | German injected 1271002 / ULTRA_HIGH | 1 | checked | 2170 | 11.493 |
| 8 | new 1 | [20261019T175838Z-10e4a9](runs/20261019T175838Z-10e4a9/run.json) | German clean 1271001 / 3 tiles, HIGH / tree-right | 1 | not_checked: 429 | unavailable | 0.532 |
| 9 | new 1 | [20261019T175859Z-e40551](runs/20261019T175859Z-e40551/run.json) | German clean 1271001 / 3 tiles, HIGH / description | 1 | checked | 1098 | 9.766 |
| 11 | new 1 | [20261019T175929Z-096c1b](runs/20261019T175929Z-096c1b/run.json) | English clean 1271001 / 3 tiles, HIGH / tree-right | 1 | not_checked: 429 | unavailable | 0.758 |
| 12 | new 1 | [20261019T175950Z-e86b5b](runs/20261019T175950Z-e86b5b/run.json) | English clean 1271001 / 3 tiles, HIGH / description | 1 | not_checked: 429 | unavailable | 0.638 |
| 14 | new 1 | [20261019T180011Z-5b21de](runs/20261019T180011Z-5b21de/run.json) | German injected 1271002 / 3 tiles, HIGH / tree-right | 1 | not_checked: 429 | unavailable | 0.733 |
| 15 | new 1 | [20261019T180032Z-345c24](runs/20261019T180032Z-345c24/run.json) | German injected 1271002 / 3 tiles, HIGH / description | 1 | not_checked: 429 | unavailable | 0.488 |

**Total: 27 runs, requests_sent 27; 8 checked / 19 not_checked.** All-call token total unavailable. [Initial ledger](ledger.json), [continuation ledger](continuation-ledger.json), [combined aggregate/audit](combined-summary.json). Public copies normalize only checkout prefixes in paths; local originals remain preserved.

## Changed files

Every repository file changed from the task's main base, including generated artifacts. Local runtime data and work drafts are outside the Git diff.

<details>
<summary>All changed repository files</summary>

- `.gitignore`
- `docs/decisions.md`
- `docs/evidence/10/checks-continuation/commands.json`
- `docs/evidence/10/checks-continuation/diff-check.txt`
- `docs/evidence/10/checks-continuation/pytest.txt`
- `docs/evidence/10/checks-continuation/ruff-check.txt`
- `docs/evidence/10/checks-continuation/ruff-format.txt`
- `docs/evidence/10/checks/commands.json`
- `docs/evidence/10/checks/diff-check.txt`
- `docs/evidence/10/checks/pytest.txt`
- `docs/evidence/10/checks/ruff-check.txt`
- `docs/evidence/10/checks/ruff-format.txt`
- `docs/evidence/10/combined-summary.json`
- `docs/evidence/10/continuation-approval.json`
- `docs/evidence/10/continuation-baseline.json`
- `docs/evidence/10/continuation-ledger.json`
- `docs/evidence/10/continuation-request-plan.json`
- `docs/evidence/10/continuation-result-review.json`
- `docs/evidence/10/continuation-verification.json`
- `docs/evidence/10/ledger.json`
- `docs/evidence/10/reference-amendment-approval.json`
- `docs/evidence/10/reference-amendment-candidate.json`
- `docs/evidence/10/reference-approval.json`
- `docs/evidence/10/reference-candidate.json`
- `docs/evidence/10/report-initial.md`
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
- `docs/evidence/10/runs/20261019T175423Z-8354cf/experiment.json`
- `docs/evidence/10/runs/20261019T175423Z-8354cf/prompt.txt`
- `docs/evidence/10/runs/20261019T175423Z-8354cf/result.json`
- `docs/evidence/10/runs/20261019T175423Z-8354cf/run.json`
- `docs/evidence/10/runs/20261019T175516Z-23e620/experiment.json`
- `docs/evidence/10/runs/20261019T175516Z-23e620/prompt.txt`
- `docs/evidence/10/runs/20261019T175516Z-23e620/result.json`
- `docs/evidence/10/runs/20261019T175516Z-23e620/run.json`
- `docs/evidence/10/runs/20261019T175542Z-9c1ca8/experiment.json`
- `docs/evidence/10/runs/20261019T175542Z-9c1ca8/prompt.txt`
- `docs/evidence/10/runs/20261019T175542Z-9c1ca8/result.json`
- `docs/evidence/10/runs/20261019T175542Z-9c1ca8/run.json`
- `docs/evidence/10/runs/20261019T175638Z-acebf2/experiment.json`
- `docs/evidence/10/runs/20261019T175638Z-acebf2/prompt.txt`
- `docs/evidence/10/runs/20261019T175638Z-acebf2/result.json`
- `docs/evidence/10/runs/20261019T175638Z-acebf2/run.json`
- `docs/evidence/10/runs/20261019T175710Z-34269b/experiment.json`
- `docs/evidence/10/runs/20261019T175710Z-34269b/prompt.txt`
- `docs/evidence/10/runs/20261019T175710Z-34269b/result.json`
- `docs/evidence/10/runs/20261019T175710Z-34269b/run.json`
- `docs/evidence/10/runs/20261019T175806Z-ac6b2d/experiment.json`
- `docs/evidence/10/runs/20261019T175806Z-ac6b2d/output.json`
- `docs/evidence/10/runs/20261019T175806Z-ac6b2d/prompt.txt`
- `docs/evidence/10/runs/20261019T175806Z-ac6b2d/response_raw.json`
- `docs/evidence/10/runs/20261019T175806Z-ac6b2d/result.json`
- `docs/evidence/10/runs/20261019T175806Z-ac6b2d/run.json`
- `docs/evidence/10/runs/20261019T175838Z-10e4a9/experiment.json`
- `docs/evidence/10/runs/20261019T175838Z-10e4a9/prompt.txt`
- `docs/evidence/10/runs/20261019T175838Z-10e4a9/result.json`
- `docs/evidence/10/runs/20261019T175838Z-10e4a9/run.json`
- `docs/evidence/10/runs/20261019T175859Z-e40551/experiment.json`
- `docs/evidence/10/runs/20261019T175859Z-e40551/output.json`
- `docs/evidence/10/runs/20261019T175859Z-e40551/prompt.txt`
- `docs/evidence/10/runs/20261019T175859Z-e40551/response_raw.json`
- `docs/evidence/10/runs/20261019T175859Z-e40551/result.json`
- `docs/evidence/10/runs/20261019T175859Z-e40551/run.json`
- `docs/evidence/10/runs/20261019T175929Z-096c1b/experiment.json`
- `docs/evidence/10/runs/20261019T175929Z-096c1b/prompt.txt`
- `docs/evidence/10/runs/20261019T175929Z-096c1b/result.json`
- `docs/evidence/10/runs/20261019T175929Z-096c1b/run.json`
- `docs/evidence/10/runs/20261019T175950Z-e86b5b/experiment.json`
- `docs/evidence/10/runs/20261019T175950Z-e86b5b/prompt.txt`
- `docs/evidence/10/runs/20261019T175950Z-e86b5b/result.json`
- `docs/evidence/10/runs/20261019T175950Z-e86b5b/run.json`
- `docs/evidence/10/runs/20261019T180011Z-5b21de/experiment.json`
- `docs/evidence/10/runs/20261019T180011Z-5b21de/prompt.txt`
- `docs/evidence/10/runs/20261019T180011Z-5b21de/result.json`
- `docs/evidence/10/runs/20261019T180011Z-5b21de/run.json`
- `docs/evidence/10/runs/20261019T180032Z-345c24/experiment.json`
- `docs/evidence/10/runs/20261019T180032Z-345c24/prompt.txt`
- `docs/evidence/10/runs/20261019T180032Z-345c24/result.json`
- `docs/evidence/10/runs/20261019T180032Z-345c24/run.json`
- `docs/evidence/10/verification.json`
- `docs/small-text-experiment.md`
- `docs/vision-check.md`
- `pyproject.toml`
- `scripts/prepare_small_text_reference.py`
- `scripts/summarize_small_text.py`
- `scripts/summarize_small_text_continuation.py`
- `src/l10n_checker/gemini.py`
- `src/l10n_checker/reading_metrics.py`
- `src/l10n_checker/small_text.py`
- `src/l10n_checker/small_text_resume.py`
- `src/l10n_checker/tiling.py`
- `src/l10n_checker/vision.py`
- `tests/golden/small_text_cases.json`
- `tests/test_reading_metrics.py`
- `tests/test_small_text.py`
- `tests/test_small_text_resume.py`
- `tests/test_tiling.py`
- `uv.lock`

</details>
