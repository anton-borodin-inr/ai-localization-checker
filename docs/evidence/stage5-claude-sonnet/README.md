# Stage 5: Claude Sonnet 5.5 (`claude-sonnet-5-5`) vs DeepSeek on the Dev Set

**Preliminary v1 caveat:** Tested `claude-sonnet-5-5` (Messages API `anthropic-version: 2026-10-21`, `thinking: {"type": "between_tools"}`, `output_config: {"effort": "high", "format": {"type": "json_schema", ...}}`, `max_tokens: 4096`, no sampling parameters) over `datasets/dev` (`34` PNGs: `24` mutated, `10` clean controls; `33` labels: `overflow` 6, `wrong_language` 17, `truncated_text` 6, `other` 4; D-006, D-044, D-049, D-062). Prompt `v3`, schema `v2`, full `2400×1080` PNGs, and D-026/D-029 matching were unchanged; provider was the only variable. Every call used `5,060` input tokens (`3,354` native image tokens + `1,706` prompt/schema/framing — no downscaling) and `0` thinking tokens across all `102` dev calls (`0` API/schema failures). Hold-out (`~/l10n-holdout`) was never read or run (D-010).

## 1. Comparison: Claude Sonnet 5.5 vs DeepSeek `disabled` (#82) and `low` (#84) (`datasets/dev`, 34 PNGs, 33 Labels)

Per-class recall is D-026 type-free detection recall (`matched / total`). DeepSeek `disabled` (#82) and `low` (#84) rows are carried from their committed evidence reports without rerunning.

| Model / Run | `not_checked` | Precision | Recall (all / chk) | `overflow` (/6) | `wrong_lang` (/17) | `truncated` (/6) | `other` (/4) | Clean FP (10 PNGs) | Halluc. (spliced) | Stability (`3/3` / `2/3` / `1/3` / `0/3`) | USD/PNG | Time/PNG |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| **DeepSeek `disabled` 3-run mean** ([#82](../stage5-vision-dev/README.md)) | **0.00** (0/102) | **0.773** | 0.586 / 0.586 | 0.00 (0.000) | 12.00 (0.706) | **6.00 (1.000)** | 1.33 (0.333) | **1.00** | **2.33 (0.33)** | 18 / 1 / 2 / 12 | **\$0.000308**\* | **1.49 s** |
| **DeepSeek `low` 3-run mean** ([#84](../stage5-vision-thinking/README.md)) | 0.33 (1/102) | 0.633 | **0.747 / 0.755** | 0.33 (0.056)† | **15.33 (0.902)** | **6.00 (1.000)** | **3.00 (0.750)** | 5.00 | 10.00 (1.67) | **22 / 3 / 2 / 6** | \$0.002212\* | 8.78 s |
| **Claude Sonnet 5.5 3-run mean** (`between_tools`) | 1.33 (4/102) | 0.561 | 0.646 / 0.704 | **3.00 (0.500)**‡ | 13.00 (0.765) | 3.33 (0.556) | 2.00 (0.500) | 4.00 | 15.67 (1.33) | 20 / 1 / 2 / 10 | \$0.011071 | 2.22 s |
| ↳ Claude R1 ([run.json](../../../data/runs/stage5-claude-dev-run1-20261126T152200Z/run.json)) | 1 (`partial`) | 0.553 | 0.636 / 0.677 | 3 (0.500) [1 ex] | 13 (0.765) [12 ex] | 3 (0.500) | 2 (0.500) | 4 | 16 (1) | — | \$0.011060 | 2.31 s |
| ↳ Claude R2 ([run.json](../../../data/runs/stage5-claude-dev-run2-20261126T152400Z/run.json)) | 2 (`partial`) | 0.568 | 0.636 / 0.724 | 3 (0.500) [1 ex] | 13 (0.765) [12 ex] | 3 (0.500) | 2 (0.500) | 4 | 14 (1) | — | \$0.011068 | 2.34 s |
| ↳ Claude R3 ([run.json](../../../data/runs/stage5-claude-dev-run3-20261126T152600Z/run.json)) | 1 (`partial`) | 0.564 | 0.667 / 0.710 | 3 (0.500) [2 ex] | 13 (0.765) [12 ex] | 4 (0.667) | 2 (0.500) | 4 | 17 (2) | — | \$0.011083 | 2.03 s |

\*DeepSeek USD/PNG uses peak tariff (`\$0.30/1M` input miss, `\$1.20/1M` output); Claude uses standard tariff (`\$2.00/1M` input, `\$10.00/1M` output, verified `2026-11-26`).
†DeepSeek `low` had `0/6` exact-type `overflow` (`1` match in R1 flagged `Decrease` as `truncated_text`).
‡Claude exact-type `overflow` was `1.33/6` (`1` in R1, `1` in R2, `2` in R3); remaining matched `overflow` labels were reported as `other` (plus `1` `wrong_language` label `"Bergbau"` reported as `other` in `3/3` runs).
`not_checked` reasons (all `4/102` were valid `readability="partial"` on `tech-picker__de`, blaming the scroll-clipped bottom wonder line, costing `2` labels each → `fn_on_not_checked`: `2`, `4`, `2`): `batch-e45e29bd` in R1 & R2; `batch-99984bb5` in R2 & R3.

## 2. `overflow` and `"Hilfe"` (`options-gameplay__de`, `batch-99984bb52ea65c2f`)

- **Overall `overflow` (`3.00/6` matched, `1.33/6` exact):** Claude is the first vision model here to detect `overflow` on the full image:
  - Found `3/3`: `"Erhöhen"` (`overflow` `3/3`), `"Increase"` (`other` R1–R2, `overflow` R3).
  - Found `2/3`: `"Help"` (`other` R1 & R3; missed R2).
  - Found `1/3`: `"Verringern"` (`other` R2; R1 flagged neighbor `"Maximale Rundanzahl des Benachrichtigungsverlaufs"`, R3 spliced both).
  - Missed `0/3`: `"Decrease"` (visually noticed in `3/3` runs, but spliced with the neighboring label as `other`: `"Notifications log max turnsDecrease"`) and **`"Hilfe"`**.
- **`"Hilfe"` was NOT found as `overflow` (or any defect) in any run (`0/3` dev runs + `0/1` probe).** In every call on `options-gameplay__de__2400x1080__batch-99984bb52ea65c2f__1869508724.png`, Claude returned the exact same two findings:
  > `{"defect_type": "wrong_language", "text_seen": "Unités inactives", "region": "top", "confidence": 0.9}`
  > `{"defect_type": "truncated_text", "text_seen": "Spra", "region": "top-right", "confidence": 0.6}`

## 3. Hallucinations and Stability (3-Run Totals)

Total hallucinations across 3 Claude runs were **`47` (`15.67`/run)** — `6.7×` DeepSeek `disabled` (`7`) and `1.6×` DeepSeek `low` (`30`), driven overwhelmingly by viewport/scroll-edge clipping rather than invented text:

| Hallucination pattern (3-run total / mean) | DeepSeek `disabled` | DeepSeek `low` | Claude Sonnet 5.5 | Claude examples |
|---|---:|---:|---:|---|
| **Spliced adjacent labels** | **1** (0.33) | 5 (1.67) | 4 (1.33) | `"Notifications log max turnsDecrease"` (`3×`), `"Maximale Rundenanzahl des Benachrichtigungsverlaufs Verringern"` (`1×`); `0` splices on `"Unités inactives"` |
| **2-line button counter joined** | **0** (0.00) | 2 (0.67) | 3 (1.00) | `"[amount] erforschen (0/24)"` (`3×`, misclassified as `wrong_language`) |
| **Clipped viewport / scroll edge** | **6** (2.00) | 19 (6.33) | 40 (13.33) | `"Spra"` (`12×`), `"Natior"`/`"Nation"` (`9×`), scroll-clipped `"• Temple of Artemis..."` / `"• Tempel der Artemis..."` (`19×`, including all `6` clean `tech-picker` calls) |
| **Misread / typo text** | **0** (0.00) | 4 (1.33) | **0** (0.00) | — |
| **Total hallucinations** | **7** (2.33) | 30 (10.00) | 47 (15.67) | Clean FPs (`4/run` every run): `civilopedia__de` (`Natior`/`Nation`), `options-gameplay__de` (`Spra`), `tech-picker__de` & `tech-picker__en` (scroll-clipped wonder line) |

- **Stability (`33` labels):** **`20` (`3/3`) / `1` (`2/3`) / `2` (`1/3`) / `10` (`0/3`)**. The `10` labels missed `0/3` were: `"Hilfe"` & `"Decrease"` (`overflow`), both `"Arbeiter"` occurrences on `city-production__en` (`wrong_language`), `"Mining"` & `"Minage"` (`wrong_language`), `"[amount] erforschen"` & `"Research [amount]"` (`other`), and `"Mauerarbeiten und S..."` & `"Bergbau und Erzgew..."` (`truncated_text`, hurt by `readability="partial"` in R2–R3 and missed in R1).

## 4. Probe and Budget Accounting (D-035)

- **Probe** ([run.json](../../../data/runs/stage5-claude-probe-20261126T151700Z/run.json)): `1` request on `options-gameplay__de` (`batch-99984bb5`), `5,060` input tokens (`<= 12,976` reserve bound), `115` output tokens (`0` thinking), `3.635 s`, `\$0.01127`.
- **Total task API usage (`4` runs: `1` probe + `3` dev runs):** **`103 / 110` requests**, `521,180` input tokens, `9,811` output tokens (`0` cache write/read), **`\$1.14047` / `\$2.00`** budget.

## 5. Conclusion

**Mixed result — keep DeepSeek `deepseek-flash` (D-034) as v1 default (no D-034 superseding decision proposed):**
- Native-resolution Claude Sonnet 5.5 broke the `0/6` `overflow` ceiling (`3.00/6` matched, `1.33/6` exact, plus visually catching `"Decrease"` in `3/3` spliced findings), while still missing `"Hilfe"` (`0/3`).
- However, it **regressed sharply on precision (`0.561` vs `0.773` / `0.633`), hallucinations (`15.67` vs `2.33` / `10.00`), `not_checked` (`1.33` vs `0.00` / `0.33`), and `truncated_text` recall (`0.556` vs `1.000`)** — mostly because it repeatedly flagged scroll-clipped wonder descriptions and viewport-clipped tab headers as truncation or `readability="partial"` despite prompt `v3`'s D-025 rule — at **`36×` the cost of DeepSeek `disabled`** (`5×` DeepSeek `low`).
- `--provider claude` remains available on `l10n-eval` alongside default `--provider deepseek`.
