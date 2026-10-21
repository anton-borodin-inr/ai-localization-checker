# Issue 48: pre-registered OCR comparison

Approved by Anton in chat on 2026-10-21, before any task OCR result.
The machine-readable grid, exact inputs and protected hashes are in
`protocol.json`. This protocol is committed before production changes or OCR.

| Preprocessing | Tesseract | EasyOCR |
| --- | --- | --- |
| Original PNG, unchanged | T0 (existing default) | E0 |
| RGB, exactly 2x Pillow LANCZOS | T1 | E1 |
| Previous variant, L grayscale, Otsu, no inversion | T2 | E2 |

Otsu maximizes between-class variance; the smallest threshold wins a tie.
Pixels strictly above the threshold become white. No crops, inversion,
spell correction, confidence cutoff, extra configurations or result-based
retries. Engine-native segmentation/order is retained. Upscaled boxes return
to original pixels using floor for minima and ceil for maxima, clipped to
the image. EasyOCR segments are not split into invented word boxes.

Tesseract retains OEM 1 / PSM 11, 30-second subprocess timeout, `eng` / `deu+eng`.
EasyOCR 1.7.2 uses CPU, CRAFT, standard recognition, `['en']` / `['de', 'en']`,
greedy decoding and the explicit version-1.7.2 parameters in the JSON.
`canvas_size=4800` avoids undoing the external 2x upscale. PyTorch uses one
thread; the EasyOCR image-operation watchdog is 300 seconds. Model downloads
are a separate setup step, disabled during measurement. Dependency versions,
model URLs, SHA-256 and the runtime platform are frozen before OCR.

Only seven named, hash-validated images may reach the OCR runner: the #8 trio
and four #41 pass-1 clean dev captures (two screens, EN/DE, build 1271045).
No directory discovery. Two serial passes, a fresh engine session per
configuration/pass: 84 image operations. Initialization is timed separately
from per-image preprocessing, OCR and adaptation. All failures are retained
as `not_checked`; failed coverage is unavailable, not zero. No retries based
on an OCR result. A corrected harness may replay stored OCR without new OCR.

Detection uses the unchanged matching/metrics modules, existing #8 labels and
the D-037 projection of the confirmed amended #10 reference. Report Mining
TP/FN and classification, all clean FP, checked/all recall, precision,
hallucinations and unavailable denominators. Distinguish observed Mining
text from a source-derived `missing` candidate. The reference's known gaps
remain explicit; OCR never supplies evaluation `screen_texts`.

Transcription uses unchanged `reading_metrics.coverage`: one reading per
native Tesseract line or EasyOCR segment, preserving text and union geometry,
without cross-widget concatenation. Report primary (16/20/20), section and
clipped-diagnostic coverage separately. Stage 2 has no reference or labels;
record only raw OCR, runtime and qualitative observations there.

Compare native output, adapted TSV, readings, findings and diagnostics across
passes; operational run IDs and timing are excluded. List every difference.
Consider checked coverage/stability, Mining detection and clean false
positives, transcription exact/fuzzy coverage, and runtime together. If these
trade off, report the tradeoff rather than introducing a new threshold or
forcing a universal winner. Any recommendation is preliminary and Proposed;
the final freeze awaits Stage 3 dev data and Anton's decision.

The default output remains baseline-v0.1. The test-only frozen v0 oracle is
committed first. Inventory/rendering/comparison, matching, metrics, schema,
goldens, labels, and #10 reference remain unchanged. No device operations,
provider calls, or changes in the #45/#47 capture/hook areas.
