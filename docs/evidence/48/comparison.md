# Preliminary OCR comparison

Three labelled images from one source screen; four qualitative-only images.

| Config | Pass | TP / FP / FN | Clean FP | Exact /56 | Fuzzy /56 | Coverage images | 7-image seconds | Init seconds |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| T0 | 1 | 1 / 40 / 0 | 29 | 35 | 39 | 3/3 | 4.947 | 0.000 |
| T0 | 2 | 1 / 40 / 0 | 29 | 35 | 39 | 3/3 | 4.669 | 0.000 |
| T1 | 1 | 1 / 40 / 0 | 29 | 35 | 40 | 3/3 | 9.713 | 0.000 |
| T1 | 2 | 1 / 40 / 0 | 29 | 35 | 40 | 3/3 | 9.866 | 0.000 |
| T2 | 1 | 1 / 35 / 0 | 25 | 37 | 45 | 3/3 | 7.326 | 0.000 |
| T2 | 2 | 1 / 35 / 0 | 25 | 37 | 45 | 3/3 | 7.108 | 0.000 |
| E0 | 1 | 0 / 29 / 1 | 18 | 45 | 47 | 3/3 | 51.007 | 9.886 |
| E0 | 2 | 0 / 29 / 1 | 18 | 45 | 47 | 3/3 | 61.712 | 7.111 |
| E1 | 1 | 0 / 26 / 1 | 16 | 47 | 50 | 3/3 | 256.919 | 7.679 |
| E1 | 2 | 0 / 26 / 1 | 16 | 47 | 50 | 3/3 | 260.135 | 6.844 |
| E2 | 1 | 1 / 26 / 0 | 18 | 45 | 49 | 3/3 | 234.425 | 7.150 |
| E2 | 2 | 1 / 26 / 0 | 18 | 45 | 49 | 3/3 | 242.530 | 7.963 |

Failed transcription is unavailable; counts above cover only available images.
Primary denominators are 16/20/20. Clipped diagnostics remain separate in summary.json.

Repeat differences: 0/42 image/configuration pairs.

D-037: #10 is not an exhaustive occurrence map; supplied clipped/numeric diagnostics only, no OCR-derived additions. Hallucination counts inherit its gaps.

Per-image metrics, all findings, Mining rules, coverage matches and runtime: summary.json.
No Stage 2 detection metrics or coverage were computed. API requests/spend: 0.
