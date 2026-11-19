# Stage 4: Baseline OCR Engine Selection on the Stage 3 Dev Set (D-045)

**Status:** Pre-registered selection rule and inventory contract recorded before any grid run. Results will be added after executing the six-configuration grid on `datasets/dev/`.

**Preliminary v1 scope caveat:** Results are preliminary (v1 dev set: 5 source screens, 2 languages, 34 PNGs, 33 human-confirmed labels; D-006, D-049, D-062). Hold-out screens (`~/l10n-holdout`) are never touched (D-010).

## Pre-registered Grid (D-045 / Issue #48)

Exact six configurations from `docs/evidence/48/protocol.json`, run for one pass over all 34 PNGs in `datasets/dev/` using unchanged frozen baseline v0.1 rules (`src/l10n_checker/baseline.py`) and unchanged D-026/D-029 matching/metrics:

| Preprocessing | Tesseract 5.5.2 (OEM 1 / PSM 11) | EasyOCR 1.7.2 (CPU, `torch_threads=1`) |
|---|---|---|
| Original PNG (`none`) | `T0` (current default) | `E0` |
| 2× LANCZOS (`upscale2x`) | `T1` | `E1` |
| 2× LANCZOS + grayscale/Otsu (`upscale2x-otsu`) | `T2` | `E2` |

Each screenshot is evaluated against its own build's translation tables (Unciv `b534a8a` plus that batch's patches from `fixtures/stage3/recipes-v1.json`, per D-030) and the reviewed screen inventories in `fixtures/baseline/`.

## Inventory Rule

Recorded in `fixtures/baseline/README.md`: an inventory holds translatable UI text that is at least partly readable on the clean dev screenshot in EN or DE; numbers and icons are excluded; the dimmed backdrop behind a modal popup (`options-gameplay` main menu) is excluded as not part of the screen under test. Only one slot across all five screens (`civilopedia` / `article-double-aqueducts`) is visible in one language only (EN; pushed below viewport in DE).

## Pre-registered Selection Rule (Approved by Anton Before Grid Runs)

Applied strictly in order across `T0, T1, T2, E0, E1, E2` on all 34 dev PNGs (33 labels, 10 clean controls):

1. **Completion gate:** Keep only configurations with `not_checked == 0` (if none achieve 0, keep those with the fewest `not_checked`).
2. **Primary metric — Detection `TP` (`recall_all`, D-026 type-free):** Let `TP_max` be the highest `TP` among surviving configurations. A meaningful difference on 33 labels is **≥ 2 labels (≥ 6.1 pp)**. Keep all surviving configurations with `TP >= TP_max - 1`; eliminate the rest.
3. **Tie-breaker 1 — Total False Positives (`FP`):** Among surviving configurations, let `FP_min` be the lowest total `FP`. A meaningful difference is **≥ 20% relative reduction AND ≥ 10 fewer FPs**. Keep all surviving configurations with `FP <= max(FP_min + 9, floor(FP_min / 0.8))`; eliminate the rest.
4. **Tie-breaker 2 — Simplicity and runtime:** Among remaining configurations, prefer no new dependency and simpler/faster preprocessing in the strict order: `T0 > T1 > T2 > E0 > E1 > E2`.

*(Clean-control FP, per-class recall, precision, observed vs `missing`-rule TP breakdown, and OCR time are reported alongside these metrics for transparency, while selection follows Steps 1–4 strictly as written.)*
