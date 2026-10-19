# Offline baseline v0

Issue #12. This is a detector over previously captured PNGs, not a capture or
evaluation command (D-003). It returns the existing `CheckResult` / `Finding`
schema. No provider, API key, human label file, emulator or network is needed.

## Dependency and command

**Dependency reason:** Tesseract supplies offline OCR with English and German
language models, word boxes and confidence through its CLI, without a Python
wrapper dependency. Install Tesseract 5 and the `eng` / `deu` traineddata files
before use; the command never downloads models. On Homebrew these are
`tesseract` and `tesseract-lang`. Existing local verification found version
5.5.2 with both models installed. See the official [CLI documentation].

From the checker repository root, supply a separate local Unciv fork containing
both commits recorded in `docs/evidence/8/pair-manifest.json`:

```bash
uv run --no-editable l10n-baseline \
  --image docs/evidence/8/final/tech-picker__de__2400x1080__injected__1271002.png \
  --manifest docs/evidence/8/pair-manifest.json \
  --inventory docs/evidence/12/tech-picker.json \
  --unciv-fork /path/to/Unciv
```

Repeat with each of the two clean PNGs. Outputs go to a fresh
`data/baseline-runs/<run-id>/`. Exit status: 0 checked, 2 not checked, 1 unable
to record a run. A checked result may contain findings.

`--no-editable` avoids the host's known editable-import issue (D-019). It
installs the local package normally; it changes neither dependencies nor
Python support. After changes, sync again before a `--no-sync` verification.

## Frozen v0 rules

These settings and the screen inventory are fixed before the first real slice
run. They are not selected by looking at the clean-screen false positives.

- Tesseract LSTM `--oem 1 --psm 11` (sparse UI text); `eng` for English,
  `deu+eng` for German, in that order. Timeout: 30 seconds per subprocess.
- NFKC, case folding and whitespace collapse for comparison. No edit-distance
  tolerance, spell correction, confidence cutoff or screen-specific OCR fix.
  The original OCR text is retained in findings and TSV.
- Search contiguous word spans inside each declared widget slot, including
  wrapped lines. A full normalized match satisfies that expectation.
- A proper prefix needs at least four alphabetic characters and at least 50%
  of the full normalized expected length. Terminal `...` / `…` is removed
  only for this prefix comparison; its original text stays in the finding.
  Prefix or absent expectation gives a `truncated_text` candidate.
- A recognized literal `[placeholder]` gives `other` (D-027). Otherwise an
  exact source-language fallback for a missing German translation gives
  `untranslated`; an exact known alternative in the other configured language
  also gives `untranslated` if it differs from the expected string. An
  explicitly identical translation is accepted. Unknown OCR words alone are
  not evidence of another language. Rule priority is placeholder, source
  fallback, expected exact match, foreign alternative, prefix, missing.
- Observed candidates use mean OCR word confidence divided by 100, not a
  calibrated probability. A missing candidate uses heuristic confidence 0.5
  and empty `text_seen`; its expected string is in diagnostics, never invented
  as observed text. Region comes from the observed union-box centre, or the
  declared expected-slot centre when nothing is read (a localization limit).
- No scroll-edge masking, ellipsis exception, global full-text-elsewhere
  exemption, or clean-screen allowlist. D-025/D-023 govern human assessment;
  the baseline's contrary candidates stay in its output as false positives.

## Source and rendering contract

The screenshot's five-field name, PNG hash, size, language and versionCode must
agree with its capture in the manifest. The selected build's fork commit must
contain the same versionCode in BuildConfig. The inventory must match the
screen and upstream base. English.properties and German.properties are read
with `git show` at that exact commit, never from the fork's working tree.
Thus German clean 1271001 expects `Bergbau`, while German injected 1271002
expects `Bergbau und Erzgewinnung`.

The inventory contains source requests, runtime context and normalized search
slots, with source references. These are expected UI content, not defect
labels. It includes Writing at the top viewport edge and the full continuation
of the selected Archery description, including Temple of Artemis bonuses.
Source-defined clipped content is not omitted to reduce false positives.
It does not claim automatic discovery of widgets, scroll state or game state.
Slot boxes are manually declared search areas, not measured text bounding boxes.

The parser follows Unciv's ` = ` delimiter, nonempty-value rule and escaped
newlines. Missing/empty values fall back to source text. Template lookup reduces
parameters to `[]`, maps arguments through the original parameter names, then
substitutes their translations in target-language order. `{}` fragments are
translated separately with surrounding punctuation retained. For example:

- `Research [Archery]` -> `Bogenschießen erforschen`
- `{Units enabled}:` -> `Freigeschaltete Einheiten:`
- `[+10]% [Food] [in all cities]` -> `+10% Nahrung in allen Städten`

The supported subset covers plain strings and nested square/curly templates
used by this slice. Conditionals `<...>`, mods, icon insertion, number
localization and stat serialization are not a general Unciv renderer. Required
unsupported conditional/malformed templates fail as `not_checked`. Icons,
numeric stats/counters and arbitrary wrong substitutions are outside textual
coverage; the inventory checks translated description fragments individually.
The baseline recognizes known source keys/fallbacks, not every possible raw
identifier or arbitrary foreign language. One slot produces at most one
candidate; no label matching or evaluation deduplication is implemented.

## Failures, isolation and records

Missing Tesseract/language data, timeout, invalid/empty OCR on this text-bearing
screen, invalid PNG, source mismatch or unsupported rendering give
`not_checked` with a reason, never a successful empty result (D-013).

The baseline never opens or discovers `*.labels.json`. It accesses only build
and capture provenance fields from the manifest, not its human-label fields or
visual observations. Tests deny label-file access and poison label metadata.
Matching, metrics and Anton's golden expectations remain unchanged (D-026).

Each run stores `result.json`, `run.json`, `diagnostics.json` and, when
available, `ocr.tsv` and `source-entries.json`. Records include image/source
hashes, full commit, resolved translations, engine version, traineddata hashes,
settings, elapsed time and `requests_sent: 0`. Findings and supporting expected
strings can be traced through diagnostics and source entries. Failing input
validation may leave only the failure result and basic metadata.

## Verification

`uv run pytest` uses small known-text PNGs and fake OCR subprocess results; it
requires neither the OCR system package nor a device/network. Real OCR on the
same synthetic English/German images is checked separately with
`uv run --no-editable python scripts/baseline_ocr_smoke.py`. A missing OCR installation fails
that explicit smoke check rather than silently skipping it. The three real
slice runs and every clean-screen finding are recorded in
`docs/evidence/12/report.md`; they do not establish model superiority or the
quality of an unimplemented evaluator.

[CLI documentation]: https://tesseract-ocr.github.io/tessdoc/Command-Line-Usage.html
