# Synthetic OCR fixtures

These 960 x 200 PNGs contain the strings in `texts.json`, drawn in black on
white at (40, 60), Arial 48 px. They are implementation test inputs, not human
labels or Unciv screenshots. They were generated once with Pillow from the
Codex bundled runtime and macOS's Arial.ttf; Pillow is not a project or test
runtime dependency. The committed image bytes are the reproducible inputs.

The unit tests use controlled TSV outputs; the separate OCR smoke command
actually recognizes `en.png`, `de.png` and `de-umlauts.png` with Tesseract.
