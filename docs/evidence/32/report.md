# Issue #32 Part 1 — DeepSeek confirmation run

**3 of 3 responses `checked`; the injected Mining ellipsis is found in the labeled region; both clean screens get findings on the scroll-clipped description panel, which D-025 does not count as a defect.** Three screenshots, one request each: this shows the adapter works end to end and returns stable, valid responses. It does not measure precision or recall. The end-to-end slice table is #14.

## Setup

- Command, one per screenshot in `docs/evidence/8/final/` (run by Anton in his terminal; the agent's own attempts were refused by the session permission layer before any request was sent):
  `uv run --env-file .env l10n-check --image <png> --max-requests 1`
- Provider `deepseek`, requested model `deepseek-flash`, returned model `deepseek-flash` (alias only; no immutable revision), `system_fingerprint` `e72d3c7f663d3e1383b00b3884cb4501` in all three runs.
- Settings (D-034): non-thinking, temperature 0, `response_format` `json_object`, image `detail: original` (PNG bytes unchanged), `max_tokens` 4096, timeout 120 s, no streaming, no redirects, no transport retries.
- Prompt: detector `PROMPT` `v0`, byte-identical to the Gemini detector prompt, plus wrapper `deepseek-json-object-v1` (the `ModelOutput` JSON Schema). `prompt_sent.txt` in each run holds the exact text (1717 bytes).
- Records: [records/](records/), byte-identical copies of `data/runs/<run_id>/` (no absolute paths or key-like strings in them, so nothing was normalized).

## Results

| Screenshot | Run id | Status | Findings | Prompt tokens (cache hit / miss) | Completion tokens | Latency (s) | Est. cost, peak (USD) |
|---|---|---|---|---|---:|---:|---:|
| English clean | [20261020T134619Z-68d6fd](records/20261020T134619Z-68d6fd/run.json) | checked | 1 | 1454 (896 / 558) | 62 | 2.216 | 0.000247176 |
| German clean | [20261020T134628Z-88d08c](records/20261020T134628Z-88d08c/run.json) | checked | 3 | 1454 (896 / 558) | 117 | 1.986 | 0.000313176 |
| German injected | [20261020T134635Z-76d8d0](records/20261020T134635Z-76d8d0/run.json) | checked | 1 | 1454 (896 / 558) | 37 | 1.630 | 0.000217176 |

All three responses ended with `finish_reason` `stop` and passed strict validation without any repair.

### Every finding against the labels

| Run | Finding (type, `text_seen`, region, confidence) | Label | Assessment |
|---|---|---|---|
| English clean | truncated_text, "Wonders enabled: • Temple of Artemis (+1 Culture; +10% Food in all cities; +15% Production when constructing Archer units in this city;", bottom, 0.9 | none (no labels) | The description panel cuts off the last line at the bottom edge; scrolling shows it (D-025). Not a defect: would count as a false positive. The model also wrote "Archer units" where the screen shows "Archery units". |
| German clean | truncated_text, "Freigeschaltete Wunder:", bottom-left, 0.9 | none | Fully visible header, not truncated: false positive. |
| German clean | truncated_text, "Tempel der Artemis (+1 Kultur, +10%", bottom-left, 0.9 | none | Scroll-clipped description line (D-025): false positive. |
| German clean | truncated_text, "Nahrung in allen Städten: +15% Produktion beim Bau von", bottom-left, 0.9 | none | Same scroll-clipped line: false positive. |
| German injected | truncated_text, "Bergbau und Erzgew...", center, 0.95 | truncated_text, "Bergbau und Erzgew...", center | Same text, type and region as the label. |

The German injected screen also shows the scroll-clipped description, but this run reported no finding there.

This assessment is the agent's reading of the screenshots against Anton's labels and D-025. It is not an output of the matching or metric code, and it creates no labels.

## Comparison with earlier runs on the same screenshots

Same PNGs (sha256 `88ff1c55…`, `a6a5beb3…`, `372aa318…`). The **prompt differs**: the #10 Gemini and #29 DeepSeek runs used the issue 10 small-text prompt, which asks for transcriptions (`readings`) as well as findings and says explicitly that scroll viewport clipping is not a defect and that an ellipsis is a defect only if the full text is not visible elsewhere. The #32 runs use the unchanged v0 detector prompt, which says neither. No Gemini run with the v0 detector prompt exists on these screenshots. Gemini HIGH/ULTRA_HIGH and DeepSeek `detail: original` are different provider-side image treatments.

| Screenshot | #10 Gemini (small-text prompt) | #29 DeepSeek (small-text prompt) | #32 DeepSeek (detector prompt) |
|---|---|---|---|
| English clean | ULTRA_HIGH [20261019T173210Z-e38a73]: checked, 0 findings. HIGH: three attempts, all HTTP 503. | [20261020T110607Z-504fcd]: checked, 0 findings | checked, 1 finding (scroll clipping) |
| German clean | HIGH [20261019T155009Z-c8f4d4] and ULTRA_HIGH [20261019T173133Z-0a453a]: checked, 0 findings | [20261020T110538Z-03f139]: checked, 0 findings | checked, 3 findings (scroll clipping; one fully visible header) |
| German injected | ULTRA_HIGH [20261019T175806Z-ac6b2d]: checked, "Bergbau und Erzgew...", center. HIGH: all attempts HTTP 503. | [20261020T110611Z-d87d4d]: `not_checked` (extra `confidence` in readings); the rejected raw finding had the right text but region `left` | checked, "Bergbau und Erzgew...", center |

Run records of #10 and #29 are on the archive branch `feat/10-small-text-experiment` under `docs/evidence/10/runs/`.

What three screenshots support: the adapter, JSON object mode with the wrapper and strict validation produced 3/3 valid responses on these screens, in about 2 s each. The injected defect was found with the labeled region. The clean-screen false positives match the one rule the detector prompt lacks and the small-text prompt had (scroll clipping). That is plausible, but it is not shown: the prompts differ in more than that one sentence, and prompt tuning is out of scope here. Nothing here estimates precision, recall or a provider ranking.

## Cost and request accounting

- **Requests:** 3 of the 10 budgeted. Each run has `max_requests` 1, `requests_sent` 1, one attempt, no retry. No other DeepSeek or Gemini request was sent in this task.
- **Estimated cost (tariff snapshot of 2026-10-20 in `deepseek.py`, peak rates USD 0.30 / 0.006 / 1.20 per million cache-miss input / cache-hit input / output tokens):**
  - per run: 896 × 0.006 + 558 × 0.30 + completion × 1.20, per million tokens;
  - total at peak rates: **USD 0.000777528**; at off-peak rates (× 0.5): USD 0.000388764. Which rate applied was not checked, so the peak figure is the conservative one. These are tariff estimates, not a billing receipt.
- **Worst-case arithmetic that keeps the task under USD 0.10:** per request, at most 4096 output tokens (`max_tokens`) and an assumed input bound of 8192 tokens, all priced as peak cache misses: 8192 × 0.30 / 10⁶ + 4096 × 1.20 / 10⁶ = 0.0024576 + 0.0049152 = **USD 0.0073728**. For the full budget of 10 requests: **USD 0.073728 < 0.10**. The input bound is an assumption, not enforced before sending; the observed input (1454 tokens per request) is far below it and the observed output (at most 117) far below 4096.
- **Actual against worst case:** USD 0.000777528 for 3 requests, against a worst case of USD 0.0221184 for 3 requests and USD 0.073728 for the whole budget.
