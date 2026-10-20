# Local Qwen comparison — issue 10 Report

**14/14 local generation sends completed: 2 checked, 12 not_checked (7 client-contract rejections, 3 timeouts, 2 incomplete outputs).** Gemini is unchanged at 27 sends; combined actual count **41/41**. A failed, cancelled or invalid response never means no defects. Source-screen coverage is preliminary and does not establish general model superiority. Independent PR review and Anton's final conclusions remain pending.

## What changed

Added a loopback-only standard-library HTTP adapter and separate project command, persistent local ledger, local aggregation and evidence. No new dependency, production provider/default change, prompt tuning, schema/metric/label change, resizing or source-image mutation. Existing exact crops, prompt and response schema are reused from the Gemini experiment. The confirmed amended reference was approved **before all local calls**, with denominators **German clean 16, English clean 20, German injected 20**. Its earlier correction after Gemini calls remains traceable separately.

Model metadata before the experiment: `qwen/qwen3-vl-8b`, `qwen3_vl`, MLX, 8-bit, loaded context 16185 (reported maximum 262144). This is an alias, not an immutable weight revision. No image-processing configuration or equivalent Gemini media_resolution setting is established. Request parameters: temperature 0, max_tokens 8192, stream false, unchanged JSON schema, image first then the frozen prompt in one user message. No credentials, proxies, redirects, transport retries, cloud fallback, or prior-turn/model-output context.

[Approved initial plan](plan.md), [hash-bound approval](approval.json), [12-input allocation](request-plan.json), [timeout/budget amendment](timeout-extension.json), [overnight amendment](nightly-extension.json), [execution protocol](protocol.md), [initial timeout diagnosis](diagnostic-initial.json). The initial plan remains historical; the separately approved amendments govern the later calls. Post-run model metadata could not be fetched because the server refused the read-only GET (curl exit 7); no retry or generation was made. See [the failed metadata discovery record](model-discovery-after.json).

## Local results

For each distinct input, select the first validated response, otherwise its last failure. Do not select by measured quality. Selected response costs and all-attempt costs are separate; the original 180-second timeout is included. Complete three-crop coverage is unavailable if any crop fails; partial observations remain diagnostic. Ordinary text coverage is not D-026 defect recall. Exact/fuzzy rules, crop overlap handling and clipped diagnostic denominators are unchanged.

| Input | Local option | Status | Exact primary | Fuzzy primary | Clipped diagnostic exact | Invented strings | Image tokens | Selected latency (s) | All-attempt latency (s) | Requests |
|---|---|---|---:|---:|---:|---|---|---:|---:|---:|
| German clean 1271001 | original | not_checked | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | 1188.861 | 3 |
| German clean 1271001 | tiles | not_checked | unavailable | unavailable | unavailable | unavailable; partial returned readings: 0 | unavailable | unavailable | 110.239 | 3 |
| English clean 1271001 | original | not_checked | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | 55.495 | 1 |
| English clean 1271001 | tiles | not_checked | unavailable | unavailable | unavailable | unavailable; partial returned readings: 0 | unavailable | unavailable | 115.383 | 3 |
| German injected 1271002 | original | not_checked | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | 400.008 | 1 |
| German injected 1271002 | tiles | not_checked | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | 680.080 | 3 |

The two validated local left crops transcribe four primary technology names each. Both are clean controls; all 12 validated truncation findings are unsupported, including repeated numeric findings. The remaining complete JSON responses are not accepted by the frozen local validator. Therefore this run does not provide a complete local ordinary-coverage or defect-quality ranking. It identifies two separate issues: API/client format compatibility and repeated/unsupported findings. Long latency alone is not a quality rejection criterion.

Image-token breakdown is unavailable from this local server; prompt-token totals must not be substituted for image tokens or compared directly with Gemini IMAGE tokens. Model revision is unavailable. Latency includes each recorded provider attempt and depends on this machine/runtime; deliberate inter-call pauses and offline preparation are excluded.

## Side-by-side transcription coverage

| Input | Gemini original HIGH | Gemini original ULTRA_HIGH | Local original | Gemini 3 crops HIGH | Local 3 crops |
|---|---|---|---|---|---|
| German clean 1271001 | 16/16 exact; 16/16 fuzzy | 16/16 exact; 16/16 fuzzy | unavailable | unavailable | unavailable |
| English clean 1271001 | unavailable | 20/20 exact; 20/20 fuzzy | unavailable | unavailable | unavailable |
| German injected 1271002 | unavailable | 20/20 exact; 20/20 fuzzy | unavailable | unavailable | unavailable |

HIGH/ULTRA_HIGH are Gemini-specific treatments. There are 12 distinct local inputs, not 15 artificial local resolution slots. Local calls after the overnight amendment use an explicitly authorized timeout of 1800 s (earlier calls retain 180/400 s), versus Gemini 180 s. Gemini's failed original/crop groups remain unavailable; local success against a Gemini API failure is availability evidence, not a controlled demonstration of better reading. The complete cloud comparisons, original reference scores and every cloud run are in [the preserved Gemini Report](../report-gemini.md).

## Visual audit and every finding

Validated readings reviewed: **12** out of **12**. The [visual review](result-review.json) records each output hash, invented strings, reading errors, hidden completions and every finding's region. Unique-text coverage ignores region as specified by D-026; region accuracy is diagnosed separately. The existing human labels remain unchanged; an unmatched partial reading is not automatically an invented string. Cancelled or malformed text never becomes a new label or a checked response.

| Run / index | Text | Local region | Region review | Defect diagnostic |
|---|---|---|---|---|
| 20261019T205726Z-f54d7f / 0 | Landwirtschaft | left | Correct local cell; coarse mapping remains ambiguous. | Unsupported truncation on the pre-existing clean control: the text/counter is fully visible. No new label is created. |
| 20261019T205726Z-f54d7f / 1 | Tierhaltung | top | Correct local cell; coarse mapping remains ambiguous. | Unsupported truncation on the pre-existing clean control: the text/counter is fully visible. No new label is created. |
| 20261019T205726Z-f54d7f / 2 | Bogenschießen | top | Incorrect local cell; expected center. | Unsupported truncation on the pre-existing clean control: the text/counter is fully visible. No new label is created. |
| 20261019T205726Z-f54d7f / 3 | Bergbau | top | Incorrect local cell; expected bottom. | Unsupported truncation on the pre-existing clean control: the text/counter is fully visible. No new label is created. |
| 20261019T205726Z-f54d7f / 4 | 6 | top | Incorrect local cell; expected top-right, right, bottom-right. Repeated numeric readings cannot identify one counter. | Unsupported truncation on the pre-existing clean control: the text/counter is fully visible. No new label is created. |
| 20261019T205726Z-f54d7f / 5 | 6 | top | Incorrect local cell; expected top-right, right, bottom-right. Repeated numeric readings cannot identify one counter. | Unsupported truncation on the pre-existing clean control: the text/counter is fully visible. No new label is created. |
| 20261019T205726Z-f54d7f / 6 | 6 | top | Incorrect local cell; expected top-right, right, bottom-right. Repeated numeric readings cannot identify one counter. | Unsupported truncation on the pre-existing clean control: the text/counter is fully visible. No new label is created. |
| 20261019T205726Z-f54d7f / 7 | 6 | top | Incorrect local cell; expected top-right, right, bottom-right. Repeated numeric readings cannot identify one counter. | Unsupported truncation on the pre-existing clean control: the text/counter is fully visible. No new label is created. |
| 20261019T210044Z-118817 / 0 | Animal Husbandry 6 | right | Incorrect local cell; expected top-right. For combined name plus counter, the bounding-box centre covers both visible text components. Original-cell mapping may remain ambiguous. | Unsupported truncation on the clean control; the title and counter are fully visible. No new label. |
| 20261019T210044Z-118817 / 1 | Archery 6 | right | Correct local cell. For combined name plus counter, the bounding-box centre covers both visible text components. Original-cell mapping may remain ambiguous. | Unsupported truncation on the clean control; the title and counter are fully visible. No new label. |
| 20261019T210044Z-118817 / 2 | Mining 6 | right | Incorrect local cell; expected bottom-right. For combined name plus counter, the bounding-box centre covers both visible text components. Original-cell mapping may remain ambiguous. | Unsupported truncation on the clean control; the title and counter are fully visible. No new label. |
| 20261019T210044Z-118817 / 3 | Agriculture | left | Correct local cell. For combined name plus counter, the bounding-box centre covers both visible text components. Original-cell mapping may remain ambiguous. | Unsupported truncation on the clean control; the title and counter are fully visible. No new label. |

The [output-limit diagnostic](output-limit-diagnostic.json) records the injected left crop at 602.724 s: timeout 1800 did not interrupt it, but the API returned finish_reason length with 8191 completion tokens under max_tokens 8192, and unfinished repeated overlap objects. The correct existing Mining text appears in its prefix, but an incomplete response is not credited as a checked detection. The [final German clean original](final-original-diagnostic.json) similarly returned finish_reason length at 608.848 s with 8191 completion tokens; its unfinished content repeats Schluss 243 times. Neither response hit the 1800 s timeout, and neither supplies a complete readings list.

The initial server diagnostic is separate from this audit. Prompt processing reached 100% about 13 s after the first request; the server stopped generation when the client disconnected at 180 s. Its cancelled content repeats a `Schluss` object 69 times and is unfinished. The server-side finish_reason stop does not override the client timeout or make incomplete content valid JSON. [Request-specific excerpt](server-log-excerpt-initial.txt), [server-side cancelled prediction](server-prediction-initial.json). Logged usage from that cancelled prediction is diagnostic only, not the harness's completed-response usage.

## Format compatibility and raw diagnostics

The exact API schema copied from Gemini omits `additionalProperties` restrictions, while Pydantic `Reading` forbids extra fields. Thus a response can satisfy the API-level schema and still fail the local validator when it includes `confidence` in readings. This is a transport/client contract mismatch; it does not by itself establish that the text was unreadable. The experiment keeps both original contracts and does not silently drop fields or promote rejected responses to checked. No score uses model confidence, and high self-reported values are not calibrated correctness probabilities.

[Raw-response visual diagnostics](raw-response-review.json) review **98 readings and 42 raw findings** from the seven complete JSON responses rejected by Pydantic separately, preserving confidence fields and every original `not_checked` result. This includes every raw finding's region, two occurrences of the misread Schritt/Schrift and punctuation substitutions in one German description reading. No invented strings or hidden continuations were found in those complete raw readings; their formal primary metrics remain unavailable. These diagnostics do not repair or rescore responses, create labels, or fill unavailable primary metrics. The [English format diagnostic](format-diagnostic-english.json) records 28 readings with confidence 1.0 and a wrong Agriculture region despite otherwise present text. Validated clean-crop findings also carry confidence 0.99 despite unsupported truncation claims. The reported confidence is therefore retained as a diagnostic, without thresholding or weighting.

## How it was verified

- Before the first call: 226 passed, 1 device test skipped, 1 existing SDK deprecation warning; Ruff check/format passed. Additional approval/timeout tests were added after the amendment. Latest full verification: **233 passed, 1 skipped, 1 warning**; see [actual check commands/results](checks/commands.json) and pytest log. Device tests were not run because capture/device code is unchanged.
- Adapter tests cover the inline PNG bytes, frozen prompt/schema, recorded/effective parameters, timeout 180/400/1800, malformed/truncated/missing responses, mismatched model aliases, HTTP failures, disabled redirects/proxies, no response repair and exactly one send. Ledger tests cover the original 12-cap, explicit 13/14-cap amendments, only the two approved repeats of the initial timeout, no fourth attempt, interrupted reservations and published-ledger reset protection. Approval/input/endpoint tampering is rejected.
- [Verification receipt](verification.json): all 151 pre-existing Gemini evidence files and their original Report preserved; screenshot/crop bytes unchanged; frozen prompt/schema/reference hashes unchanged; all sent local runs have cap 1, requests_sent 1 and one transport attempt. The API schema is copied exactly from the cloud request; the same Pydantic validation applies.
- `uv sync --offline` initially failed because hatchling was absent from the selected cache; subsequent `uv sync` succeeded without adding dependencies. Ruff's initial unused-import finding was fixed before the first call. No prior failed check is represented as passing. A development test block was initially inserted into the wrong test function and was corrected before the successful full suite, without removing its assertions. A published-pending/completed ledger transition initially refused the next slot before sending; a regression test and the guard were fixed, then execution resumed at that unsent input. This refusal sent zero provider requests and did not reuse a reservation.
- Live calls ran only through project commands with explicit cap 1 and the approved loopback endpoint. Read-only model discovery GETs are recorded separately; none generates text. `.env`, environment values and keys were not read or copied. No hold-out input. No server model/settings change made by the agent; post-run metadata is unavailable. No self-approval or merge; independent review pending.

## Deviations from the task

The initial 12-send/180-second plan was explicitly amended by Anton after its first timeout to **13 sends total and timeout 400 seconds**, then **14 total and 1800 seconds**: two counted retries of German clean plus eleven remaining inputs. Original records/approval remain immutable. This local-only timeout difference and unavailable revision/image-token details limit direct timing/token comparisons. The initial cancelled repetition is an observed diagnostic, not proof of its underlying cause. Any unsupported or incomplete quality comparison stays unavailable.

## Decisions proposed

**D-032** records the approved bounded local comparison now, as an isolated exception to D-004/D-006's post-v1 timing and D-028's cloud-key condition. Production remains Gemini. D-029–D-031 remain Proposed, and no Accepted entry is edited. The evidence alone does not accept a new provider or production default.

## Open questions for Anton

Review the local results and Proposed decisions after independent PR review. Further tuning, timeout/model/server changes or retries outside the recorded authorization require a new explicit plan/budget. Final model choice and merge remain Anton's. A later explicitly approved contract version could either prohibit extra fields at the local API boundary or allow optional diagnostic confidence; no such schema change or retrospective rescoring was performed here.

## API usage: every local run

**Local sends 14/14; Gemini sends 27; combined actual sends 41/41.** The original timeout counts. Each row is one POST generation; all per-run caps are 1. Model discovery GETs do not generate and are not counted as generation sends. Partial server logs are observations from the existing request, not an additional call.

| Slot | Attempt | Run id | Input | Timeout (s) | requests_sent | Result | Latency (s) |
|---:|---:|---|---|---:|---:|---|---:|
| 1 | 1 | [20261019T203555Z-2b7451](../runs/20261019T203555Z-2b7451/run.json) | German clean 1271001 / full | 180 | 1 | not_checked: timeout | 180.007 |
| 1 | 2 | [20261019T204249Z-0c72cd](../runs/20261019T204249Z-0c72cd/run.json) | German clean 1271001 / full | 400 | 1 | not_checked: timeout | 400.006 |
| 2 | 1 | [20261019T204946Z-b5d5d5](../runs/20261019T204946Z-b5d5d5/run.json) | English clean 1271001 / full | 400 | 1 | not_checked: invalid_response | 55.495 |
| 3 | 1 | [20261019T205044Z-a17e6e](../runs/20261019T205044Z-a17e6e/run.json) | German injected 1271002 / full | 400 | 1 | not_checked: timeout | 400.008 |
| 4 | 1 | [20261019T205726Z-f54d7f](../runs/20261019T205726Z-f54d7f/run.json) | German clean 1271001 / tree-left | 1800 | 1 | checked | 32.623 |
| 5 | 1 | [20261019T205801Z-0e6d1d](../runs/20261019T205801Z-0e6d1d/run.json) | German clean 1271001 / tree-right | 1800 | 1 | not_checked: invalid_response | 50.441 |
| 6 | 1 | [20261019T210014Z-bc6de2](../runs/20261019T210014Z-bc6de2/run.json) | German clean 1271001 / description | 1800 | 1 | not_checked: invalid_response | 27.175 |
| 7 | 1 | [20261019T210044Z-118817](../runs/20261019T210044Z-118817/run.json) | English clean 1271001 / tree-left | 1800 | 1 | checked | 19.667 |
| 8 | 1 | [20261019T210105Z-51cd84](../runs/20261019T210105Z-51cd84/run.json) | English clean 1271001 / tree-right | 1800 | 1 | not_checked: invalid_response | 74.307 |
| 9 | 1 | [20261019T210222Z-1fcbbd](../runs/20261019T210222Z-1fcbbd/run.json) | English clean 1271001 / description | 1800 | 1 | not_checked: invalid_response | 21.409 |
| 10 | 1 | [20261019T210246Z-9286b9](../runs/20261019T210246Z-9286b9/run.json) | German injected 1271002 / tree-left | 1800 | 1 | not_checked: incomplete_response | 602.724 |
| 11 | 1 | [20261019T211251Z-24e71b](../runs/20261019T211251Z-24e71b/run.json) | German injected 1271002 / tree-right | 1800 | 1 | not_checked: invalid_response | 46.886 |
| 12 | 1 | [20261019T211340Z-c54b2c](../runs/20261019T211340Z-c54b2c/run.json) | German injected 1271002 / description | 1800 | 1 | not_checked: invalid_response | 30.470 |
| 1 | 3 | [20261019T211412Z-8cb835](../runs/20261019T211412Z-8cb835/run.json) | German clean 1271001 / full | 1800 | 1 | not_checked: incomplete_response | 608.848 |

[Durable local ledger](ledger.json), [aggregate/readings/findings](summary.json). Local originals are in `data/runs/<run_id>`; public copies normalize only the repository prefix in paths.

## Changed files

Every task file changed from main, including cloud and local evidence, is listed below. Historical cloud Reports retain their then-current lists. Local runtime data and scratch scripts are outside the Git diff.

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
- `docs/evidence/10/local-model/approval.json`
- `docs/evidence/10/local-model/baseline.json`
- `docs/evidence/10/local-model/checks/commands.json`
- `docs/evidence/10/local-model/checks/diff-check.txt`
- `docs/evidence/10/local-model/checks/pytest.txt`
- `docs/evidence/10/local-model/checks/ruff-check.txt`
- `docs/evidence/10/local-model/checks/ruff-format.txt`
- `docs/evidence/10/local-model/diagnostic-initial.json`
- `docs/evidence/10/local-model/diagnostic-repeat.json`
- `docs/evidence/10/local-model/final-original-diagnostic.json`
- `docs/evidence/10/local-model/format-diagnostic-english.json`
- `docs/evidence/10/local-model/ledger-initial.json`
- `docs/evidence/10/local-model/ledger.json`
- `docs/evidence/10/local-model/model-discovery-after.json`
- `docs/evidence/10/local-model/models-before.json`
- `docs/evidence/10/local-model/nightly-extension.json`
- `docs/evidence/10/local-model/output-limit-diagnostic.json`
- `docs/evidence/10/local-model/plan.md`
- `docs/evidence/10/local-model/protocol.md`
- `docs/evidence/10/local-model/raw-response-review.json`
- `docs/evidence/10/local-model/report.md`
- `docs/evidence/10/local-model/request-plan.json`
- `docs/evidence/10/local-model/result-review.json`
- `docs/evidence/10/local-model/server-log-excerpt-initial.txt`
- `docs/evidence/10/local-model/server-prediction-initial.json`
- `docs/evidence/10/local-model/server-prediction-repeat.json`
- `docs/evidence/10/local-model/summary-initial.json`
- `docs/evidence/10/local-model/summary.json`
- `docs/evidence/10/local-model/timeout-extension.json`
- `docs/evidence/10/local-model/verification-initial.json`
- `docs/evidence/10/local-model/verification.json`
- `docs/evidence/10/reference-amendment-approval.json`
- `docs/evidence/10/reference-amendment-candidate.json`
- `docs/evidence/10/reference-approval.json`
- `docs/evidence/10/reference-candidate.json`
- `docs/evidence/10/report-gemini.md`
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
- `docs/evidence/10/runs/20261019T203555Z-2b7451/experiment.json`
- `docs/evidence/10/runs/20261019T203555Z-2b7451/prompt.txt`
- `docs/evidence/10/runs/20261019T203555Z-2b7451/result.json`
- `docs/evidence/10/runs/20261019T203555Z-2b7451/run.json`
- `docs/evidence/10/runs/20261019T204249Z-0c72cd/experiment.json`
- `docs/evidence/10/runs/20261019T204249Z-0c72cd/prompt.txt`
- `docs/evidence/10/runs/20261019T204249Z-0c72cd/result.json`
- `docs/evidence/10/runs/20261019T204249Z-0c72cd/run.json`
- `docs/evidence/10/runs/20261019T204946Z-b5d5d5/experiment.json`
- `docs/evidence/10/runs/20261019T204946Z-b5d5d5/prompt.txt`
- `docs/evidence/10/runs/20261019T204946Z-b5d5d5/response_raw.json`
- `docs/evidence/10/runs/20261019T204946Z-b5d5d5/result.json`
- `docs/evidence/10/runs/20261019T204946Z-b5d5d5/run.json`
- `docs/evidence/10/runs/20261019T205044Z-a17e6e/experiment.json`
- `docs/evidence/10/runs/20261019T205044Z-a17e6e/prompt.txt`
- `docs/evidence/10/runs/20261019T205044Z-a17e6e/result.json`
- `docs/evidence/10/runs/20261019T205044Z-a17e6e/run.json`
- `docs/evidence/10/runs/20261019T205726Z-f54d7f/experiment.json`
- `docs/evidence/10/runs/20261019T205726Z-f54d7f/output.json`
- `docs/evidence/10/runs/20261019T205726Z-f54d7f/prompt.txt`
- `docs/evidence/10/runs/20261019T205726Z-f54d7f/response_raw.json`
- `docs/evidence/10/runs/20261019T205726Z-f54d7f/result.json`
- `docs/evidence/10/runs/20261019T205726Z-f54d7f/run.json`
- `docs/evidence/10/runs/20261019T205801Z-0e6d1d/experiment.json`
- `docs/evidence/10/runs/20261019T205801Z-0e6d1d/prompt.txt`
- `docs/evidence/10/runs/20261019T205801Z-0e6d1d/response_raw.json`
- `docs/evidence/10/runs/20261019T205801Z-0e6d1d/result.json`
- `docs/evidence/10/runs/20261019T205801Z-0e6d1d/run.json`
- `docs/evidence/10/runs/20261019T210014Z-bc6de2/experiment.json`
- `docs/evidence/10/runs/20261019T210014Z-bc6de2/prompt.txt`
- `docs/evidence/10/runs/20261019T210014Z-bc6de2/response_raw.json`
- `docs/evidence/10/runs/20261019T210014Z-bc6de2/result.json`
- `docs/evidence/10/runs/20261019T210014Z-bc6de2/run.json`
- `docs/evidence/10/runs/20261019T210044Z-118817/experiment.json`
- `docs/evidence/10/runs/20261019T210044Z-118817/output.json`
- `docs/evidence/10/runs/20261019T210044Z-118817/prompt.txt`
- `docs/evidence/10/runs/20261019T210044Z-118817/response_raw.json`
- `docs/evidence/10/runs/20261019T210044Z-118817/result.json`
- `docs/evidence/10/runs/20261019T210044Z-118817/run.json`
- `docs/evidence/10/runs/20261019T210105Z-51cd84/experiment.json`
- `docs/evidence/10/runs/20261019T210105Z-51cd84/prompt.txt`
- `docs/evidence/10/runs/20261019T210105Z-51cd84/response_raw.json`
- `docs/evidence/10/runs/20261019T210105Z-51cd84/result.json`
- `docs/evidence/10/runs/20261019T210105Z-51cd84/run.json`
- `docs/evidence/10/runs/20261019T210222Z-1fcbbd/experiment.json`
- `docs/evidence/10/runs/20261019T210222Z-1fcbbd/prompt.txt`
- `docs/evidence/10/runs/20261019T210222Z-1fcbbd/response_raw.json`
- `docs/evidence/10/runs/20261019T210222Z-1fcbbd/result.json`
- `docs/evidence/10/runs/20261019T210222Z-1fcbbd/run.json`
- `docs/evidence/10/runs/20261019T210246Z-9286b9/experiment.json`
- `docs/evidence/10/runs/20261019T210246Z-9286b9/prompt.txt`
- `docs/evidence/10/runs/20261019T210246Z-9286b9/response_raw.json`
- `docs/evidence/10/runs/20261019T210246Z-9286b9/result.json`
- `docs/evidence/10/runs/20261019T210246Z-9286b9/run.json`
- `docs/evidence/10/runs/20261019T211251Z-24e71b/experiment.json`
- `docs/evidence/10/runs/20261019T211251Z-24e71b/prompt.txt`
- `docs/evidence/10/runs/20261019T211251Z-24e71b/response_raw.json`
- `docs/evidence/10/runs/20261019T211251Z-24e71b/result.json`
- `docs/evidence/10/runs/20261019T211251Z-24e71b/run.json`
- `docs/evidence/10/runs/20261019T211340Z-c54b2c/experiment.json`
- `docs/evidence/10/runs/20261019T211340Z-c54b2c/prompt.txt`
- `docs/evidence/10/runs/20261019T211340Z-c54b2c/response_raw.json`
- `docs/evidence/10/runs/20261019T211340Z-c54b2c/result.json`
- `docs/evidence/10/runs/20261019T211340Z-c54b2c/run.json`
- `docs/evidence/10/runs/20261019T211412Z-8cb835/experiment.json`
- `docs/evidence/10/runs/20261019T211412Z-8cb835/prompt.txt`
- `docs/evidence/10/runs/20261019T211412Z-8cb835/response_raw.json`
- `docs/evidence/10/runs/20261019T211412Z-8cb835/result.json`
- `docs/evidence/10/runs/20261019T211412Z-8cb835/run.json`
- `docs/evidence/10/verification.json`
- `docs/small-text-experiment.md`
- `docs/vision-check.md`
- `pyproject.toml`
- `scripts/prepare_small_text_reference.py`
- `scripts/summarize_small_text.py`
- `scripts/summarize_small_text_continuation.py`
- `scripts/summarize_small_text_local.py`
- `src/l10n_checker/gemini.py`
- `src/l10n_checker/local_model.py`
- `src/l10n_checker/reading_metrics.py`
- `src/l10n_checker/small_text.py`
- `src/l10n_checker/small_text_local.py`
- `src/l10n_checker/small_text_resume.py`
- `src/l10n_checker/tiling.py`
- `src/l10n_checker/vision.py`
- `tests/golden/small_text_cases.json`
- `tests/test_local_model.py`
- `tests/test_reading_metrics.py`
- `tests/test_small_text.py`
- `tests/test_small_text_resume.py`
- `tests/test_tiling.py`
- `uv.lock`

</details>
