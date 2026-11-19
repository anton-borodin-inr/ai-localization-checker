# Stage 5: First Vision-Detector Measurement on the Dev Set

**Preliminary v1 caveat:** v1 uses 1 provider (`deepseek-flash`), 1 resolution (`2400×1080` at `420 dpi`), 5 dev source screens (`34` PNGs: `24` mutated, `10` clean controls), 2 languages (`en`, `de`), and `33` human-confirmed labels (`overflow` 6, `wrong_language` 17, `truncated_text` 6, `other` 4; D-006, D-044, D-049, D-062). Results are a preliminary v1 starting-point measurement of the unchanged detector (D-034, D-036, D-046, D-048: prompt `v3`, schema `v2`, wrapper `deepseek-json-object-v3`, temperature `0`, non-thinking, `detail: original`). Hold-out (`~/l10n-holdout`) was never read or run (D-010).

**Budget reserve note (D-035):** `evaluation.worst_case_request_reserve_usd()` reserves `1,048,576` input tokens plus `4,096` output tokens (`USD 0.319488`) before each request. Because Run 1's actual peak spend across 34 images is `USD 0.0223752` (`0.0223752 + 0.319488 = 0.3418632 > 0.33`), a `--max-usd 0.33` per-run cap would stop at image 18 (`not_checked: usd_cap_reached`). Runs 1 and 2 therefore used `--max-usd 0.36`, and Run 3 used `--max-usd = min(0.36, 1.00 - 0.026689968) = 0.36` with no code changes. Actual total spend across all 3 runs (102 requests) was **`USD 0.031413` peak** (`USD 0.015706` off-peak).

## 1. Per-Run, 3-Run Mean, and Baseline Comparison (`datasets/dev`, 34 PNGs, 33 Labels)

Per-class recall is D-026 type-free detection recall (`matched / total`). For the vision detector, every matched finding in all 3 runs also had the exact label `defect_type`. The baseline row is reused without rerunning from `stage6-eval-dev-baseline-20261119T190210Z` (D-063 Tesseract `T2` after the #79 literal-placeholder fix) and is a **different detector (`ocr-translation-baseline`)** whose TPs come mostly from `missing`-rule expectations (`15` missing-rule vs `5` OCR-observed; only `6/20` match the label's `defect_type`).

| Detector / Run ID | `not_checked` (reason) | TP (obs / miss) | FP | FN (+NC) | Precision | Recall (all / checked) | `overflow` (/6) | `wrong_lang` (/17) | `truncated` (/6) | `other` (/4) | Clean FP (10 PNGs) | Halluc. | Peak USD (per PNG) | Time (per PNG) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **Vision Run 1** (`stage5-eval-dev-vision-run1-20261119T212830Z`) | 0 (—) | 21 (21 / 0) | 6 | 12 (+0) | 0.778 | 0.636 / 0.636 | 0 (0.000) | 13 (0.765) | 6 (1.000) | 2 (0.500) | 0 | 2 | \$0.022375 (\$0.000658) | 57.1 s (1.68 s) |
| **Vision Run 2** (`stage5-eval-dev-vision-run2-20261119T212945Z`) | 0 (—) | 18 (18 / 0) | 6 | 15 (+0) | 0.750 | 0.545 / 0.545 | 0 (0.000) | 11 (0.647) | 6 (1.000) | 1 (0.250) | 1 | 4 | \$0.004315 (\$0.000127) | 46.6 s (1.37 s) |
| **Vision Run 3** (`stage5-eval-dev-vision-run3-20261119T213055Z`) | 0 (—) | 19 (19 / 0) | 5 | 14 (+0) | 0.792 | 0.576 / 0.576 | 0 (0.000) | 12 (0.706) | 6 (1.000) | 1 (0.250) | 2 | 1 | \$0.004723 (\$0.000139) | 48.3 s (1.42 s) |
| **Vision 3-Run Mean** (`deepseek-flash`, prompt `v3`) | **0.0 (—)** | **19.33 (19.33 / 0)** | **5.67** | **13.67 (+0)** | **0.773** | **0.586 / 0.586** | **0.00 (0.000)** | **12.00 (0.706)** | **6.00 (1.000)** | **1.33 (0.333)** | **1.00** | **2.33** | **\$0.010471 (\$0.000308)** | **50.7 s (1.49 s)** |
| **Baseline (different detector: OCR + table `T2`)** (`stage6-eval-dev-baseline-20261119T190210Z`) | 0 (—) | 20 (5 obs / 15 miss) | 172 (34 / 138) | 13 (+0) | 0.104 | 0.606 / 0.606 | 6 (1.000)\* | 10 (0.588) | 1 (0.167) | 3 (0.750) | 49 (9 / 40) | 6 | \$0 (\$0) | 35.6 s (1.05 s) |

\*All 6 baseline `overflow` TPs are `missing`-rule `truncated_text` findings caused by OCR failing to read the overflowing word (0 exact-type `overflow` matches; D-063).

## 2. Hallucinations (7 Total Across 3 Runs: 4 Clipped Fragments, 3 Invented/Garbled)

Under the whole-word presence rule (D-029, golden `08c`), an unmatched finding whose body (without trailing `...`) does not sit at word boundaries in `screen_texts` (and is `< 0.90` similar to every visible text and label `text_expected`) counts as a hallucination. Below, clipped sub-word fragments of visible text are separated from invented/garbled text:

| Category | Run(s) | Screenshot | Finding type & region | `text_seen` | Source visible text / explanation |
|---|---|---|---|---|---|
| **Clipped fragment of visible text** (4) | Runs 1, 2, 3 (3×) | `options-gameplay__de__…__batch-e46946a0…__1892114822.png` | `truncated_text` (`top-right`) | `"Spra"` | Sub-word prefix of visible header `"Sprache"`, clipped at the right viewport edge of the options table. |
| **Clipped fragment of visible text** | Run 1 (1×) | `options-gameplay__en__…__batch-e46946a0…__1892114822.png` | `overflow` (`bottom`) | `"Decrea"` | Sub-word prefix of the overflowing label `"Decrease"` (no trailing `...`, similarity `6/8 = 0.75 < 0.90`, so 1 FN + 1 hallucination FP). |
| **Invented / garbled text** (3) | Run 2 (1×) | `options-gameplay__de__…__batch-37517e5f…__1862826555.png` (clean) | `truncated_text` (`top-right`) | `"Spa"` | Misread of viewport-clipped `"Sprache"` (dropped `'r'`; not a contiguous substring of `"Sprache"`). |
| **Invented / garbled text** | Run 2 (1×) | `options-gameplay__de__…__batch-99984bb5…__1869508724.png` | `truncated_text` (`top-right`) | `"Spa"` | Same misread of viewport-clipped `"Sprache"` (dropped `'r'`). |
| **Invented / garbled text** | Run 2 (1×) | `options-gameplay__de__…__batch-99984bb5…__1869508724.png` | `wrong_language` (`center`) | `"Unités inactives etzen"` | Splices injected `"Unités inactives"` with `"etzen"` from a neighboring German option (similarity `16/22 = 0.727 < 0.90` to label, causing 1 FN + 1 hallucination FP). |

*(The remaining 10 FPs across the 3 runs name real whole-word visible strings: 6× neighboring slider labels `"Maximale Rundenanzahl des Benachrichtigungsverlaufs"` / `"Notifications log max turn"` flagged as `overflow` in 3/3 runs; 1× native `"Settler"` in Run 1; 1× game name `"Unciv"` in Run 1; 2× clean German Civilopedia paragraphs containing `"Civilization V"` / `"UnCiv"` in Run 3.)*

## 3. Stability Across the 3 Runs

- **Labels found (33 labels total):**
  - **3/3 runs: 18 labels (`54.5%`)** — all `6/6` `truncated_text` labels (`tech-picker` DE/EN), `11/17` `wrong_language` labels (`city-production` DE 2 / EN 3, `civilopedia` EN 1, `empire-stats` DE 1 / EN 1, `options-gameplay` DE 1 / EN 1, `tech-picker` EN 1), and `1/4` `other` label (`city-production__de` batch `e45e29bd` `"Benötigt mindestens [count] Bevölkerung"`).
  - **2/3 runs: 1 label (`3.0%`)** — `options-gameplay__de` batch `99984bb5` `wrong_language` `"Unités inactives"` (Runs 1 & 3; Run 2 emitted `"Unités inactives etzen"`).
  - **1/3 runs: 2 labels (`6.1%`)** — `city-production__en` batch `e45e29bd` `other` `"Requires at least [count] population"` (Run 1) and `civilopedia__de` batch `99984bb5` `wrong_language` `"New Game"` (Run 1).
  - **0/3 runs: 12 labels (`36.4%`)** — all `6/6` `overflow` labels on `options-gameplay` (`"Hilfe"`, `"Verringern"`, `"Erhöhen"`, `"Increase"`, `"Help"`, `"Decrease"`), `4/17` short `wrong_language` labels (`civilopedia__de` `"Nouvelle partie"`, `empire-stats__de` `"Tile yields"`, `tech-picker__de` `"Mining"` and `"Minage"`), and `2/4` `other` broken-placeholder labels on `tech-picker` (`"[amount] erforschen"`, `"Research [amount]"`).
- **Finding repeatability (75 total finding instances across 3 runs: 27 + 24 + 24; 0 duplicates collapsed within any run):**
  - Grouped by `(image, defect_type, normalize_text(text_seen))` (identical to grouping by `(image, normalize_text(text_seen))` because no finding changed `defect_type` across runs):
    - **Repeated in 3/3 runs:** **20 distinct `(image, text)` keys** (**21 findings/run = 63/75 instances**, as `"Arbeiter"` appears twice per run in `left` and `bottom-right` on `city-production__en` batch `99984bb5`): **17 distinct TP keys (18 TP findings/run)** and **3 distinct FP keys** (`"Maximale Rundenanzahl des Benachrichtigungsverlaufs"`, `"Notifications log max turn"`, `"Spra"`).
    - **Repeated in 2/3 runs:** **1 distinct key** (**2/75 instances**, Runs 1 & 3): **1 TP** (`"Unités inactives"`).
    - **Present in 1/3 runs:** **10 distinct keys** (**10/75 instances**): **2 TPs** (`"Requires at least [count] population"`, `"New Game"`) and **8 FPs**.

## 4. Readability Check (D-031 / D-036)

Across all **34 PNGs × 3 runs (102 responses)**, the model returned **`readability = "readable"` (`unreadable_regions = []`, `status = "checked"`) on 102/102 calls** (`0` `partial`, `0` `unreadable`, `0` `fn_on_not_checked`). Below is the per-screenshot readability answer next to its `FN` across the 3 runs, starting with the **13 screens marked `readable` that still missed labels (`FN > 0`)**:

| Screenshot | Labels | Readability (R1 / R2 / R3) | FN (R1 / R2 / R3) | Missed label(s) on `readable` screen (`defect_type`: `text_seen`) |
|---|---:|---|---:|---|
| **Screens marked `readable` that missed labels (13 PNGs)** | | | | |
| `city-production__en__2400x1080__batch-e45e29bd1f0f9039__1887578114.png` | 1 | `readable` / `readable` / `readable` | 0 / 1 / 1 | `other`: `"Requires at least [count] population"` (R2, R3) |
| `civilopedia__de__2400x1080__batch-99984bb52ea65c2f__1869508724.png` | 1 | `readable` / `readable` / `readable` | 0 / 1 / 1 | `wrong_language`: `"New Game"` (R2, R3) |
| `civilopedia__de__2400x1080__batch-e46946a0afe9ec07__1892114822.png` | 1 | `readable` / `readable` / `readable` | 1 / 1 / 1 | `wrong_language`: `"Nouvelle partie"` |
| `empire-stats__de__2400x1080__batch-e45e29bd1f0f9039__1887578114.png` | 1 | `readable` / `readable` / `readable` | 1 / 1 / 1 | `wrong_language`: `"Tile yields"` |
| `options-gameplay__de__2400x1080__batch-99984bb52ea65c2f__1869508724.png` | 2 | `readable` / `readable` / `readable` | 1 / 2 / 1 | `overflow`: `"Hilfe"` (3/3); `wrong_language`: `"Unités inactives"` (R2) |
| `options-gameplay__de__2400x1080__batch-e45e29bd1f0f9039__1887578114.png` | 2 | `readable` / `readable` / `readable` | 1 / 1 / 1 | `overflow`: `"Verringern"` |
| `options-gameplay__de__2400x1080__batch-e46946a0afe9ec07__1892114822.png` | 1 | `readable` / `readable` / `readable` | 1 / 1 / 1 | `overflow`: `"Erhöhen"` |
| `options-gameplay__en__2400x1080__batch-99984bb52ea65c2f__1869508724.png` | 2 | `readable` / `readable` / `readable` | 1 / 1 / 1 | `overflow`: `"Increase"` |
| `options-gameplay__en__2400x1080__batch-e45e29bd1f0f9039__1887578114.png` | 1 | `readable` / `readable` / `readable` | 1 / 1 / 1 | `overflow`: `"Help"` |
| `options-gameplay__en__2400x1080__batch-e46946a0afe9ec07__1892114822.png` | 1 | `readable` / `readable` / `readable` | 1 / 1 / 1 | `overflow`: `"Decrease"` (R1 emitted clipped `"Decrea"`) |
| `tech-picker__de__2400x1080__batch-e45e29bd1f0f9039__1887578114.png` | 2 | `readable` / `readable` / `readable` | 1 / 1 / 1 | `wrong_language`: `"Mining"` |
| `tech-picker__de__2400x1080__batch-e46946a0afe9ec07__1892114822.png` | 2 | `readable` / `readable` / `readable` | 2 / 2 / 2 | `wrong_language`: `"Minage"`; `other`: `"[amount] erforschen"` |
| `tech-picker__en__2400x1080__batch-99984bb52ea65c2f__1869508724.png` | 2 | `readable` / `readable` / `readable` | 1 / 1 / 1 | `other`: `"Research [amount]"` |
| **Screens marked `readable` with 0 missed labels (11 mutated + 10 clean PNGs)** | | | | |
| `city-production__de__2400x1080__batch-99984bb52ea65c2f__1869508724.png` | 1 | `readable` / `readable` / `readable` | 0 / 0 / 0 | — |
| `city-production__de__2400x1080__batch-e45e29bd1f0f9039__1887578114.png` | 1 | `readable` / `readable` / `readable` | 0 / 0 / 0 | — |
| `city-production__de__2400x1080__batch-e46946a0afe9ec07__1892114822.png` | 1 | `readable` / `readable` / `readable` | 0 / 0 / 0 | — |
| `city-production__en__2400x1080__batch-99984bb52ea65c2f__1869508724.png` | 2 | `readable` / `readable` / `readable` | 0 / 0 / 0 | — |
| `city-production__en__2400x1080__batch-e46946a0afe9ec07__1892114822.png` | 1 | `readable` / `readable` / `readable` | 0 / 0 / 0 | — |
| `civilopedia__en__2400x1080__batch-e46946a0afe9ec07__1892114822.png` | 1 | `readable` / `readable` / `readable` | 0 / 0 / 0 | — |
| `empire-stats__de__2400x1080__batch-99984bb52ea65c2f__1869508724.png` | 1 | `readable` / `readable` / `readable` | 0 / 0 / 0 | — |
| `empire-stats__en__2400x1080__batch-e45e29bd1f0f9039__1887578114.png` | 1 | `readable` / `readable` / `readable` | 0 / 0 / 0 | — |
| `tech-picker__de__2400x1080__batch-99984bb52ea65c2f__1869508724.png` | 2 | `readable` / `readable` / `readable` | 0 / 0 / 0 | — |
| `tech-picker__en__2400x1080__batch-e45e29bd1f0f9039__1887578114.png` | 1 | `readable` / `readable` / `readable` | 0 / 0 / 0 | — |
| `tech-picker__en__2400x1080__batch-e46946a0afe9ec07__1892114822.png` | 2 | `readable` / `readable` / `readable` | 0 / 0 / 0 | — |
| All 10 clean controls (`{city-production,civilopedia,empire-stats,options-gameplay,tech-picker}__{de,en}__2400x1080__batch-37517e5f3dc66819__1862826555.png`) | 0 each | `readable` / `readable` / `readable` | 0 / 0 / 0 | — |
