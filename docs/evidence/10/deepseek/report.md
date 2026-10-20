# DeepSeek comparison — issue 10 Report

**11/12 responses validated; injected German original is not_checked because all 33 readings add confidence.** Do not treat it as a clean screen. Five complete original/crop groups are available; this one-screen experiment does not establish a production provider choice or general defect recall. Independent review and Anton's final conclusions remain pending.

## What changed

Added a separate official DeepSeek API adapter, paid experiment command, durable request/money reservations and offline summarizer. Continue the same branch and PR #29. Production remains Gemini; existing finding/reading validators, reference, labels, matching, thresholds, source PNGs and crops are unchanged. No package added or lockfile change. HTTPS uses standard-library transport and the already installed certifi CA bundle, with certificate/hostname verification enabled; proxies, redirects and retries are disabled.

Model requested/returned: deepseek-flash. Documentation identified DeepSeek-V4.1-Flash-1017, but the response supplies only the alias, so an immutable model revision is unavailable. Explicit non-thinking mode, temperature 0, max_tokens 8192, timeout 1800 s, stream false, image detail original. The provider internally resizes/tokenizes images; this does not mutate source files or establish equivalence with Gemini media_resolution.

The [approved plan](plan.md), [hash-bound approval](approval.json), [allocation/settings](request-plan.json) and [Proposed D-033](../../../decisions.md) record the isolated paid exception to the earlier v1/free-tier restrictions. Reference denominators remain 16/20/20, confirmed by Anton before every DeepSeek call. The original Gemini post-call reference amendment remains explicitly historical.

DeepSeek documents JSON object mode, without response_format json_schema. The exact prior task instructions remain the prefix, followed by a versioned format-only schema/example wrapper. [Exact prompt](prompt.txt), [strict schema](schema.json). This changes the provider formatting treatment and is not byte-identical prompting. Returned output is never repaired, stripped or promoted after rejection. No reference text, previous model output or labels are sent.

## Results

Ordinary string coverage uses the frozen existing exact/fuzzy implementation. It is separate from defect detection/recall and region diagnostics. Fragmenting one reference unit across separate readings is not repaired by joining text. Crop overlap counts a reference unit once. Failure means unavailable group metrics. Image-token breakdown is unavailable: usage gives prompt/completion/cache totals but no separate image count.

| Input | Option | Status | Primary exact | Primary fuzzy | Clipped diagnostics | Provider latency (s) | Requests |
|---|---|---|---|---|---|---:|---:|
| German clean | original | checked | 16/16 (100%) | 16/16 (100%) | 5/5 exact; 5/5 fuzzy | 3.178 | 1 |
| German clean | tiles | checked | 16/16 (100%) | 16/16 (100%) | 1/5 exact; 2/5 fuzzy | 5.980 | 3 |
| English clean | original | checked | 16/20 (80%) | 16/20 (80%) | not applicable | 3.259 | 1 |
| English clean | tiles | checked | 18/20 (90%) | 20/20 (100%) | not applicable | 5.797 | 3 |
| German injected | original | not_checked | unavailable | unavailable | unavailable | 3.966 | 1 |
| German injected | tiles | checked | 18/20 (90%) | 18/20 (90%) | 0/1 exact; 0/1 fuzzy | 6.240 | 3 |

German clean reaches 16/16 for both options. English original reaches 16/20; its research-button and three description units are fragmented across readings. English crops reach 18/20 exact and 20/20 fuzzy: Research Archer and Archer units misread visible Archery. Injected crops reach 18/20; culture/food units are fragmented across readings and not recombined. German diagnostic text also has punctuation and a +1,5% versus +15% reading error. A 100% primary reference score therefore does not mean every character, icon, counter and clipped diagnostic was perfect.

The preserved [Gemini Report](../report-gemini.md) has German originals 16/16, English ULTRA_HIGH 20/20 and injected ULTRA_HIGH 20/20; HIGH/crop comparisons remain incomplete because of API failures. The [Qwen Report](../local-model/report.md) remains frozen at 2/14 validated responses with no complete original/crop group. Different format enforcement, provider resizing, failed groups and a single source screen prevent a clean general superiority claim.

## Visual review and every finding

The coding agent reviewed all **163 validated readings**, plus **33 raw readings** in the rejected original. [Hash-bound validated audit](result-review.json), [separate raw audit](raw-response-review.json). No wholly invented reading or hidden continuation was identified; actual reading errors (including Schrift → Schritt, Archery → Archer and punctuation/numeric substitutions) are recorded separately and retained verbatim. This is a bounded manual diagnostic, not an automatic hallucination score or a new human label. Fragmentation and icon omission remain visible in raw artifacts.

- Validated finding, run 20261020T110635Z-777496, injected tree-left: truncated_text, Bergbau und Erzgew..., confidence 0.9. It identifies the existing human-labeled ellipsis. Its local bottom-right region is correct; the coarse crop-to-original mapping can remain ambiguous. No new label or population-level recall is inferred.
- Raw finding, rejected run 20261020T110611Z-d87d4d: same text/type and confidence 0.9, but original-image region left is incorrect (existing reference center). It is not credited as a checked detection because the response failed strict validation.
- All accepted clean-control responses return empty findings. That is an observation for these controls, not proof that all future screens are defect-free. Confidence remains self-reported and uncalibrated.

## Cost and request accounting

**12 DeepSeek POST attempts, each max_requests 1 and requests_sent 1, no generation retry. Combined task count: 53 = Gemini 27 + Qwen 14 + DeepSeek 12.** Every failed/invalid attempt counts. All DeepSeek responses supply usage; no unknown-usage reservation remains. No additional generation is authorized in this batch.

The application permanently reserved **$0.2359296** for the batch against the **$0.25** ceiling. This is a conservative budget reservation, not the amount spent. The [bound](cost-bound.json) allows 32768 input tokens and 8192 output tokens per request at peak uncached rates. Actual combined-prompt length is 2425 UTF-8 bytes; the official downloadable byte-level tokenizer and generous framing margin underpin the bound. The demo tokenizer is not a pinned server revision; actual usage also satisfied the bound.

Token-based estimate: **$0.004356006 at the published off-peak rates**, or **$0.008712012 conservatively at peak rates**, using returned cache hits/misses and completion tokens. All calls ran around 11:05–11:06 UTC, outside the documented peak windows. These are tariff-derived estimates, not an independently itemized billing receipt. The [tariff snapshot](tariff.json) records source/date/rates.

The balance API returned **$2.00 before and $2.00 after**, with intermediate responses also $2.00. Observed balance delta is **$0.00 at the returned precision**; it does not establish that calls were free. No per-request cash debit can be resolved from these balance strings, and unrelated account activity could affect a balance delta. No top-up or fallback was made.

## How it was verified

- Latest full offline verification: **250 passed, 1 device test skipped, 1 existing SDK warning**; Ruff check/format and diff check passed. [Actual commands](checks/latest-commands.json). Device tests were not run because capture/device code is unchanged.
- Tests cover exact PNG bytes, prompt prefix/wrapper, settings, strict validation, no repair/retry, empty credentials, allowed endpoints, request and money caps, pre-send reservations, unknown-cost failures, HTTP-key redaction, interrupted/published reservation protection, metadata/balance failures, TLS certificate/hostname verification and narrow zero-send preflight recovery.
- [Verification receipt](verification.json): every previous evidence file preserved (the former main Report index archived byte-for-byte); screenshots/crops unchanged; all twelve runs cap 1/one transport attempt; reference/prompt/schema hashes unchanged; output review hashes verified.
- No secret file or environment dump was read/printed/copied by the agent. uv loads the existing secret file directly into the application; errors/raw artifacts redact the key. No new input, hold-out access, model tuning, schema relaxation or retrospective scoring.

## Deviations and diagnostics

Before any paid send, a command used a nonexistent checkout .env and stopped with zero network requests. The old Gemini scratch driver supplied the actual secret-file path, without inspecting its contents. Two authenticated metadata attempts then failed before a successful HTTP response. A separate unauthenticated HEAD reproduced Python's empty-root-store certificate failure. The adapter now uses the existing certifi bundle (121 CA roots), retaining CERT_REQUIRED and hostname checking. [Transport diagnostic](transport-diagnostic.json), [failed read-only metadata diagnosis](metadata-diagnostic.json).

The first discovery failure originally retained only a generic halt, so diagnosis required one additional read-only attempt; its URLError is preserved. The logging gap was corrected. A single explicit recovery is allowed only for that original failure with zero generation reservations. Its previous halt is retained in ledger history; no run, attempt or cost reservation was erased or reused. After the TLS fix, one successful GET /models and 24 successful balance GETs were recorded separately from generation counts. The unauthenticated HEAD and two failed metadata attempts are additional diagnostics, not paid generation probes.

An initial setup command used system Python without pydantic and stopped before writes; using the project venv resolved it. A later scratch audit omitted PYTHONPATH and was rerun with src configured. Development tests initially decoded a PNG as UTF-8; they now inspect bytes while retaining every secret assertion. Ruff-required exception narrowing and these fixes preceded the successful checks. No failed check is represented as passing.

## Decisions proposed and open questions

D-033 remains Proposed: approve only this bounded paid comparison, without changing any Accepted production decision. The results support a later, separately scoped evaluation of DeepSeek quality and cost, but do not by themselves choose it as the v1 provider. A future contract change could address optional reading confidence or stronger API constraints; no such change or extra run was made. Anton owns acceptance and merge; independent PR review is pending.

## Every DeepSeek run

| Slot | Run id | Input / view | max_requests | requests_sent | Result | Provider latency (s) | Peak tariff estimate ($) |
|---:|---|---|---:|---:|---|---:|---:|
| 1 | [20261020T110538Z-03f139](../runs/20261020T110538Z-03f139/run.json) | German clean / full | 1 | 1 | checked | 3.178 | 0.0010104 |
| 2 | [20261020T110607Z-504fcd](../runs/20261020T110607Z-504fcd/run.json) | English clean / full | 1 | 1 | checked | 3.259 | 0.0011256 |
| 3 | [20261020T110611Z-d87d4d](../runs/20261020T110611Z-d87d4d/run.json) | German injected / full | 1 | 1 | not_checked | 3.966 | 0.0015324 |
| 4 | [20261020T110616Z-150386](../runs/20261020T110616Z-150386/run.json) | German clean / tree-left | 1 | 1 | checked | 1.889 | 0.000543 |
| 5 | [20261020T110619Z-28c8ed](../runs/20261020T110619Z-28c8ed/run.json) | German clean / tree-right | 1 | 1 | checked | 2.329 | 0.0007626 |
| 6 | [20261020T110623Z-84c480](../runs/20261020T110623Z-84c480/run.json) | German clean / description | 1 | 1 | checked | 1.762 | 0.0005253 |
| 7 | [20261020T110626Z-d7f0c1](../runs/20261020T110626Z-d7f0c1/run.json) | English clean / tree-left | 1 | 1 | checked | 1.926 | 0.0005382 |
| 8 | [20261020T110629Z-cbf87c](../runs/20261020T110629Z-cbf87c/run.json) | English clean / tree-right | 1 | 1 | checked | 2.037 | 0.000669 |
| 9 | [20261020T110632Z-6dd4bb](../runs/20261020T110632Z-6dd4bb/run.json) | English clean / description | 1 | 1 | checked | 1.834 | 0.0004533 |
| 10 | [20261020T110635Z-777496](../runs/20261020T110635Z-777496/run.json) | German injected / tree-left | 1 | 1 | checked | 1.824 | 0.000603 |
| 11 | [20261020T110638Z-73fd38](../runs/20261020T110638Z-73fd38/run.json) | German injected / tree-right | 1 | 1 | checked | 2.248 | 0.000428712 |
| 12 | [20261020T110641Z-036be3](../runs/20261020T110641Z-036be3/run.json) | German injected / description | 1 | 1 | checked | 2.168 | 0.0005205 |

[Complete aggregate](summary.json), [durable ledger and discovery/balance records](ledger.json). Public run copies normalize only the checkout path prefix.

## Every changed repository file

The list covers the entire issue 10 branch, including earlier Gemini/Qwen work. Historical Reports retain their then-current lists.

<details><summary>Changed files</summary>

- `.env.example`
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
- `docs/evidence/10/deepseek/approval.json`
- `docs/evidence/10/deepseek/baseline.json`
- `docs/evidence/10/deepseek/checks/commands.json`
- `docs/evidence/10/deepseek/checks/diff-check-latest.txt`
- `docs/evidence/10/deepseek/checks/latest-commands.json`
- `docs/evidence/10/deepseek/checks/pytest-latest.txt`
- `docs/evidence/10/deepseek/checks/ruff-check-latest.txt`
- `docs/evidence/10/deepseek/checks/ruff-format-latest.txt`
- `docs/evidence/10/deepseek/cost-bound.json`
- `docs/evidence/10/deepseek/ledger.json`
- `docs/evidence/10/deepseek/metadata-diagnostic.json`
- `docs/evidence/10/deepseek/plan.md`
- `docs/evidence/10/deepseek/preflight-verification.json`
- `docs/evidence/10/deepseek/prompt.txt`
- `docs/evidence/10/deepseek/raw-response-review.json`
- `docs/evidence/10/deepseek/report-before-deepseek.md`
- `docs/evidence/10/deepseek/report.md`
- `docs/evidence/10/deepseek/request-plan.json`
- `docs/evidence/10/deepseek/result-review.json`
- `docs/evidence/10/deepseek/schema.json`
- `docs/evidence/10/deepseek/summary.json`
- `docs/evidence/10/deepseek/tariff.json`
- `docs/evidence/10/deepseek/transport-diagnostic.json`
- `docs/evidence/10/deepseek/verification.json`
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
- `docs/evidence/10/runs/20261020T110538Z-03f139/cost.json`
- `docs/evidence/10/runs/20261020T110538Z-03f139/experiment.json`
- `docs/evidence/10/runs/20261020T110538Z-03f139/output.json`
- `docs/evidence/10/runs/20261020T110538Z-03f139/prompt.txt`
- `docs/evidence/10/runs/20261020T110538Z-03f139/response_raw.json`
- `docs/evidence/10/runs/20261020T110538Z-03f139/result.json`
- `docs/evidence/10/runs/20261020T110538Z-03f139/run.json`
- `docs/evidence/10/runs/20261020T110607Z-504fcd/cost.json`
- `docs/evidence/10/runs/20261020T110607Z-504fcd/experiment.json`
- `docs/evidence/10/runs/20261020T110607Z-504fcd/output.json`
- `docs/evidence/10/runs/20261020T110607Z-504fcd/prompt.txt`
- `docs/evidence/10/runs/20261020T110607Z-504fcd/response_raw.json`
- `docs/evidence/10/runs/20261020T110607Z-504fcd/result.json`
- `docs/evidence/10/runs/20261020T110607Z-504fcd/run.json`
- `docs/evidence/10/runs/20261020T110611Z-d87d4d/cost.json`
- `docs/evidence/10/runs/20261020T110611Z-d87d4d/experiment.json`
- `docs/evidence/10/runs/20261020T110611Z-d87d4d/prompt.txt`
- `docs/evidence/10/runs/20261020T110611Z-d87d4d/response_raw.json`
- `docs/evidence/10/runs/20261020T110611Z-d87d4d/result.json`
- `docs/evidence/10/runs/20261020T110611Z-d87d4d/run.json`
- `docs/evidence/10/runs/20261020T110616Z-150386/cost.json`
- `docs/evidence/10/runs/20261020T110616Z-150386/experiment.json`
- `docs/evidence/10/runs/20261020T110616Z-150386/output.json`
- `docs/evidence/10/runs/20261020T110616Z-150386/prompt.txt`
- `docs/evidence/10/runs/20261020T110616Z-150386/response_raw.json`
- `docs/evidence/10/runs/20261020T110616Z-150386/result.json`
- `docs/evidence/10/runs/20261020T110616Z-150386/run.json`
- `docs/evidence/10/runs/20261020T110619Z-28c8ed/cost.json`
- `docs/evidence/10/runs/20261020T110619Z-28c8ed/experiment.json`
- `docs/evidence/10/runs/20261020T110619Z-28c8ed/output.json`
- `docs/evidence/10/runs/20261020T110619Z-28c8ed/prompt.txt`
- `docs/evidence/10/runs/20261020T110619Z-28c8ed/response_raw.json`
- `docs/evidence/10/runs/20261020T110619Z-28c8ed/result.json`
- `docs/evidence/10/runs/20261020T110619Z-28c8ed/run.json`
- `docs/evidence/10/runs/20261020T110623Z-84c480/cost.json`
- `docs/evidence/10/runs/20261020T110623Z-84c480/experiment.json`
- `docs/evidence/10/runs/20261020T110623Z-84c480/output.json`
- `docs/evidence/10/runs/20261020T110623Z-84c480/prompt.txt`
- `docs/evidence/10/runs/20261020T110623Z-84c480/response_raw.json`
- `docs/evidence/10/runs/20261020T110623Z-84c480/result.json`
- `docs/evidence/10/runs/20261020T110623Z-84c480/run.json`
- `docs/evidence/10/runs/20261020T110626Z-d7f0c1/cost.json`
- `docs/evidence/10/runs/20261020T110626Z-d7f0c1/experiment.json`
- `docs/evidence/10/runs/20261020T110626Z-d7f0c1/output.json`
- `docs/evidence/10/runs/20261020T110626Z-d7f0c1/prompt.txt`
- `docs/evidence/10/runs/20261020T110626Z-d7f0c1/response_raw.json`
- `docs/evidence/10/runs/20261020T110626Z-d7f0c1/result.json`
- `docs/evidence/10/runs/20261020T110626Z-d7f0c1/run.json`
- `docs/evidence/10/runs/20261020T110629Z-cbf87c/cost.json`
- `docs/evidence/10/runs/20261020T110629Z-cbf87c/experiment.json`
- `docs/evidence/10/runs/20261020T110629Z-cbf87c/output.json`
- `docs/evidence/10/runs/20261020T110629Z-cbf87c/prompt.txt`
- `docs/evidence/10/runs/20261020T110629Z-cbf87c/response_raw.json`
- `docs/evidence/10/runs/20261020T110629Z-cbf87c/result.json`
- `docs/evidence/10/runs/20261020T110629Z-cbf87c/run.json`
- `docs/evidence/10/runs/20261020T110632Z-6dd4bb/cost.json`
- `docs/evidence/10/runs/20261020T110632Z-6dd4bb/experiment.json`
- `docs/evidence/10/runs/20261020T110632Z-6dd4bb/output.json`
- `docs/evidence/10/runs/20261020T110632Z-6dd4bb/prompt.txt`
- `docs/evidence/10/runs/20261020T110632Z-6dd4bb/response_raw.json`
- `docs/evidence/10/runs/20261020T110632Z-6dd4bb/result.json`
- `docs/evidence/10/runs/20261020T110632Z-6dd4bb/run.json`
- `docs/evidence/10/runs/20261020T110635Z-777496/cost.json`
- `docs/evidence/10/runs/20261020T110635Z-777496/experiment.json`
- `docs/evidence/10/runs/20261020T110635Z-777496/output.json`
- `docs/evidence/10/runs/20261020T110635Z-777496/prompt.txt`
- `docs/evidence/10/runs/20261020T110635Z-777496/response_raw.json`
- `docs/evidence/10/runs/20261020T110635Z-777496/result.json`
- `docs/evidence/10/runs/20261020T110635Z-777496/run.json`
- `docs/evidence/10/runs/20261020T110638Z-73fd38/cost.json`
- `docs/evidence/10/runs/20261020T110638Z-73fd38/experiment.json`
- `docs/evidence/10/runs/20261020T110638Z-73fd38/output.json`
- `docs/evidence/10/runs/20261020T110638Z-73fd38/prompt.txt`
- `docs/evidence/10/runs/20261020T110638Z-73fd38/response_raw.json`
- `docs/evidence/10/runs/20261020T110638Z-73fd38/result.json`
- `docs/evidence/10/runs/20261020T110638Z-73fd38/run.json`
- `docs/evidence/10/runs/20261020T110641Z-036be3/cost.json`
- `docs/evidence/10/runs/20261020T110641Z-036be3/experiment.json`
- `docs/evidence/10/runs/20261020T110641Z-036be3/output.json`
- `docs/evidence/10/runs/20261020T110641Z-036be3/prompt.txt`
- `docs/evidence/10/runs/20261020T110641Z-036be3/response_raw.json`
- `docs/evidence/10/runs/20261020T110641Z-036be3/result.json`
- `docs/evidence/10/runs/20261020T110641Z-036be3/run.json`
- `docs/evidence/10/verification.json`
- `docs/small-text-experiment.md`
- `docs/vision-check.md`
- `pyproject.toml`
- `scripts/prepare_small_text_reference.py`
- `scripts/summarize_small_text.py`
- `scripts/summarize_small_text_continuation.py`
- `scripts/summarize_small_text_deepseek.py`
- `scripts/summarize_small_text_local.py`
- `src/l10n_checker/deepseek.py`
- `src/l10n_checker/gemini.py`
- `src/l10n_checker/local_model.py`
- `src/l10n_checker/reading_metrics.py`
- `src/l10n_checker/small_text.py`
- `src/l10n_checker/small_text_deepseek.py`
- `src/l10n_checker/small_text_local.py`
- `src/l10n_checker/small_text_resume.py`
- `src/l10n_checker/tiling.py`
- `src/l10n_checker/vision.py`
- `tests/golden/small_text_cases.json`
- `tests/test_deepseek.py`
- `tests/test_local_model.py`
- `tests/test_reading_metrics.py`
- `tests/test_small_text.py`
- `tests/test_small_text_resume.py`
- `tests/test_tiling.py`
- `uv.lock`

</details>
