# Issue 12 Report — offline OCR baseline v0

**Weak slice result:** the baseline produces **15 false positives on German
clean and 14 on English clean**. It produces 12 candidates on German injected.
The Mining expectation is flagged as missing with empty `text_seen`: Tesseract
never recovered the visible Mining prefix. This is **not evidence of a
text-identifiable detection TP under D-026**. No matching, precision, recall or
vision-model comparison was run. Independent PR review and Anton's acceptance
remain pending. All candidates are retained, with no post-run tuning.

## What changed

Added `l10n-baseline`, using Tesseract and the existing CheckResult/Finding
schema. It resolves per-image versionCode through the pair manifest and reads
English/German translation files from the matching immutable fork commit with
`git show`. The source inventory supplies keys, runtime arguments and UI slots;
its expected text is rendered with square/curly templates, not read from human
labels. Full behavior, dependency reason, coverage and thresholds are in
[baseline.md](../../baseline.md). The baseline and this report generator never
open the final `*.labels.json` files. Clean-control status comes from Anton's
already published reviewed-screen table in [labeling.md](../../labeling.md).

### Frozen settings and reproducibility

- OEM 1, PSM 11; English `eng`, German `deu+eng`; 30 s per OCR subprocess.
- NFKC + case folding + whitespace collapse, exact match, no fuzzy tolerance.
- Proper prefix: at least 4 letters and 50% of normalized expected length.
- No OCR confidence cutoff, viewport exclusion, ellipsis exemption or allowlist.
- Observed confidence = mean OCR word confidence / 100; missing confidence =
  0.5 (heuristic). Missing `text_seen` is empty and uses the expected-slot centre.
- Literal placeholders -> other; known untranslated fallbacks/foreign text ->
  untranslated; otherwise prefix/missing -> truncated_text. Identical explicit
  translations are accepted. These are detector rules, not D-026 matching.

Settings, detector and inventory were committed **before slice OCR** in
`05032f86711bfc9b905c4a736dae4ee10ce810c2`.
The executed code is `9abdbcb30c760b2d8b0b70ede6d6adb2e3d572e0`;
its only later change is the baseline CLI output-path guard and regression test.
The three records below were copied byte for byte from `data/baseline-runs/`.

Tesseract was **5.5.2**, with these traineddata SHA-256 values:

- eng: `7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2`
- deu: `19d219bbb6672c869d20a9636c6816a81eb9a71796cb93ebe0cb1530e2cdb22d`

Source pairing:

| Screenshot | versionCode | Fork commit | Mining expectation |
|---|---:|---|---|
| German clean | 1271001 | `2e4d6af664e204c4ddcc06383a0e2e700a9665c4` | Bergbau |
| German injected | 1271002 | `038329f93966a8d1d0ac7f23f551c98feb32614c` | Bergbau und Erzgewinnung |
| English clean | 1271001 | `2e4d6af664e204c4ddcc06383a0e2e700a9665c4` | Mining |

Each run records the source-file, inventory, manifest and screenshot hashes.
It also retains raw OCR TSV, the source entries used, per-slot resolved text,
rule decisions and the unchanged CheckResult shape. Source versionCode,
language, PNG dimensions and PNG hash are independently checked before OCR.

## How it was verified

Final checks are recorded below after execution. The device check is not run:
this task changes neither capture nor device code. The existing device test
is skipped by default and needs a prepared emulator (`--run-device`). All
baseline tests and OCR runs are offline and need no emulator.

| Command | Actual result |
|---|---|
| `uv sync --offline` | exit 0 after retry with cache access; initial sandbox cache initialization failed |
| `uv sync --offline --no-editable --reinstall-package ai-localization-checker` | exit 0; regular package install for standalone CLI |
| `uv run pytest` | exit 0; 248 passed, 1 skipped (device), 1 third-party SDK deprecation warning |
| `uv run ruff check .` | exit 0; all checks passed |
| `uv run ruff format --check .` | exit 0; 41 files already formatted |
| `uv run --offline --no-editable python scripts/baseline_ocr_smoke.py` | exit 0; Mining, Bergbau and Straße Größe recognized exactly |
| `git diff --check` | exit 0 |
| `git diff --cached --check` | exit 0 after declaring raw TSV's empty final column in .gitattributes |
| `uv run pytest --run-device` | not run; no capture/device changes |

Synthetic fixtures cover English/German, umlauts and sharp s. Unit tests use
controlled OCR output and temporary Git source builds; they check build-specific
strings despite a dirty fork working tree, template composition/reordering,
proper/missing prefixes, foreign alternatives and raw-key fallback, placeholder
classification, bounding-box-centre regions, retained viewport/ellipsis
candidates, failures, label-file isolation and CLI behavior. Real OCR is checked
separately on the committed English/German synthetic PNGs, including `Straße
Größe`, without adding Pillow to project dependencies.

### Executed screenshot commands

All three invocations used the following command, replacing `<image>` with the
exact filename in the next table and `<fork>` with the existing separate local
Unciv fork path. The host fork path is editorially abbreviated here; flags and
input files are unchanged. No recapture, rebuild, device call or provider call
was involved.

```bash
uv run --offline --no-editable l10n-baseline \
  --image docs/evidence/8/final/<image> \
  --manifest docs/evidence/8/pair-manifest.json \
  --inventory docs/evidence/12/tech-picker.json \
  --unciv-fork <fork>
```

| Run id | Image | Status / exit | Findings | Detector elapsed s | Provider requests |
|---|---|---|---:|---:|---:|
| [20261019T155103Z-47dbbd](records/20261019T155103Z-47dbbd/result.json) | `tech-picker__de__2400x1080__clean__1271001.png` | checked / 0 | 15 | 0.853 | 0 |
| [20261019T155117Z-7e8171](records/20261019T155117Z-7e8171/result.json) | `tech-picker__de__2400x1080__injected__1271002.png` | checked / 0 | 12 | 0.871 | 0 |
| [20261019T155118Z-659d65](records/20261019T155118Z-659d65/result.json) | `tech-picker__en__2400x1080__clean__1271001.png` | checked / 0 | 14 | 0.527 | 0 |

### Every finding, without suppression

Empty `text_seen` below means that no identifying OCR span met the rule; it
never substitutes the expected string for observed text. All rows have type
`truncated_text`. Confidence is rounded to six decimals here; JSON retains the
original number. **Every row on either clean control is a false positive.**
Injected-screen candidates are listed in full, without assigning evaluation
TP/FP status: that requires the D-026 matcher owned by issue #13.

#### `tech-picker__de__2400x1080__clean__1271001.png`

| Slot | Expected text | Rule | text_seen | Region | Confidence |
|---|---|---|---|---|---:|
| writing | Schrift | missing | (empty) | top | 0.500000 |
| agriculture | Landwirtschaft | missing | (empty) | top-left | 0.500000 |
| animal-husbandry | Tierhaltung | missing | (empty) | top | 0.500000 |
| archery | Bogenschießen | missing | (empty) | center | 0.500000 |
| mining | Bergbau | missing | (empty) | center | 0.500000 |
| masonry | Mauerarbeiten | missing | (empty) | center | 0.500000 |
| bronze-working | Bronzebearbeitung | missing | (empty) | bottom | 0.500000 |
| horseback-riding | Reiten | missing | (empty) | top-right | 0.500000 |
| research | Bogenschießen erforschen | missing | (empty) | bottom-right | 0.500000 |
| archer | Bogenschütze | missing | (empty) | bottom | 0.500000 |
| wonder-name | Tempel der Artemis | missing | (empty) | bottom | 0.500000 |
| wonder-culture | Kultur | missing | (empty) | bottom | 0.500000 |
| wonder-food | +10% Nahrung in allen Städten | missing | (empty) | bottom | 0.500000 |
| wonder-archery-production | +15% Produktion beim Bau von Bogenschießen Einheiten in dieser Stadt | missing | (empty) | bottom | 0.500000 |
| wonder-ranged-production | +15% Produktion beim Bau von Schießpulver-Fernkampf Einheiten in dieser Stadt | missing | (empty) | bottom | 0.500000 |

[All slot decisions](records/20261019T155103Z-47dbbd/diagnostics.json), [raw OCR](records/20261019T155103Z-47dbbd/ocr.tsv), [used source entries](records/20261019T155103Z-47dbbd/source-entries.json).

#### `tech-picker__de__2400x1080__injected__1271002.png`

| Slot | Expected text | Rule | text_seen | Region | Confidence |
|---|---|---|---|---|---:|
| writing | Schrift | missing | (empty) | top | 0.500000 |
| agriculture | Landwirtschaft | missing | (empty) | top-left | 0.500000 |
| animal-husbandry | Tierhaltung | missing | (empty) | top | 0.500000 |
| archery | Bogenschießen | missing | (empty) | center | 0.500000 |
| mining | Bergbau und Erzgewinnung | missing | (empty) | center | 0.500000 |
| research | Bogenschießen erforschen | missing | (empty) | bottom-right | 0.500000 |
| archer | Bogenschütze | missing | (empty) | bottom | 0.500000 |
| wonder-name | Tempel der Artemis | missing | (empty) | bottom | 0.500000 |
| wonder-culture | Kultur | missing | (empty) | bottom | 0.500000 |
| wonder-food | +10% Nahrung in allen Städten | missing | (empty) | bottom | 0.500000 |
| wonder-archery-production | +15% Produktion beim Bau von Bogenschießen Einheiten in dieser Stadt | missing | (empty) | bottom | 0.500000 |
| wonder-ranged-production | +15% Produktion beim Bau von Schießpulver-Fernkampf Einheiten in dieser Stadt | missing | (empty) | bottom | 0.500000 |

[All slot decisions](records/20261019T155117Z-7e8171/diagnostics.json), [raw OCR](records/20261019T155117Z-7e8171/ocr.tsv), [used source entries](records/20261019T155117Z-7e8171/source-entries.json).

#### `tech-picker__en__2400x1080__clean__1271001.png`

| Slot | Expected text | Rule | text_seen | Region | Confidence |
|---|---|---|---|---|---:|
| writing | Writing | missing | (empty) | top | 0.500000 |
| agriculture | Agriculture | missing | (empty) | top-left | 0.500000 |
| animal-husbandry | Animal Husbandry | missing | (empty) | top | 0.500000 |
| archery | Archery | missing | (empty) | center | 0.500000 |
| mining | Mining | missing | (empty) | center | 0.500000 |
| research | Research Archery | prefix | `Research` | bottom-right | 0.933007 |
| units-header | Units enabled: | prefix | `Units enabled` | bottom-left | 0.965067 |
| archer | Archer | missing | (empty) | bottom | 0.500000 |
| wonders-header | Wonders enabled: | prefix | `Wonders enabled` | bottom-left | 0.961966 |
| wonder-name | Temple of Artemis | missing | (empty) | bottom | 0.500000 |
| wonder-culture | Culture | missing | (empty) | bottom | 0.500000 |
| wonder-food | +10% Food in all cities | missing | (empty) | bottom | 0.500000 |
| wonder-archery-production | +15% Production when constructing Archery units in this city | prefix | `+15% Production when constructing Archery units in this` | bottom | 0.854629 |
| wonder-ranged-production | +15% Production when constructing Ranged Gunpowder units in this city | missing | (empty) | bottom | 0.500000 |

[All slot decisions](records/20261019T155118Z-659d65/diagnostics.json), [raw OCR](records/20261019T155118Z-659d65/ocr.tsv), [used source entries](records/20261019T155118Z-659d65/source-entries.json).

### Interpretation and limits

The frozen sparse-text OCR frequently groups coloured technology buttons and
icons as non-text or misreads their titles. The raw German injected TSV contains
no usable `Bergbau` prefix. Several other perfectly readable titles are also
missed. This explains many false positives and the empty Mining evidence;
there is no claim that the injected defect was successfully matched.

The clean English prefixes `Units enabled` and `Wonders enabled` lose only a
colon, and `Research` is missing its icon-adjacent technology name in OCR. These
are retained false positives of the strict textual rule. The description has
icon-adjacent text, a clipped continuation and source fragments extending below
the viewport; they also remain candidates. The full expected continuation is
not shortened to what happens to be visible. D-025 excludes scroll clipping
from human defects; D-023 excludes a shortened label when its full text is
visible elsewhere. The baseline implements neither contextual exemption.

Slots are manually declared UI search areas, not labels or automatic layout
recognition. Missing findings have no observed box/text and cannot be treated
as text-identifiable D-026 matches. Arbitrary foreign languages, arbitrary raw
identifiers, wrong runtime substitutions, icon correctness and numeric stats
are not covered. This is a reproducible, weak v0 reference, not evidence of
vision-model superiority or measured QA benefit.

### Failed attempts and corrections

- Initial `uv sync --offline` inside the sandbox could not initialize the shared
  uv cache. The same offline command succeeded with cache access.
- The first focused pytest invocation failed collection because `request` is a
  reserved pytest parameter name. Renaming the test parameter fixed collection;
  no assertion or expected value was weakened.
- The first synthetic smoke command using the editable package failed with
  `ModuleNotFoundError`. A regular local package install resolved it. This is
  consistent with the already documented D-019 editable-import limitation; its
  original hidden-file cause was not reinvestigated here.
- The first baseline CLI invocation then failed **before OCR** because reusing
  capture's output-directory helper anchored `data/` to the installed package.
  The baseline now anchors output to the invoking checkout, with a regression
  test including symlink escape. Capture code is unchanged. No run directory
  or screenshot OCR record was produced by this failed invocation.
- No screenshot run was discarded or retried. No detector setting, prefix
  threshold or source-inventory slot changed after seeing slice OCR output.
- The first staged `git diff --cached --check` rejected trailing tabs on raw
  Tesseract layout rows. These tabs encode the required empty final text
  column, not editable source whitespace. A narrowly scoped `.gitattributes`
  entry declares that raw TSV convention; the original bytes are preserved
  and ordinary source whitespace checks remain enabled. No test was changed.

## Deviations from the task

The standalone command uses `--no-editable` for the existing host import
limitation, and the new CLI has its own checkout-relative output guard. Both
are implementation accommodations; capture behavior is unchanged. The renderer
is explicitly the slice subset, not a port of Unciv. No scope expansion into
matching, evaluation, overlap heuristics, new mutations or live inference.

The raw-TSV whitespace attribute is a storage-format accommodation for exact
machine output, scoped to the committed issue-12 OCR evidence only.

## Decisions proposed

[D-030](../../decisions.md#d-030--offline-baseline-v0-source-context-and-frozen-comparison-rules):
per-build source context, source-backed screen inventory, fixed OCR/comparison
settings and failure/evidence behavior. Status remains **Proposed** for review;
Accepted D-003/D-013/D-018/D-021/D-023/D-025/D-026/D-027 are preserved.

## Open questions for Anton

- Review D-030 and the declared inventory/coverage. The implementation follows
  the approved plan; retaining these defaults for later stages is a separate
  methodological decision, not a claim that these slice results are good.
- Perform independent PR review and final acceptance. No precision/recall or
  claim of model advantage is available from this task.

## API usage

**0 live provider calls, 0 provider requests sent, no API spend.** Each of the
three baseline records has `requests_sent: 0`. No key or `.env` was read. No
hold-out data was accessed. GitHub reads/push/PR management are repository
operations, not inference calls.

## Every changed file

- `.gitattributes`
- `docs/baseline.md`
- `docs/decisions.md`
- `docs/evidence/12/records/20261019T155103Z-47dbbd/diagnostics.json`
- `docs/evidence/12/records/20261019T155103Z-47dbbd/ocr.tsv`
- `docs/evidence/12/records/20261019T155103Z-47dbbd/result.json`
- `docs/evidence/12/records/20261019T155103Z-47dbbd/run.json`
- `docs/evidence/12/records/20261019T155103Z-47dbbd/source-entries.json`
- `docs/evidence/12/records/20261019T155117Z-7e8171/diagnostics.json`
- `docs/evidence/12/records/20261019T155117Z-7e8171/ocr.tsv`
- `docs/evidence/12/records/20261019T155117Z-7e8171/result.json`
- `docs/evidence/12/records/20261019T155117Z-7e8171/run.json`
- `docs/evidence/12/records/20261019T155117Z-7e8171/source-entries.json`
- `docs/evidence/12/records/20261019T155118Z-659d65/diagnostics.json`
- `docs/evidence/12/records/20261019T155118Z-659d65/ocr.tsv`
- `docs/evidence/12/records/20261019T155118Z-659d65/result.json`
- `docs/evidence/12/records/20261019T155118Z-659d65/run.json`
- `docs/evidence/12/records/20261019T155118Z-659d65/source-entries.json`
- `docs/evidence/12/report.md`
- `docs/evidence/12/run-index.json`
- `docs/evidence/12/tech-picker.json`
- `pyproject.toml`
- `scripts/baseline_ocr_smoke.py`
- `src/l10n_checker/baseline.py`
- `src/l10n_checker/baseline_cli.py`
- `src/l10n_checker/unciv_text.py`
- `tests/fixtures/ocr/README.md`
- `tests/fixtures/ocr/de-prefix.png`
- `tests/fixtures/ocr/de-umlauts.png`
- `tests/fixtures/ocr/de.png`
- `tests/fixtures/ocr/en.png`
- `tests/fixtures/ocr/placeholder.png`
- `tests/fixtures/ocr/texts.json`
- `tests/test_baseline.py`
- `tests/test_baseline_cli.py`
- `tests/test_unciv_text.py`
