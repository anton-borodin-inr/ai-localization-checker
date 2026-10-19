# Local Qwen comparison plan — awaiting Anton approval

## Verified server

Read-only GETs to `http://127.0.0.1:1234/v1/models` and `/api/v0/models` succeeded on 2026-10-19. No generation request has been sent.

- Model: `qwen/qwen3-vl-8b`; server type `vlm`, state `loaded`.
- Architecture: `qwen3_vl`; runtime compatibility `mlx`; quantization `8bit`.
- Loaded context: 16185; reported maximum: 262144. Keep the current server configuration.
- An embedding model is also listed and will not be used.

## Requested scope exception

This is an explicitly requested exploratory comparison alongside issue 10. D-004/D-006 normally defer local models/provider comparisons until after v1. Approval of this plan permits this isolated experiment now; production provider selection and v1 defaults remain Gemini. D-028's free-tier/key condition applies to cloud calls; this local experiment uses no cloud key or paid endpoint. Record the exception and local cap in the issue before generating. No Accepted decision is silently changed.

## Inputs and allocation

Reuse the three exact PNGs from `docs/evidence/8/final/`, identified by filename/build and hash:

| Input | Original | Existing exact crops | Total local sends |
|---|---:|---:|---:|
| German clean 1271001 | 1 | 3 | 4 |
| English clean 1271001 | 1 | 3 | 4 |
| German injected 1271002 | 1 | 3 | 4 |
| **Total** | **3** | **9** | **12** |

The crop rectangles remain tree-left (0,0,1320,920), tree-right (1080,0,2400,920), description (0,900,2400,1080). Original pixels and existing crop files stay unchanged. There is no resizing or synthetic HIGH/ULTRA_HIGH emulation.

Gemini's two original-image resolution settings are provider-specific and are not local-model treatments. Therefore there are 12 distinct local inputs instead of 15 Gemini slots. Compare the local original-image result to both existing Gemini original-image columns, and the complete local crop group to the existing Gemini partial crop evidence. Do not claim identical internal vision resolution or directly comparable image tokens.

## Frozen methodology and execution

1. Add a narrow local HTTP adapter using Python standard-library networking, with no new dependency. Restrict it to the supplied loopback endpoint and disable redirects/proxies/cloud fallback. Use the existing recorder and validator through a separate project command.
2. Send the same frozen issue-10 prompt and semantically identical readings/findings schema through `/v1/chat/completions` with an inline image. Use temperature 0, output cap 8192, client timeout 180 seconds, non-streaming, one request per run, no retries. Preserve the same schema constraints and validate with `ReadingOutput`; do not repair or selectively strip malformed output.
3. Keep the confirmed amended reference and its approval hashes: denominators German clean 16, English clean 20, German injected 20. No reference text is sent to the model. Preserve existing exact/fuzzy code, thresholds, labels and hand-confirmed examples.
4. Before generation, run offline adapter/ledger/recorder tests and Ruff. Reserve each local slot durably before sending, with task locking and `--max-requests 1` required on every invocation.
5. The first original-image slot is also the compatibility check and counts toward the 12. If image/schema support is rejected or the connection/configuration is unusable, stop the batch, preserve that result and report the blocker. Do not tune the prompt, change model/server settings or make unbudgeted probes. An ordinary model-quality omission is a result, not a reason to stop or retry.
6. Failed, timed-out or invalid calls count as one local send and produce `not_checked`. An interrupted reservation cannot be reused. Total at most 12 local sends, with no extra retry allowance. No further Gemini sends: its historical ledger stays **27/33**. Combined actual generation count is at most **39 = 27 existing + 12 local**. Discovery GETs are listed separately from generation counts.

LM Studio documents image-capable chat completions and JSON-schema output: [compatibility endpoints](https://lmstudio.ai/docs/developer/openai-compat), [structured output](https://lmstudio.ai/docs/developer/openai-compat/structured-output). Actual compatibility with this loaded model/runtime is not established until the first counted image call.

## Evidence and delivery

Record model metadata, effective request parameters, prompt/schema/image hashes, raw response, validated output or failure, usage and latency for every run under `data/runs/`. If the server omits image-token breakdown or model revision, report unavailable rather than estimate it. Local latency depends on this machine/runtime and is not model-only performance.

Review every returned reading against original pixels and confirmed source-derived reference for errors, invented text and hidden completion. Check every finding's local/original region using the existing ambiguity-preserving mapping. Keep ordinary coverage separate from defect recall and partial tile groups separate from complete variants.

Preserve all Gemini artifacts and original/amended references. Publish a separate local Report plus side-by-side comparison, each local run id/requests_sent, local total and combined actual total. Keep the existing branch/PR #29, add a Proposed decision for this bounded scope exception, rerun relevant offline checks, and update the PR Report. No self-review approval or merge.

## Approval requested

Approve the isolated local-model scope exception, the 12-send no-retry allocation, unchanged reference/metrics and the provider-specific comparison described above. No repository implementation or generation starts before approval, following AGENTS.md's plan checkpoint.
