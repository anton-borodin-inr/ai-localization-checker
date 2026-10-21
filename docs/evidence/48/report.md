# Issue 48 report

**Preliminary:** three labelled images from one source screen, with one labelled defect. E2 is a proposed OCR candidate, not an accepted default. Its Mining TP is a source-derived `missing` candidate, so this does not establish successful OCR of the injected label or measured QA time savings.

## What changed

- Added EasyOCR 1.7.2 as the only new direct dependency; locked its transitive dependencies, including PyTorch 2.14.1 and torchvision 0.29.1. Model URLs and SHA-256, Tesseract 5.5.2 traineddata hashes, Python and platform are recorded in `environment.json`.
- Added explicit `--ocr-engine` / `--ocr-preprocess` selection and an offline comparison/replay command. The default remains Tesseract, no preprocessing, baseline-v0.1.
- Kept native EasyOCR segments and confidence, native Tesseract TSV, deterministic preprocessing provenance and original-screen coordinates. No spelling correction, confidence cutoff, invented word boxes or screen-specific fix.
- Committed the six-configuration protocol and frozen v0 oracle before implementation (`2cb4c56`); implemented the adapters (`f526487`); committed runtime/model provenance before OCR (`ddeefab`).

## Results

Both passes produced the same counts below. They are repeated runs, not six independent labelled images. Exact/fuzzy are D-033 primary transcription counts out of 56 units (16/20/20), not defect recall.

| Config | TP / FP / FN | Clean FP | Precision | Recall checked / all | Exact /56 | Fuzzy /56 | Seven-image OCR seconds, passes 1 / 2 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| T0 | 1 / 40 / 0 | 29 | 0.0244 | 1.0 / 1.0 | 35 | 39 | 4.947 / 4.669 |
| T1 | 1 / 40 / 0 | 29 | 0.0244 | 1.0 / 1.0 | 35 | 40 | 9.713 / 9.866 |
| T2 | 1 / 35 / 0 | 25 | 0.0278 | 1.0 / 1.0 | 37 | 45 | 7.326 / 7.108 |
| E0 | 0 / 29 / 1 | 18 | 0.0000 | 0.0 / 0.0 | 45 | 47 | 51.007 / 61.712 |
| E1 | 0 / 26 / 1 | 16 | 0.0000 | 0.0 / 0.0 | 47 | 50 | 256.919 / 260.135 |
| E2 | 1 / 26 / 0 | 18 | 0.0370 | 1.0 / 1.0 | 45 | 49 | 234.425 / 242.530 |

T0/T1/T2 = Tesseract; E0/E1/E2 = EasyOCR. Suffix 0 = original; 1 = 2x LANCZOS; 2 = 2x LANCZOS + grayscale/Otsu. The full fixed settings are in `protocol.json`.

All **84/84 operations were checked**, with no timeout or engine failure. Native OCR, adapted TSV, readings, findings and diagnostics were identical in **42/42 repeat pairs**, excluding operational run IDs and timing. No configuration or parameter was added after results.

E2 is the proposed provisional baseline v1 OCR candidate: compared with T0 it has fewer total/clean FP, better primary reading coverage and the same scored Mining recall. It reads `Bergbau` and `Mining` on the labelled clean controls, where Tesseract missed them. However, its injected Mining TP comes from expected source text under `missing`, not from reading the truncation. E0/E1 instead emitted the observed prefix `Bergbau und Erzgew` without an ellipsis; the unchanged D-029 matching rejected it, preserving one FN and the corresponding unmatched finding. No manual TP override was made.

E1 has the best primary reading counts and the lowest clean FP, but retains that FN. E2 is therefore not a winner on every measure. Its seven-image operations took 234.425–242.530 seconds plus 7.150–7.963 seconds of Reader initialization; T0 took 4.669–4.947 seconds. These are observed host runtimes, not an isolated or resource-normalized benchmark. The final freeze awaits the Stage 3 dev set and Anton's decision.

Each configuration has six scorer-reported hallucinations per pass and no collapsed duplicates. These counts inherit the known incomplete #10 occurrence reference; they are not new human hallucination labels. A matched Mining finding is classified as `truncated_text`. There are no labelled `untranslated` positives in this trio, so its recall is not established.

Detailed evidence:

- `comparison.md`: both passes, initialization and totals.
- `summary.json`: all per-image results, matching indices/confusion, coverage matches, runtime and repeat fingerprints.
- `clean-findings.md`: every clean-image FP from both passes, including the rule and source-derived missing text.
- `transcription.md`: primary, section and clipped-diagnostic coverage.
- `runtime.md`: every image/configuration/pass runtime.
- `qualitative.md`: Stage 2 spot observations, without metrics or labels.
- `operations.json`, `record-index.json`, `records/`: complete operation ledger and hash-indexed raw records.

## Data and unchanged contracts

OCR processed only the exact seven named PNGs in `protocol.json`: the #8 trio and four #41 pass-1 clean captures of tech-picker/city-production, EN/DE, build 1271045. The other eight Stage 2 source screens were never processed. The four copied dev inputs were validated against #41 hashes. Stage 2 `checked` means OCR completed; no defect checks, transcription coverage or labels were inferred for those captures.

Inventory, source rendering, normalization, D-030 comparison rules, matching, metrics, schema, goldens, labels and the #10 reference are unchanged and hash-checked. The amended reference SHA-256 remains `bba4e51d48d81bfa836eb80632697069b4e70fd67944a09f93d71aada609dd19`. D-037 visible rows and supplied numeric diagnostics remain the sole evaluation screen texts; OCR never fills reference gaps. The reference is not an exhaustive occurrence map.

No capture/hook/Unciv source changes, emulator operations or provider calls were made. The parallel #45/#47 areas are untouched. The top-level baseline settings retain the v0 record structure; actual selected OCR parameters/provenance are recorded under `metadata.ocr` and in the fixed protocol.

## How it was verified

- `uv run --offline pytest -q -rs`: **1481 passed, 2 skipped**, exit 0. Only `test_capture_device.py` and `test_hook_device.py` were skipped because they require a prepared emulator; this task has no device phase. Full output: `pytest.txt`.
- The frozen-v0 suite passed all six tests. On all six real T0 trio records, identical TSV/provenance replay produced byte-identical `result.json`, `run.json`, `diagnostics.json`, `source-entries.json` and `ocr.tsv` for both the current default and oracle, with run ID/timing fixed to the recorded values. This used no OCR or source checkout during testing.
- `uv run --offline --no-editable python -m l10n_checker.ocr_experiment summarize`: exit 0; **86 derived files** (summary, comparison and 84 reading files) were byte-identical after replay. No OCR/model load/network call. See `replay-verification.json`.
- `uv run --offline --no-editable l10n-baseline --help`: exit 0; installed CLI exposes both selectors. See `cli-help.txt`.
- `uv run --offline ruff check .`, `uv run --offline ruff format --check .`, and `git diff --check`: final results are recorded in `ruff.txt`, `format.txt`, and `diff-check.txt`.

## Reproduction

From the repository root, with the exact source fork commits from the pair manifest available locally:

```bash
uv sync --locked
uv run --no-editable python -m l10n_checker.ocr_experiment prepare-models
uv run --no-editable python -m l10n_checker.ocr_experiment summarize
```

The last command reproduces the reported numbers from committed raw OCR without another image operation. To run fresh E2 OCR on exactly the trio and print the matching/coverage numbers automatically:

```bash
uv run --no-editable python -m l10n_checker.ocr_recheck \
  --unciv-fork /path/to/Unciv
```

Expected counts on the recorded setup: TP/FP/FN = 1/26/0, clean FP = 18, primary exact/fuzzy = 45/56 and 49/56. This helper was added after the fixed experiment and tested with saved-output replay only; it made no additional OCR calls in this task. It reuses the existing scorer and pre-registered E2, with no configuration change. It writes a fresh bundle under `data/issue-48-rechecks/`.

The equivalent lower-level baseline commands are:

```bash
for image in \
  tech-picker__de__2400x1080__clean__1271001.png \
  tech-picker__de__2400x1080__injected__1271002.png \
  tech-picker__en__2400x1080__clean__1271001.png
do
  uv run --no-editable l10n-baseline \
    --image "docs/evidence/8/final/$image" \
    --manifest docs/evidence/8/pair-manifest.json \
    --inventory docs/evidence/12/tech-picker.json \
    --unciv-fork /path/to/Unciv \
    --ocr-engine easyocr --ocr-preprocess upscale2x-otsu
done
```

Those future reruns are not included in this task's 84 operations. Rerun quality numbers are obtained by the unchanged evaluator with the same labels/reference; runtime depends on host conditions. `summarize` is the complete, no-OCR reproduction of the committed table.

## Deviations from the task

None in the grid, data boundary or methodology. Initial network-restricted clone/dependency downloads failed DNS and were repeated with network authorization. Setup emitted upstream PyTorch quantization/pin-memory warnings, retained in the logs; inference completed without failures or parameter changes. No new direct dependency beyond the approved EasyOCR was added.

Every changed repository file is listed in `changed-files.txt`. The frozen oracle is intentionally retained as a test-only independent reference. Existing Tesseract support and its smoke script remain because T0 is the unchanged default; no replacement made them unused.

## Decisions proposed

`D-0XX — Preliminary baseline v1 OCR candidate from the fixed dev comparison`, appended to `docs/decisions.md`. It proposes E2 and would supersede only D-030's OCR part upon acceptance. D-030's existing entry/status and all comparison rules remain untouched. The placeholder avoids number collisions with #45/#47; assign a number against main before merge.

## Open questions for Anton

Accept or reject the preliminary E2 recommendation, considering its runtime and source-derived Mining TP. The default is unchanged regardless. Independent review and Anton's acceptance remain pending; the author has not approved or merged this work.

## API usage

**0 provider requests, USD 0.00.** Dependency/model downloads were setup only, separate from OCR. Every inference used local weights with downloads disabled. No `.env` or secret value was read or printed.
