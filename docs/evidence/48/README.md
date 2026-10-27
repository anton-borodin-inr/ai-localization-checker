# Issue 48: Tesseract vs EasyOCR on dev data (summary)

**Preliminary.** Three labelled images from one source screen (the #8 tech-picker trio) plus four qualitative-only Stage 2 dev captures. One labelled defect (Mining truncation). This cannot settle the engine choice; it only ranks candidates for Stage 4.

Only the conclusion is kept in `main`. The comparison harness, the EasyOCR adapter, the frozen v0 oracle and all raw OCR records stay on the archive branch `feat/48-ocr-comparison` at [`c1c2a7e`](https://github.com/anton-borodin-inr/ai-localization-checker/blob/c1c2a7ef2e69aef7723dc67a43535416a0e360ff/docs/evidence/48/report.md) (PR #50, closed without merging). The pre-registered grid is [protocol.json](protocol.json); package versions and model weight hashes are in [environment.json](environment.json); per-configuration totals and the repeat check are in [totals.json](totals.json).

## Grid

| Preprocessing | Tesseract (OEM 1 / PSM 11) | EasyOCR 1.7.2 (CPU) |
|---|---|---|
| Original PNG | T0 (current default) | E0 |
| 2x LANCZOS | T1 | E1 |
| 2x LANCZOS + grayscale/Otsu | T2 | E2 |

## Results

Both passes gave identical outputs for all 42 image/configuration pairs. Detection uses the unchanged D-026 matching on the #8 trio; coverage is D-033 primary transcription against the #10 reference (56 units).

| Config | TP / FP / FN | FP on clean image | Coverage exact /56 | Coverage fuzzy /56 | OCR time, 7 images |
|---|---|---|---|---|---|
| T0 | 1 / 40 / 0 | 29 | 35 | 39 | ~5 s |
| T1 | 1 / 40 / 0 | 29 | 35 | 40 | ~10 s |
| T2 | 1 / 35 / 0 | 25 | 37 | 45 | ~7 s |
| E0 | 0 / 29 / 1 | 18 | 45 | 47 | ~55 s + ~8 s init |
| E1 | 0 / 26 / 1 | 16 | 47 | 50 | ~260 s + ~7 s init |
| E2 | 1 / 26 / 0 | 18 | 45 | 49 | ~240 s + ~8 s init |

## Conclusion

- EasyOCR reads clearly more of the screen (45–47 vs 35 exact units) and produces fewer false positives (26–29 vs 35–40) than Tesseract, at 10–50x the runtime and with PyTorch as a dependency.
- No configuration reads the Mining ellipsis reliably. E2's TP comes from a source-derived `missing` candidate, not from OCR of the truncated text; E0/E1 read the prefix without the ellipsis and are scored FN by the unchanged matching. The detection column therefore does not separate the engines; coverage and false positives do.
- Every configuration has very low precision (at most 0.04) on this trio. The baseline is noisy regardless of the engine.
- The decision is recorded as D-045: Tesseract T0 stays the baseline default for now; EasyOCR is the leading candidate, and the engine and preprocessing are chosen at Stage 4 on the Stage 3 dev set.

0 provider requests, USD 0.
