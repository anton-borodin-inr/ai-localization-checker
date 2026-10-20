Agent: Codex, model: gpt-6.1-sol

# Issue #35 — Prompt and response schema v1

**Limitations and failures:** this is one observation per screenshot, not a precision/recall study or proof of complete text reading. The injected finding has the labeled text and type, but its region regressed from v0 `center` (the human label) to v1 `left`. All three v1 responses self-report `readable`; partial/unreadable behavior is established offline, not by these live samples. CLI preflight exposed the existing macOS hidden editable `.pth` issue; two credential-loaded command attempts exited before sending any request, as detailed below. No prompt or schema change was made after viewing results. Independent review and Anton's screenshot/label acceptance remain pending.

## Report

- **What changed:**
  - `src/l10n_checker/vision.py`: prompt/schema v1, required readability fields and strict consistency, result gating and readability run metadata.
  - `src/l10n_checker/deepseek.py`: wrapper version v2, including appended-schema changes in the bump rule; request settings are unchanged.
  - `tests/test_readability.py`: 26 new offline cases; `tests/test_vision.py` and `tests/test_deepseek.py`: update mock payloads to v1 without removing assertions or scenarios.
  - `docs/vision-check.md`: v1 contract, diagnostics and failure mapping.
  - `docs/decisions.md`: only the status of D-031 changes to Accepted, as instructed in #35; D-036 is Proposed.
  - `docs/evidence/35/report.md`, `preflight.json`, `tests.md`, `readability-red-green.json`: this report, frozen versions/hashes/settings/images, and per-case FAIL/PASS evidence.
  - `docs/evidence/35/records/20261020T144718Z-d67e6c/`: all five new files, `run.json`, `result.json`, `response_raw.json`, `prompt.txt`, `prompt_sent.txt`; byte-identical to `data/runs/20261020T144718Z-d67e6c/`.
  - `docs/evidence/35/records/20261020T144739Z-74f8b3/`: all five new files, `run.json`, `result.json`, `response_raw.json`, `prompt.txt`, `prompt_sent.txt`; byte-identical to `data/runs/20261020T144739Z-74f8b3/`.
  - `docs/evidence/35/records/20261020T144759Z-265ca3/`: all five new files, `run.json`, `result.json`, `response_raw.json`, `prompt.txt`, `prompt_sent.txt`; byte-identical to `data/runs/20261020T144759Z-265ca3/`.
- **How it was verified:**
  - `uv sync --offline`: succeeded; no dependency or lockfile change.
  - Initial `uv run pytest`: **352 passed, 1 skipped** (7.45 s).
  - `uv run pytest tests/test_readability.py -vv --junitxml=../readability-red.xml`: exit 1, **26 failed**, at test-only commit `0d53c9a`, with production files identical to `main` (`dbb5664`).
  - `uv run pytest tests/test_readability.py -vv --junitxml=../readability-green.xml`: exit 0, **26 passed** (0.30 s), with the exact same test file. Every node id, actual original failure message and outcome is in [readability-red-green.json](readability-red-green.json); the complete FAIL → PASS table is in [tests.md](tests.md). Validation tests assert the particular consistency rule, error location or error type so v0 extra-field rejection cannot falsely satisfy them.
  - Full suite after the implementation: `uv run pytest`: **378 passed, 1 skipped**. Final verification after documentation/evidence: see the final-checks section below.
  - `uv run ruff check .`: passed; `uv run ruff format --check .`: passed.
  - The one skipped test requires a prepared emulator. `--run-device` was not run because capture/device code is unchanged.
  - Three real `l10n-check` runs, each with `--max-requests 1`, all exit 0; their exact prompts, raw responses, usage and results are committed below.
  - Each record copy was compared byte-for-byte with its `data/runs/` original. Prompt and sent-prompt hashes, provider settings and PNG hashes match the pre-call manifest in every run. The diff for matching, metrics, baseline, golden cases, labeling rules and old evidence was checked to be empty.
- **Deviations from the task:** no functional or methodological scope change. The isolated checkout is under the chat's `work/` folder. To load the key without reading or copying `.env`, live commands ran from the original checkout using `--project <implementation-checkout>` and an explicit source import path. This also avoids the host's hidden `.pth` problem. CLI preflight details below are environment diagnostics, not extra provider requests. No new dependencies.
- **Decisions proposed:** D-036 records response/prompt v1 and wrapper v2; it extends the v0 response while retaining D-018 finding fields and D-034 request settings. D-031 is Accepted on Anton's instruction in #35; its original text was not rewritten.
- **Open questions for Anton:** inspect the three records against the screenshots/labels, including `left` versus `center` for the injected finding, and decide final acceptance of D-036 after independent review. No rule ambiguity was resolved by inventing labels or thresholds.
- **API usage:** **3 of 6 allowed requests**, DeepSeek only, each cap 1, no retries or failed provider requests. Total usage: **5508 prompt tokens (2688 cache hit / 2820 miss), 118 completion tokens, 5626 total tokens**. Estimated **USD 0.001003728 peak**, USD 0.000501864 off-peak, from the code's 2026-10-20 tariff snapshot; these are estimates, not receipts. Detailed accounting for every v1 run and the v0 comparison follows.

## Frozen prompt and schema

Before any live request, commit `667c9e0` recorded [preflight.json](preflight.json): prompt `v1`, response schema `v1`, wrapper `deepseek-json-object-v2`. No production code or test was changed after the three runs. The prompt expresses the existing labeling rules in game-agnostic language, not screen-specific strings or detector-derived rules:

| Source | Prompt rule |
|---|---|
| D-025 / labeling.md | Scroll clipping is not a defect **when the full content becomes visible by scrolling**. |
| D-023 / labeling.md | An ellipsis is truncated_text only when the full text is not visible anywhere else on the same screenshot. |
| D-027 / labeling.md | A raw string key or identifier shown instead of translated text is untranslated; a literal or wrongly substituted placeholder is other. |
| D-025 / labeling.md | The 3×3 region contains the centre of the text's bounding box. |
| D-031 / issue #35 | Readability concerns visible-viewport text; scroll clipping alone, hidden scroll content and untranscribed icons do not establish unreadability. |

- Detector prompt SHA-256: `4359255e06a6d64bf35be0ee30e635f4f7e3b8b1a909c6736a07030a463779eb`.
- Sent prompt SHA-256: `26f4b4f9225b5d4744b70525f4011f526efad1375bb2ca9fb1515d803e312231`.
- ModelOutput schema SHA-256 (sorted-key JSON): `c734874957fced4aea993f0283729fb20481e86513f95bffd797927154c11349`.

`readable` requires empty unreadable_regions; `partial` requires at least one cell; `unreadable` permits none. All three readability fields are required, including the nullable reason. Invalid fields or consistency violations become `invalid_response` → `not_checked`, with no repair. Valid partial/unreadable observations survive only in response_raw.json and never become CheckResult findings. Matching, metrics and finding-object fields are unchanged.

## Paired observations on identical PNGs

v0 has no readability field: its `checked` status must not be retrospectively interpreted as a `readable` declaration. Settings are identical in both versions: deepseek-flash, non-thinking, temperature 0, JSON object mode, unchanged PNG bytes, image detail original, max_tokens 4096, timeout 120 s, no redirects, streaming or transport retries. All six records return the model alias deepseek-flash and system_fingerprint e72d3c7f663d3e1383b00b3884cb4501; neither identifies an immutable model revision.

| Screenshot | #32 v0: run, status and findings | #35 v1: run, readability, status and findings |
|---|---|---|
| English clean | [20261020T134619Z-68d6fd](../../evidence/32/records/20261020T134619Z-68d6fd/result.json): checked; 1: scroll-clipped description | [20261020T144718Z-d67e6c](records/20261020T144718Z-d67e6c/result.json): readable, checked; 0 |
| German clean | [20261020T134628Z-88d08c](../../evidence/32/records/20261020T134628Z-88d08c/result.json): checked; 3: a fully visible header and two scroll-clipped description fragments | [20261020T144739Z-74f8b3](records/20261020T144739Z-74f8b3/result.json): readable, checked; 0 |
| German injected | [20261020T134635Z-76d8d0](../../evidence/32/records/20261020T134635Z-76d8d0/result.json): checked; 1: truncated_text, Bergbau und Erzgew..., center, 0.95 | [20261020T144759Z-265ca3](records/20261020T144759Z-265ca3/result.json): readable, checked; 1: truncated_text, Bergbau und Erzgew..., left, 0.9 |

Both clean controls have no human labels. v1 reported no findings on them, whereas v0 reported one and three respectively (scroll boundaries and one fully visible header). The injected finding in v1 has the same visible text and defect type as Anton's label, but the wrong grid cell: left rather than center; v0 returned center. This is an observation against existing labels, not a new label or a metric calculation. No rerun was used to seek a preferable region.

The change includes both defect-rule instructions and readability/schema fields, so these observations do not isolate the effect of a single prompt sentence. Three samples establish neither general improvement nor a provider ranking. The #14 end-to-end slice table, matching and aggregate metrics remain out of scope.

### Screenshot identity

- `tech-picker__en__2400x1080__clean__1271001.png`: `88ff1c55aef33cc9ff0fd89cd5912384b7a1017d8d9ca2d88965ec39389b9f47` (equal in the source PNG, #32 and #35).
- `tech-picker__de__2400x1080__clean__1271001.png`: `a6a5beb3ef17ce4a640261821ff1bfc02f2dfda0e81c1cfb3aadaa32407f954e` (equal in the source PNG, #32 and #35).
- `tech-picker__de__2400x1080__injected__1271002.png`: `372aa318ce3bf4d553b4b9d427a7fe6d87f566953605c21bc705dd10df816b93` (equal in the source PNG, #32 and #35).

## Every run: requests, tokens, latency and estimated cost

All rows have max_requests 1 and a single attempt ending in ok. Costs use the recorded snapshot, with peak rates USD 0.006 / 0.30 / 1.20 per million cache-hit input / cache-miss input / output tokens. No separate image-token count is returned by the API. v0 costs are historical comparison costs, not spending by this issue.

| Version | Run id | requests_sent | Prompt tokens (hit / miss) | Completion | Total | Latency s | Est. peak USD |
|---|---|---:|---|---:|---:|---:|---:|
| v0 | `20261020T134619Z-68d6fd` | 1 | 1454 (896 / 558) | 62 | 1516 | 2.216 | 0.000247176 |
| v1 | `20261020T144718Z-d67e6c` | 1 | 1836 (896 / 940) | 30 | 1866 | 1.805 | 0.000323376 |
| v0 | `20261020T134628Z-88d08c` | 1 | 1454 (896 / 558) | 117 | 1571 | 1.986 | 0.000313176 |
| v1 | `20261020T144739Z-74f8b3` | 1 | 1836 (896 / 940) | 30 | 1866 | 1.677 | 0.000323376 |
| v0 | `20261020T134635Z-76d8d0` | 1 | 1454 (896 / 558) | 37 | 1491 | 1.630 | 0.000217176 |
| v1 | `20261020T144759Z-265ca3` | 1 | 1836 (896 / 940) | 58 | 1894 | 1.689 | 0.000356976 |

- #35 total: 3 requests, USD 0.001003728 peak estimate (USD 0.000501864 off-peak).
- #32 historical total: 3 requests, USD 0.000777528 peak estimate.
- Request and USD headroom were checked before each send. A conservative planning reserve assumed 32768 input tokens, all cache misses, and the enforced 4096 output-token maximum: `(32768 × 0.30 + 4096 × 1.20) / 1,000,000 = USD 0.0147456` per request. Six such requests reserve USD 0.0884736, below USD 0.10. **The input bound is an assumption, not an enforced API cap.** Observed input was 1836 tokens per request. Unavailable cost on a failed request would consume this reserve rather than be counted as zero. No such failed request occurred.

## Live command and environment diagnostics

The successful command was run once for each of the three screenshot paths in preflight.json. Key loading remained exclusively with uv; the agent never read, printed or copied `.env` or the key and never printed environment variables. The explicit source path below is an import setting, not an environment dump:

```bash
PYTHONPATH=<implementation-checkout>/src uv run --env-file .env --project <implementation-checkout> l10n-check --image docs/evidence/8/final/<screenshot>.png --runs-dir <implementation-checkout>/data/runs --max-requests 1
```

Here the working directory was Anton's original ai-localization-checker checkout (where uv loads `.env`); the implementation checkout was this chat's work/repository. The three full screenshot names and run ids appear above. The code used was the frozen source at 667c9e0, with an explicit source import path to avoid a host issue, not another checkout's implementation.

Before these three successful commands:

1. Offline `uv run l10n-check --help` and an offline freeze script failed with ModuleNotFoundError. The editable .pth had macOS hidden flags (confirmed with `ls -lO`), matching the environment limitation already described in D-019.
2. Offline `uv run --no-editable l10n-check --help` passed. The first credential-loaded English command with --no-editable exited 1 before a request: output_directory rejected the intended repository data/runs because a non-editable install derives a different repository root. No run id was created; requests_sent 0, token usage/cost not applicable.
3. `uv sync --offline` and chflags nohidden on the local editable .pth made offline CLI help, source-file identity and the intended output directory checks pass. A subsequent credential-loaded English command without an explicit source path nevertheless failed at import (exit 1) in a later tool call. No run id was created; requests_sent 0, token usage/cost not applicable. Clearing the flag was not a persistent solution in this host environment.
4. The successful commands explicitly selected the approved checkout's src directory. This made three provider requests and generated the three records above. No repository packaging or capture code was changed to address the unrelated host issue.

## Final checks

- `uv run pytest`: exit 0, **378 passed, 1 skipped in 9.78 s**, after the implementation, report and all 15 evidence files were saved.
- `uv run ruff check .`: exit 0, all checks passed.
- `uv run ruff format --check .`: exit 0.
- `git diff --check`: exit 0.
- `git diff --exit-code 667c9e0 -- src tests`: exit 0, proving production code and tests remain frozen after the live results.
- A path-limited `git diff --exit-code dbb5664` passed for matching, metrics, reading metrics, baseline, golden cases, labeling.md, old #8/#32 evidence, agent rules, capture.py, pyproject.toml and uv.lock. A separate byte comparison verified all 15 committed record copies against their data/runs originals and checked that none contains a key-like string. No secret file or environment dump was used for this check.
