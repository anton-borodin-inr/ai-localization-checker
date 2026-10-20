# Issue #10: small text at 2400×1080

Summary of the issue #10 experiment. The full archive — harness code, provider
adapters, raw run folders, ledgers, visual audits and the per-provider reports —
stays on the branch
[`feat/10-small-text-experiment`](https://github.com/anton-borodin-inr/ai-localization-checker/tree/feat/10-small-text-experiment)
(head `250daa012570dc9d6a8b1ed43398fb9d91153113`) and in its unmerged
[PR #29](https://github.com/anton-borodin-inr/ai-localization-checker/pull/29).
This repository keeps the outcome: the tiling and coverage code, the reference,
the decisions and this summary.

## Question

Does a vision model read small Unciv text correctly in a 2400×1080 screenshot,
and which option keeps it readable: Gemini `MEDIA_RESOLUTION_HIGH`,
`MEDIA_RESOLUTION_ULTRA_HIGH`, or cutting the screenshot into three crops? The
answer decides whether D-014 holds and whether tiling enters the detector.

**Answer (preliminary, one source screen):** D-014 holds. The reference strings
are read at 2400×1080 without tiling. Tiling does not enter the detector
(D-032).

## Frozen setup

- **Screen:** the issue #8 technology picker, three screenshots from
  `docs/evidence/8/final/`: German clean (build 1271001), English clean
  (1271001) and German injected (1271002, with the human-labeled Mining
  ellipsis).
- **Reference:** visible strings selected by hand from the translation files at
  each screenshot's exact build commit, with APK, translation and screenshot
  hashes verified. No model output was used. Primary denominators: German clean
  **16**, English clean **20**, German injected **18 → 20**. Anton confirmed the
  reference before the first call. Two visible controls on the injected screen
  (`Schließen`, `Bogenschießen erforschen`) were omitted by mistake and added
  after all Gemini calls, with Anton's separate confirmation; no label or
  threshold changed. Both versions are kept with hash-bound approvals in
  [`issue-10/`](issue-10/):
  - [`reference-candidate.json`](issue-10/reference-candidate.json) +
    [`reference-approval.json`](issue-10/reference-approval.json) (v1, 16/20/18);
  - [`reference-amendment-candidate.json`](issue-10/reference-amendment-candidate.json) +
    [`reference-amendment-approval.json`](issue-10/reference-amendment-approval.json)
    (v2, 16/20/20).

  The `status` field inside each candidate is historical; the approval file is
  authoritative. Vertically clipped text is scored separately as diagnostics,
  not as primary misses.
- **Crops:** `l10n_checker.tiling`, exact pixel crops without resizing:
  tree-left `(0, 0, 1320, 920)`, tree-right `(1080, 0, 2400, 920)`, description
  `(0, 900, 2400, 1080)`. A local 3×3 region maps to every original cell it
  intersects.
- **Response:** an experiment-only schema with `readings` (every visible string)
  next to the unchanged draft findings. The production prompt and schema were
  not changed.
- **Scoring:** `l10n_checker.reading_metrics` (D-033). Exact match after NFC and
  whitespace normalization; fuzzy match at SequenceMatcher ≥ 0.90 over
  comparable-length spans; units shorter than eight characters are exact-only.
  Each reference unit counts once across overlapping crops. Anton-confirmed
  examples: `tests/golden/small_text_cases.json`. Coverage measures reading,
  not defect recall.
- **Calls:** one request per run (`--max-requests 1`), no retries outside the
  cap. Every failed request counts.

## Results

### Gemini (main result)

`gemini-3.6-flash`, free tier, temperature 0, timeout 180 s. Budget 33, used 27.

| Screen | HIGH | ULTRA_HIGH | 3 crops, HIGH |
|---|---|---|---|
| German clean | **16/16** exact, 1078 image tokens | **16/16** exact, 2170 image tokens | incomplete (tree-right failed) |
| English clean | not_checked (3 × 503) | **20/20** exact | incomplete |
| German injected | not_checked (3 × 503) | **20/20** exact (18/18 on v1) | incomplete |

- The paired German clean screen reads the same at HIGH and at ULTRA_HIGH, at
  half the image tokens. HIGH has no successful run on the other two screens.
- ULTRA_HIGH on the injected screen found the Mining ellipsis
  (`Bergbau und Erzgew...`) in the correct region. A HIGH tree-left crop found it
  too, with a wrong local region.
- A visual review of all 130 readings in the 8 checked responses found no
  invented strings and no reading errors.
- No three-crop variant completed. The German description crop read four
  vertically clipped units that the full screenshot did not, so crops can help
  clipped text, but the comparison is incomplete.

### Gemini free-tier failure rate

**19 of 27 requests failed: 14 HTTP 503 (model overloaded) and 5 HTTP 429.** The
429 responses named the daily free-tier quota of 20 requests per project and
model. Only 8 requests returned a checked response. The experiment could not
complete the planned comparison under its approved budget.

### Local Qwen (exploratory)

`qwen/qwen3-vl-8b` (MLX 8-bit) via LM Studio on loopback. An explicitly approved
exception to D-004/D-006 (post-v1 timing) and to D-028's cloud-key
condition. **14 requests, no spend** (local).

Only 2 of 14 responses were checked (two tree-left crops); 7 were rejected by
the client/schema contract, 3 timed out (180 s, 400 s, 400 s) and 2 returned
incomplete output after about 600 s. No complete original or crop group, so no coverage
figure. Both checked responses were clean controls and contained 12 unsupported
truncation findings. A proper local adapter was planned in #30, which is closed
for now.

### DeepSeek (exploratory, paid)

`deepseek-flash`, official API, non-thinking mode, temperature 0, image
`detail: original`, JSON object mode with a versioned format wrapper. An
explicitly approved paid exception to D-006, D-017 and D-028. **12 requests**;
cap USD 0.25; estimated spend **USD 0.0044 (off-peak tariff) to USD 0.0087
(peak tariff)** from returned token usage. The account balance read USD 2.00
before and after.

| Screen | Original | 3 crops |
|---|---|---|
| German clean | **16/16** exact | 16/16 exact |
| English clean | 16/20 exact | 18/20 exact, 20/20 fuzzy |
| German injected | not_checked (extra `confidence` field in readings) | 18/20 exact |

- 11 of 12 responses were checked; none failed on availability. JSON object mode
  does not enforce the schema; the one rejected response was not repaired.
- Misses are mostly one reference unit split across several readings (not
  joined), plus real reading errors (`Archery` → `Archer`, `Schrift` →
  `Schritt`).
- The injected tree-left crop found the Mining ellipsis in the correct local
  region. Clean controls returned no findings.

### Afterwards: DeepSeek became the v1 provider

Gemini remains the main result of issue #10. Afterwards, Anton made DeepSeek the
single v1 provider (#32): Gemini billing cannot be enabled from his account, and
the free tier failed 19 of 27 requests here. `media_resolution` is a Gemini
setting, so the D-014 readability question for DeepSeek rests on the DeepSeek
runs above and on the #32 confirmation run.

## Open questions

- **HIGH on a defective screen:** every Gemini HIGH request on the injected
  screen returned 503; the defect-detection case for HIGH is still open (D-032).
  With Gemini leaving in #32, this is unlikely to be resolved.
- **Readability status:** a screen with unreadable text must become
  `not_checked`, not "no defects". Proposed in D-031; the schema change needs its
  own task.
- **Tiling:** not adopted. For vertically clipped text the evidence points both
  ways: a Gemini description crop read units the full screenshot missed, while
  DeepSeek read 5/5 clipped units on the German original but 1/5 on its crops.
  No option was compared completely.
- **Fragmented readings:** DeepSeek splits one UI string across several
  readings. Whether coverage should join adjacent readings is a methodology
  question for Anton; issue #10 did not join them.
- **Provider comparison:** a controlled paid Gemini vs DeepSeek comparison is a
  separate task after Stage 3. One screen does not rank providers.

## Request accounting

**53 requests in total: Gemini 27, local Qwen 14, DeepSeek 12.** Every run has
`max_requests` 1 and `requests_sent` 1. Per-run index:
[issue-10-small-text-runs.md](issue-10-small-text-runs.md). No hold-out input was
used.
