# Stage 2 qualitative observations

These four clean captures have no human labels or visible-text reference.
No detection metrics, transcription coverage or defect judgments were computed
for them. `checked` in their records means OCR completed, not that the screen
was checked for defects. Empty findings are placeholders for OCR-only records.

Examples below are spot observations and raw OCR excerpts, not a reference or
a denominator. Both passes have identical native output. The DE city image was
visually spot-checked against these excerpts; no labels were created.

| Config | City DE | City EN | Tech picker DE | Tech picker EN |
| --- | --- | --- | --- | --- |
| T0 | Misses the `Einheiten` heading and the left-list `Arbeiter`; reads the separate detail-panel occurrence. Gold icon merges into `160%` / `160.4`. | Word-level `Current construction`; top icon/stat row becomes `O462@05084018260`. | Emits icon-prefixed `©Bogenschießen`; no plain `Bergbau` token in this capture. | Includes `Research`, but no `Mining` token; icon/stat row mixes text and symbols. |
| T1 | Still lacks `Einheiten`; `Kaufen` and `160.4` are separate words. | Word-level heading; icon/stat row becomes `O4602058410102G@0`. | `©®Bogenschießen`; upscaling alone does not resolve this icon/text mixture. | Reads `Writing` and `Research`; no `Mining` token. |
| T2 | Reads `Einheiten` and both `Arbeiter` occurrences; purchase amount is `160.`. | Reads the word-level heading and `Queue empty`; icons/numbers still need care. | Now emits `Bergbau` as a separate token. | Emits `Mining` and `Research` separately. |
| E0 | Keeps `Einheiten`, both `Arbeiter` occurrences and multiword headers; purchase label is `Kaufen 160-`. | Multiword `Current construction` / `Queue empty`; separate `Raze` segment. | Reads `Bogenschießen erforschen`; Mining segment has trailing noise: `Bergbau _`. | Multiword technology names and separate `Mining` / `Research`. |
| E1 | Keeps heading and both Worker names; purchase label is `Kaufen 160`. | Multiword heading and separate `Raze`; segmentation differs from word-level Tesseract. | Reads `Bergbau` and `Bogenschießen erforschen`; `Bogenschießen ` carries trailing whitespace. | Reads `Mining` / `Research`; `Animal` and `Husbandry` are separate segments. |
| E2 | Keeps heading and both Worker names, but merges an icon into `Kaufen 1602`. | Emits multiword `Raze city` and `Queue empty`; icon/stat snippets remain mixed. | Emits `Bergbau` and `Bogenschießen erforschen`. | Emits `Mining`, but a research segment is `Research OArchery`, illustrating icon/text merging. |

These examples do not establish that E2 is best on these screens. The E2
recommendation uses the labelled trio, with the limitations in `report.md`.
Every Stage 2 runtime is in `runtime.md`; full native text, geometry and
confidence are in the corresponding OCR-only records. No OCR was run on the
other eight Stage 2 source screens.
