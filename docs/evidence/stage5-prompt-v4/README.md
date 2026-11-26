# Stage 5: Prompt v4 vs v3 on the Dev Set (Three Detector Configurations)

**Preliminary v1 caveat:** Tested on `datasets/dev` (`34` PNGs: `24` mutated, `10` clean controls; `33` labels: `overflow` 6, `wrong_language` 17, `truncated_text` 6, `other` 4; D-006, D-044, D-049, D-062). Prompt `v4` (`prompt_template_sha256` `c13065d113e129aa119b9f0258d39513f0e61bc1214826f8f64ad2b5411bee59`) was the only variable; response schema `v2`, wrappers (`deepseek-json-object-v3` / Claude native JSON Schema), full `2400×1080` PNGs, request settings, and D-026/D-029 matching were unchanged. Hold-out (`~/l10n-holdout`) was never read or run (D-010).

**Pre-registered adoption rule:** Per configuration, compare 3-run means of `v4` vs `v3` using `recall_all` (`not_checked` screens count as misses, D-013) and precision. `v4` is **better** if recall does not drop and precision rises, or recall rises and precision does not drop; any other outcome is **mixed** (left to Anton).

## 1. Prompt v3 vs v4 Side by Side (3-Run Means on `datasets/dev`)

v3 rows come from the committed dev runs ([#82](../stage5-vision-dev/README.md), [#84](../stage5-vision-thinking/README.md), [#85](../stage5-claude-sonnet/README.md)) without rerunning, with hallucinations re-bucketed from `data/runs/*/per_image.json` under one uniform 3-bucket split (`scroll/tab-edge` / `spliced` / `other`). Per-class recall is D-026 type-free detection recall (`matched / total`).

| Configuration | Prompt | Precision | Recall (`all / chk`) | `overflow` (/6) | `wrong_lang` (/17) | `truncated` (/6) | `other` (/4) | Clean FP (/10 PNGs) | Halluc. mean (`scroll-tab / spliced / other`)\* | `not_checked` (/34) | Stability (`3/3 / 2/3 / 1/3 / 0/3`) | USD/PNG† | Time/PNG | Adoption rule |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---|---:|---:|---|
| **DeepSeek `disabled`** | `v3` ([#82](../stage5-vision-dev/README.md)) | 0.773 | 0.586 / 0.586 | 0.00 (0.000) | 12.00 (0.706) | 6.00 (1.000) | 1.33 (0.333) | 1.00 | 2.33 (`1.67 / 0.33 / 0.33`) | 0.00 (0/102) | 18 / 1 / 2 / 12 | \$0.000308 | 1.49 s | — |
| **DeepSeek `disabled`** | **`v4`** | **0.791** | 0.576 / 0.576 | 0.00 (0.000) | 11.33 (0.667) | 6.00 (1.000) | 1.67 (0.417) | **0.67** | **2.00** (`1.67 / 0.00 / 0.33`) | 0.00 (0/102) | 18 / 1 / 1 / 13 | \$0.000238 | 1.61 s | **Mixed** (`P +1.8 pp`, `R -1.0 pp`) |
| **DeepSeek `low`** | `v3` ([#84](../stage5-vision-thinking/README.md)) | 0.633 | 0.747 / 0.755 | 0.33 (0.056)‡ | 15.33 (0.902) | 6.00 (1.000) | 3.00 (0.750) | 5.00 | 10.00 (`6.00 / 1.67 / 2.33`) | 0.33 (1/102) | 22 / 3 / 2 / 6 | \$0.002212 | 8.78 s | — |
| **DeepSeek `low`** | **`v4`** | **0.748** | **0.747** / 0.755 | 0.33 (0.056)‡ | 15.33 (0.902) | 6.00 (1.000) | 3.00 (0.750) | **2.00** | **5.33** (`2.67 / 1.00 / 1.67`) | 0.33 (1/102) | **23 / 2 / 1 / 7** | \$0.002139 | 9.55 s | **Better** (`R` exact tie `74/99`, `P +11.5 pp`) |
| **Claude Sonnet 5.5** | `v3` ([#85](../stage5-claude-sonnet/README.md)) | 0.561 | 0.646 / 0.704 | 3.00 (0.500)§ | 13.00 (0.765) | 3.33 (0.556) | 2.00 (0.500) | 4.00 | 15.67 (`13.33 / 1.33 / 1.00`) | 1.33 (4/102) | 20 / 1 / 2 / 10 | \$0.011071 | 2.22 s | — |
| **Claude Sonnet 5.5** | **`v4`** | **0.754** | **0.677** / 0.677 | 2.67 (0.444)§ | 13.00 (0.765) | **4.67 (0.778)** | 2.00 (0.500) | **2.33** | **3.67** (`1.33 / 0.00 / 2.33`) | **0.00 (0/102)** | **21 / 2 / 0 / 10** | \$0.011403 | 2.06 s | **Better** (`R +3.0 pp`, `P +19.2 pp`) |

\*Hallucination 3-run integer totals (`scroll/tab-edge` / `spliced` / `other`):
- `scroll/tab-edge`: fragments cut at a screen, scroll, or tab-strip edge (`Spra`, `Spa`, `Nation`, `Natior`, scroll-clipped `tech-picker` wonder lines / `in this cit`). Totals: DS `disabled` `5 → 5`, DS `low` `18 → 8`, Claude `40 → 4` (`90%` drop: `0/19` wonder-line clippings, `1/9` `Natior`, `3/12` `Spra`).
- `spliced`: two neighbouring labels joined into one `text_seen` (`Unités inactives etzen`/`inactivesetzen`, `Notifications log max turnsDecrease`, `Maximale Rundenanzahl ... Verringern`, `turnDecrease`, `Tile yields 2`). Totals: DS `disabled` `1 → 0`, DS `low` `5 → 3` (`Unités inactives [s]etzen` 3×), Claude `4 → 0` (`100%` eliminated).
- `other`: 2-line button counter joined to its own label (`[amount] erforschen (0/24)`: DS `low` `2 → 3`, Claude `3 → 3`), clipped reads of overflowing non-edge buttons (`Decrea` 1× in DS `disabled` v3, DS `low` v3/v4, Claude v4; `Verring` 3× in Claude v4), and garbled/standalone fragments (`setzen` 1× in DS `disabled` v4; `Minege` 1× in DS `low` v4; `Uncv`/`Civliopedia`/`Baukonst`/`by one one` in DS `low` v3). Totals: DS `disabled` `1 → 1`, DS `low` `7 → 5`, Claude `3 → 7`.

†DeepSeek USD/PNG uses peak tariff (`\$0.30/1M` input miss, `\$0.006/1M` cache hit, `\$1.20/1M` output); Claude uses standard tariff (`\$2.00/1M` input, `\$10.00/1M` output). DS `low` reasoning tokens/PNG: `1,573` (`v3`) → `1,594` (`v4`).
‡DeepSeek `low` `overflow` had `0/6` exact-type in both `v3` and `v4` (`1` matched `Decrease` in R1: `truncated_text` in `v3`, `other` in `v4`).
§Claude exact-type `overflow` rose from `1.33/6` (`v3`) to **`2.33/6` (`v4`)**: `Erhöhen` `3/3` exact, `Increase` `3/3` exact, `Decrease` `2/3` (`1` exact, `1` `other`; up from `0/3` spliced in `v3`), while `Help` dropped `2/3 → 0/3` and `Verringern` was emitted as clipped `"Verring"` `3/3`.

## 2. Key Findings, `not_checked`, and `"Hilfe"`

- **`"Hilfe"` (`options-gameplay__de`, `batch-99984bb52ea65c2f`) was NOT found in any run** (`0/3` dev runs and `0/1` probe for all three configurations; `0/12` total). DeepSeek `low` reasoning still read `"Hilfe"` and dismissed it as fine (probe: `"Hilfe" bottom-left German.`; R3: `Also the button "Hilfe" bottom-left, German.`).
- **`not_checked` screens:** Claude dropped from `4/102` (`readability="partial"` on scroll-clipped `tech-picker__de`) to **`0/102`**. DeepSeek `disabled` stayed **`0/102`**. DeepSeek `low` stayed `1/102`, shifting from `1` `readability="partial"` (`v3` R3) to `1` schema error (`v4` R3, `invalid_response: type: Extra inputs are not permitted` on `city-production__de` `batch-99984bb5`, costing `1` label).
- **DeepSeek `disabled` recall delta (`58/99 → 57/99`, `-1` TP across 3 runs):** `Unités inactives` rose `2/3 → 3/3` and `Requires at least [count] population` rose `1/3 → 2/3`, while `New Game` fell `1/3 → 0/3` and `Gains du sol` fell `3/3 → 1/3`.

## 3. Probe Verification, Per-Run v4 Results, and D-035 Budget

All 3 probe requests on `options-gameplay__de__2400x1080__batch-99984bb52ea65c2f__1869508724.png` returned valid `checked` `ModelOutput` under prompt `v4` (`not_checked = 0`): DeepSeek `disabled` and Claude both returned `1` TP (`Unités inactives`) and `0` FP (dropping `Spra`); DeepSeek `low` returned `0` TP / `2` FP (`Unités inactivesetzen`, `Spra`).

| Run ID | Config | Req | `not_checked` | TP / FP / FN | Precision | Recall (`all`) | Peak USD |
|---|---|---:|---:|---|---:|---:|---:|
| [stage5-prompt-v4-probe-deepseek-disabled-20261126T162700Z](../../../data/runs/stage5-prompt-v4-probe-deepseek-disabled-20261126T162700Z/run.json) | DS `disabled` probe | 1 | 0 | 1 / 0 / 1 | 1.000 | 0.500 | \$0.000416 |
| [stage5-prompt-v4-probe-deepseek-low-20261126T162700Z](../../../data/runs/stage5-prompt-v4-probe-deepseek-low-20261126T162700Z/run.json) | DS `low` probe | 1 | 0 | 0 / 2 / 2 | 0.000 | 0.000 | \$0.003326 |
| [stage5-prompt-v4-probe-claude-20261126T162700Z](../../../data/runs/stage5-prompt-v4-probe-claude-20261126T162700Z/run.json) | Claude probe | 1 | 0 | 1 / 0 / 1 | 1.000 | 0.500 | \$0.011444 |
| [stage5-prompt-v4-deepseek-disabled-run1-20261126T162900Z](../../../data/runs/stage5-prompt-v4-deepseek-disabled-run1-20261126T162900Z/run.json) | DS `disabled` R1 | 34 | 0 | 18 / 5 / 15 | 0.783 | 0.545 | \$0.014285 |
| [stage5-prompt-v4-deepseek-disabled-run2-20261126T163030Z](../../../data/runs/stage5-prompt-v4-deepseek-disabled-run2-20261126T163030Z/run.json) | DS `disabled` R2 | 34 | 0 | 19 / 5 / 14 | 0.792 | 0.576 | \$0.004991 |
| [stage5-prompt-v4-deepseek-disabled-run3-20261126T163145Z](../../../data/runs/stage5-prompt-v4-deepseek-disabled-run3-20261126T163145Z/run.json) | DS `disabled` R3 | 34 | 0 | 20 / 5 / 13 | 0.800 | 0.606 | \$0.004991 |
| [stage5-prompt-v4-deepseek-low-run1-20261126T163345Z](../../../data/runs/stage5-prompt-v4-deepseek-low-run1-20261126T163345Z/run.json) | DS `low` R1 | 34 | 0 | 26 / 7 / 7 | 0.788 | 0.788 | \$0.097642 |
| [stage5-prompt-v4-deepseek-low-run2-20261126T164100Z](../../../data/runs/stage5-prompt-v4-deepseek-low-run2-20261126T164100Z/run.json) | DS `low` R2 | 34 | 0 | 24 / 10 / 9 | 0.706 | 0.727 | \$0.059694 |
| [stage5-prompt-v4-deepseek-low-run3-20261126T164600Z](../../../data/runs/stage5-prompt-v4-deepseek-low-run3-20261126T164600Z/run.json) | DS `low` R3 | 34 | 1 (`invalid`) | 24 / 8 / 8 (+1 NC) | 0.750 | 0.727 | \$0.060880 |
| [stage5-prompt-v4-claude-run1-20261126T162900Z](../../../data/runs/stage5-prompt-v4-claude-run1-20261126T162900Z/run.json) | Claude R1 | 34 | 0 | 22 / 6 / 11 | 0.786 | 0.667 | \$0.387516 |
| [stage5-prompt-v4-claude-run2-20261126T163100Z](../../../data/runs/stage5-prompt-v4-claude-run2-20261126T163100Z/run.json) | Claude R2 | 34 | 0 | 22 / 8 / 11 | 0.733 | 0.667 | \$0.387606 |
| [stage5-prompt-v4-claude-run3-20261126T163230Z](../../../data/runs/stage5-prompt-v4-claude-run3-20261126T163230Z/run.json) | Claude R3 | 34 | 0 | 23 / 8 / 10 | 0.742 | 0.697 | \$0.387996 |
| **Total (`12` runs)** | — | **309 / 320** | — | — | — | — | **\$1.420787 / \$2.50** |

## 4. Conclusion

**Keep prompt `v4` and propose D-064 (`Proposed`):** `v4` met the pre-registered adoption rule on **two of three configurations** (DeepSeek `low` and Claude Sonnet 5.5) and left DeepSeek `disabled` mixed (`+1.8 pp` precision, `-1.0 pp` recall). Choosing the v1 configuration remains out of scope for this task.
