# DeepSeek screenshot comparison — plan awaiting approval

## Purpose and authorization

Anton requested a paid DeepSeek API comparison and reported depositing $2. This is not authorization to spend the entire balance. Proposed limits: at most **12 new generation requests and $0.25 attributable task spend**, including failures. Existing experiment totals remain Gemini 27 and local Qwen 14; after a complete DeepSeek batch the combined actual maximum would be **53**. No additional Gemini or Qwen request.

The repository requires plan approval before implementation. Record this paid exploratory exception to D-004/D-006/D-017/D-028 and the numeric limits in issue #10 before any authenticated provider request. Keep all Accepted decisions unchanged; add a Proposed entry. Continue the same branch and PR #29, with a separate DeepSeek evidence folder and ledger. No production provider change.

## Model and API

Use the official HTTPS endpoint https://api.deepseek.com/chat/completions and model `deepseek-flash`. On 2026-10-20 the official pricing page identifies this alias as DeepSeek-V4.1-Flash-1017. Record the requested alias and whatever actual version the API returns; do not pretend an alias is an immutable revision. DeepSeek-V4-Pro does not support vision.

Parameters: one inline PNG per request, explicit image detail `original`, temperature 0, max_tokens 8192, stream false, thinking explicitly disabled, timeout 1800 seconds, no tools/search/fetch, no redirects, automatic retries or fallback. Provider-internal resizing/tokenization is documented as a treatment difference; original source and crop bytes remain untouched. Provider-specific detail is not Gemini media_resolution.

DeepSeek documents JSON object mode rather than response_format json_schema. Keep the original task instructions intact and add a versioned format-only wrapper containing the existing readings/findings schema and a small synthetic JSON example, without reference answers. Use response_format json_object and the same strict ReadingOutput validator. Hash and publish the exact combined prompt. This is a declared provider-format adaptation, so the comparison is not described as byte-identical prompting. Do not silently strip extra confidence, repair output, relax fields or rescore earlier results. If compatibility fails, retain not_checked and stop on unusable authentication, image or endpoint configuration rather than tuning the protocol live.

## Exact allocation

| Input | Original | Existing crops | New generation requests |
|---|---:|---:|---:|
| German clean build 1271001 | 1 | 3 | 4 |
| English clean build 1271001 | 1 | 3 | 4 |
| German injected build 1271002 | 1 | 3 | 4 |
| Total | 3 | 9 | 12 |

Run the three originals first, then tree-left, tree-right and description for each screenshot. The first German original is the counted compatibility check, not an extra probe. Every invocation must set --max-requests 1. Every POST attempt, including 429, 503, invalid output and timeout, consumes one slot. No repeated input and no retry allowance. A reserved/interrupted slot cannot be reused.

Reuse screenshot/crop hashes, rectangles, human-confirmed reference (16/20/20), exact/fuzzy rules, diagnostic denominators and existing human labels from issue #10. Do not send the reference to DeepSeek or derive expected strings from its output. Human confirmation already covers these exact unchanged inputs; no new reference is proposed.

## Credentials and cost accounting

The application alone loads the existing gitignored secret file through uv --env-file, as for Gemini. Default expected variable name: DEEPSEEK_API_KEY. Never open, print or copy the secret file, dump environment variables, log Authorization headers or write keys to run artifacts. If the variable is absent, stop before network access and ask only for its name/location, never its value. Redact the key from errors and any retained raw provider output. Add no dependency; use existing project facilities or the standard library.

After approval, use the official GET /user/balance before generation and after each completed attempt, and GET /models once for metadata. These are separately logged read-only requests and are not generation slots. Save only required model/balance fields. If balance or authorization cannot be checked, stop before generating. Balance differences can include unrelated account activity; report that alongside per-response token-based cost rather than calling the delta a clean per-run bill.

Capture the official tariff before the first generation. Current peak rates are $0.30/M uncached input, $0.006/M cached input, $1.20/M output; off-peak rates are half. Use peak uncached rates for conservative reservation even when running off-peak. Twelve full 8192-token outputs alone cost at most approximately $0.118 at those rates; input costs are additional. The official vision guide documents at most 1024 image tokens per image. Expected total is below $0.20, subject to final prompt/token accounting; $0.25 is the proposed task ceiling, not a promise that every request consumes that amount.

Before each send, reserve its conservative maximum input/output cost against the durable $0.25 budget and confirm sufficient remaining balance. Establish and test the input bound during offline preparation; refuse live execution if a defensible bound cannot be established. Keep reservations for failed/timeout/interrupted attempts when actual usage is unknown; do not assume they were free. Stop if the next reservation would exceed the ceiling or if balance/accounting becomes inconsistent. No automatic top-up. Report known token-based charges, conservative reserved unknown charges, and observed balance delta separately.

## Verification and Report

Before authenticated calls: offline tests for transport settings, image/prompt/schema integrity, request and money caps, failure reservations, secret redaction and no retries; full pytest and Ruff. Device tests remain skipped because capture code does not change.

Each generation records run id, requests_sent, exact settings/hashes, raw response or failure, validated output, latency, usage (including cache/reasoning details when returned) and estimated cost. Do not invent image-token breakdown or revision details if omitted. Failures are not_checked, never clean. Complete crop-group coverage is unavailable when any crop fails; retain partial evidence separately.

Audit returned readings and every finding against the immutable screenshot, including invented text, unsupported findings and region errors. Preserve human ownership of labels and conclusions. The English Report in the existing PR lists every DeepSeek run id with requests_sent, DeepSeek totals and cost accounting, plus the combined 27 + 14 + actual DeepSeek total. Preserve all previous evidence. No self-approval or merge; independent review remains required.

## Official sources checked

- [Vision and image token accounting](https://api-docs.deepseek.com/guides/vision/)
- [Models, versions and current pricing](https://api-docs.deepseek.com/quick_start/pricing/)
- [Chat Completions parameters](https://api-docs.deepseek.com/api/create-chat-completion/)
- [JSON mode](https://api-docs.deepseek.com/guides/json_mode/)
- [Balance endpoint](https://api-docs.deepseek.com/api/get-user-balance/)

No authenticated DeepSeek request has been made while preparing this plan. Actual access and key validity remain unverified until the approved application command loads the key.
