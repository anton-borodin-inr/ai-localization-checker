# Stage 4: Baseline OCR Engine Selection on the Stage 3 Dev Set (D-045)

**Result:** Applying the pre-registered selection rule as written selects **`T2` (Tesseract 5.5.2 + 2× LANCZOS + grayscale/Otsu)**, proposed as `D-063`. No new Python dependency is added (Pillow is already a project dependency).

**Important caveats (read before interpreting totals):**
- **Preliminary v1 dev set:** 5 source screens, 2 languages, 34 PNGs (24 mutated, 10 clean), 33 human-confirmed labels (D-006, D-049, D-062). Hold-out (`~/l10n-holdout`) was never read or run (D-010).
- **6 of 34 screens were `not_checked` (10 of 33 labels in `fn_on_not_checked`) across all 6 configurations:** frozen `unciv_text.py` raises `RenderingError: Unknown translated placeholder` on `[count]` and `[amount]`, failing all 4 broken-placeholder screens (`city-production` batch `e45e29bd` EN/DE; `tech-picker` `99984bb5` EN and `e46946a0` DE) plus the 2 opposite-language `tech-picker` screens in those same batches when `baseline.detect()` renders `foreign = tables[foreign_language].render(...)`. As a result, 0/4 `other` and 5/6 `truncated_text` labels sit on `not_checked` screens. Zero OCR failures or timeouts occurred.
- **`missing`-rule TP inversion:** Under D-030 (each build checked against its own `.properties`), `overflow` (6 labels) and `foreign_text` (12 labels) are present in the build's translation table. Reading them accurately yields an exact match (FN), whereas failing to read them emits a `missing` candidate carrying `expected` as `text_seen`, which scores a type-free detection TP under D-026/D-029. Thus `E0` achieved the lowest total FP (93), lowest clean-control FP (34), and highest observed-text TP (5 vs 4), yet scored lower total TP (12) than `T2` (16, 12 via `missing`) and `E2` (17, 13 via `missing`). Per the pre-registered contract, neither baseline rules nor the selection rule were altered after seeing results.

## Pre-registered Grid (D-045 / Issue #48)

Exact six configurations from `docs/evidence/48/protocol.json`, run for one serial pass over all 34 PNGs in `datasets/dev/` using unchanged frozen baseline v0.1 rules (`src/l10n_checker/baseline.py`) and unchanged D-026/D-029 matching/metrics (`run_id`: `stage4-ocr-20261119T181246Z`, commit `9460e13`, 0 provider requests, \$0):

| Preprocessing | Tesseract 5.5.2 (OEM 1 / PSM 11) | EasyOCR 1.7.2 (CPU, `torch_threads=1`) |
|---|---|---|
| Original PNG (`none`) | `T0` (prior default) | `E0` |
| 2× LANCZOS (`upscale2x`) | `T1` | `E1` |
| 2× LANCZOS + grayscale/Otsu (`upscale2x-otsu`) | `T2` (selected) | `E2` |

Each screenshot was evaluated against its own build's translation tables (Unciv `b534a8a` plus that batch's patches from `fixtures/stage3/recipes-v1.json`, per D-030) and the reviewed dev screen inventories in `fixtures/baseline/` (114 slots; inventory rule in `fixtures/baseline/README.md`).

## Pre-registered Selection Rule (Committed in `9460e13` Before Grid Runs)

Applied strictly in order across `T0, T1, T2, E0, E1, E2` on all 34 dev PNGs (33 labels, 10 clean controls):

1. **Completion gate:** Keep only configurations with `not_checked == 0` (if none achieve 0, keep those with the fewest `not_checked`).
2. **Primary metric — Detection `TP` (`recall_all`, D-026 type-free):** Let `TP_max` be the highest `TP` among surviving configurations. Meaningful difference on 33 labels: **≥ 2 labels (≥ 6.1 pp)**. Keep surviving configurations with `TP >= TP_max - 1`.
3. **Tie-breaker 1 — Total False Positives (`FP`):** Let `FP_min` be the lowest total `FP` among surviving configurations. Meaningful difference: **≥ 20% relative reduction AND ≥ 10 fewer FPs**. Keep surviving configurations with `FP <= max(FP_min + 9, floor(FP_min / 0.8))`.
4. **Tie-breaker 2 — Simplicity and runtime:** Strict preference order `T0 > T1 > T2 > E0 > E1 > E2`.

## Results (34 Dev PNGs, 33 Labels, 10 Clean Controls)

`FN` shows checked-screen FN plus the 10 labels on the 6 `not_checked` screens (`recall_all` counts all 33 labels; `recall_checked` counts the 23 labels on the 28 checked screens). Per-class recall is D-026 type-free detection recall over all labels of that class (`overflow` /6, `wrong_language` /17, `truncated_text` /6, `other` /4).

| Config | TP (obs / miss) | FP | FN (+NC) | Clean FP (10 PNGs) | Precision | Recall all / checked | `overflow` /6 | `wrong_lang` /17 | `truncated` /6 | `other` /4 | OCR time (34 PNGs) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `T0` | 14 (4 / 10) | 141 | 9 (+10) | 53 | 0.090 | 0.424 / 0.609 | 4 (0.67) | 10 (0.59) | 0 (0.00) | 0 (0.00) | 26.8 s |
| `T1` | 16 (4 / 12) | 155 | 7 (+10) | 61 | 0.094 | 0.485 / 0.696 | 5 (0.83) | 11 (0.65) | 0 (0.00) | 0 (0.00) | 49.5 s |
| **`T2`** | **16 (4 / 12)** | **120** | **7 (+10)** | **49** | **0.118** | **0.485 / 0.696** | **6 (1.00)** | **10 (0.59)** | **0 (0.00)** | **0 (0.00)** | **36.1 s** |
| `E0` | 12 (5 / 7) | 93 | 11 (+10) | 34 | 0.114 | 0.364 / 0.522 | 2 (0.33) | 9 (0.53) | 1 (0.17) | 0 (0.00) | 223.6 s (+6.8 s init) |
| `E1` | 12 (4 / 8) | 107 | 11 (+10) | 37 | 0.101 | 0.364 / 0.522 | 3 (0.50) | 9 (0.53) | 0 (0.00) | 0 (0.00) | 1071.5 s (+6.7 s init) |
| `E2` | 17 (4 / 13) | 107 | 6 (+10) | 42 | 0.137 | 0.515 / 0.739 | 6 (1.00) | 10 (0.59) | 1 (0.17) | 0 (0.00) | 1059.8 s (+6.2 s init) |

### Selection Rule Trace

1. **Gate:** All 6 configs have `not_checked == 6` → survivors: `T0, T1, T2, E0, E1, E2`.
2. **Primary (`TP >= TP_max - 1`):** `TP_max = 17` (`E2`), cutoff `>= 16` → survivors: `T1` (16), `T2` (16), `E2` (17). Eliminated: `T0` (14), `E0` (12), `E1` (12).
3. **Tie-breaker 1 (`FP <= max(FP_min + 9, floor(FP_min / 0.8))`):** `FP_min = 107` (`E2`), cutoff `<= 133` → survivors: `T2` (120; `E2`'s 13-FP edge is 10.8% < 20%), `E2` (107). Eliminated: `T1` (155; 31.0% worse than `E2`).
4. **Tie-breaker 2 (simplicity `T0 > T1 > T2 > E0 > E1 > E2`):** **`T2` wins** over `E2` (36.1 s vs 1066.0 s total, no PyTorch/EasyOCR dependency).

0 provider requests, \$0 API spend. Full per-image record: `data/runs/stage4-ocr-20261119T181246Z/run.json`.

## Follow-up Rerun After Literal Unknown-Placeholder Fix (`T2` Default, D-063)

`unciv_text.py` now keeps unknown translated placeholders verbatim (matching Unciv's `String.tr`) instead of raising `RenderingError`; detection rules, inventories, matching, metrics, goldens and `datasets/dev/` are unchanged (`run_id`: `stage4-t2-literal-placeholder-20261119T184046Z`, commit `13525f7`, 0 provider requests, \$0).

| `T2` Run | `not_checked` | TP (obs / miss) | FP | FN (+NC) | Clean FP | Precision | Recall all / checked | `overflow` /6 | `wrong_lang` /17 | `truncated` /6 | `other` /4 | OCR time |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Before (`stage4-ocr-20261119T181246Z`) | 6 | 16 (4 / 12) | 120 | 7 (+10) | 49 | 0.118 | 0.485 / 0.696 | 6 (1.00) | 10 (0.59) | 0 (0.00) | 0 (0.00) | 36.1 s |
| After (`stage4-t2-literal-placeholder-20261119T184046Z`) | **0** | **20 (5 / 15)** | **172** | **13 (+0)** | **49** | **0.104** | **0.606 / 0.606** | **6 (1.00)** | **10 (0.59)** | **1 (0.17)** | **3 (0.75)** | **35.0 s** |

All 28 previously checked screens are identical to `stage4-ocr-20261119T181246Z` across `status`, `findings`, `tp`, `fp`, `fn`, `duplicates` and `hallucinations` (0 diffs). The 6 previously `not_checked` screens are now `checked`:

| Screenshot | Status | TP (obs/miss) | FP | FN | Notable findings |
|---|---|---:|---:|---:|---|
| `city-production__de__…__batch-e45e29bd…__1887578114.png` | `checked` | 1 (0/1) | 2 | 0 | `missing` TP on `requires-population` (`Benötigt mindestens [count] Bevölkerung`); 2 FP (`settler-list`, `worker-description`) |
| `city-production__en__…__batch-e45e29bd…__1887578114.png` | `checked` | 1 (0/1) | 1 | 0 | `missing` TP on `requires-population` (`Requires at least [count] population`); 1 FP (`settler-list`) |
| `tech-picker__de__…__batch-99984bb5…__1869508724.png` | `checked` | 0 (0/0) | 13 | 2 | `prefix` findings on `mining` (`Bergbau und Erzgew`) and `masonry` (`Mauerarbeiten und S`) without trailing `…` miss D-029 threshold |
| `tech-picker__de__…__batch-e46946a0…__1892114822.png` | `checked` | 0 (0/0) | 10 | 2 | `literal_placeholder` (`other`) on `research` emitted `[amount]` (first matching span, below D-029 threshold for `[amount] erforschen`); `Minage` matched build table exactly (FN) |
| `tech-picker__en__…__batch-99984bb5…__1869508724.png` | `checked` | 1 (1/0) | 13 | 1 | `literal_placeholder` (`other`) observed TP on `research` (`Research [amount]`); `masonry` `prefix` (`Masonry and stone`) without `…` missed D-029 |
| `tech-picker__en__…__batch-e46946a0…__1892114822.png` | `checked` | 1 (0/1) | 13 | 1 | `missing` TP on `mining` (`Mining and ore extraction`); `construction` `prefix` (`Construction and civ`) without `…` missed D-029 |

0 provider requests, \$0 API spend. Full per-image record: `data/runs/stage4-t2-literal-placeholder-20261119T184046Z/run.json`.
