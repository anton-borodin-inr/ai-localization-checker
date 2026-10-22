Latest device control: [exact 1271045/1271048 APK comparison](evidence/47/device-attempt-4/report.md) reproduced the historical 1271045 German Tech Picker pixels exactly, then reproduced the same 72-pixel delta after restoring 1271048. This establishes a binary-dependent result in the current environment, without establishing a loading/glyph-atlas cause. Two approved package updates and two v1 requests completed; settings, saves and 45 existing dump files are unchanged. Final 1271048 is stopped, adbd shell, emulator free. Strict acceptance and human reference confirmation remain pending.

Latest host findings: [shared-path mechanism probe](evidence/47/shared-path-host/report.md) demonstrates a possible loading/layout-to-atlas mechanism in a synthetic fixture, not the Android delta cause. Production source remains unchanged at that checkpoint. Further diagnosis continues in the separate fork; any new device operation requires its own exact-operation approval.

Latest device follow-up: [same-APK v1/v2 diagnosis](evidence/47/device-attempt-3/report.md) completed four approved German Tech Picker launches on 1271048. All modes match the retained 1271048 pixels and preserve the same 72-pixel difference from 1271045. No settings/save writes or install occurred; original data is unchanged, app stopped, adbd shell, emulator free. Host-only investigation continues; strict acceptance and human confirmation remain pending.

Host follow-up: [bounded pixel diagnosis](evidence/47/pixel-diagnosis-host/report.md) found no demonstrated cause or justified replacement APK. Synthetic cache A/B checks passed; a separately proposed same-APK v1/v2 device comparison awaits approval.

# Engine text candidates (issue 47)

Latest runtime evidence: [1271048 device attempt 2](evidence/47/device-attempt-2/report.md) captured 40 pairs; repeat PNG/dump checks and lifecycle checks passed, but strict equality with 1271045 failed on Tech Picker. Twenty candidates remain unconfirmed. The emulator is free; any further device operation needs its own exact plan. Historical offline/device-gate descriptions below are retained as requirements and checkpoint context.

This is an offline candidate/review workflow. Engine output is not an approved
reference, a detector or a defect label. D-038 remains Accepted for protocol v1;
the additive v2 contract and candidate rules are Proposed as D-0XX below.
No OCR, model output, translation-table inference or baseline code is used.

## Protocol and files

V1 retains its three extras, state schema v1, PANES/READY/ERROR formats and
existing `fixtures/stage2/screens.json`. V2 adds the string extra
`l10n_protocol=2`. The state JSON schema is still version 1. The v2 client sends
sorted compact UTF-8 JSON plus LF, with integer-valued floats serialized as
integers; the dump's state SHA-256 hashes those exact decoded extra bytes.

After the final quiet draw, the fork atomically publishes an app-private dump
and emits, before the unchanged READY:

```text
L10N_SCREEN_DUMP tech-picker request=r file=files/l10n-hook/r.json sha256=<64 lowercase hex>
L10N_SCREEN_READY tech-picker request=r frames=2
```

The file and its `.json.tmp` sibling are **hook outputs**, distinct from
settings/save writes. V1 produces no dump output. Tokens are unique per
request; tokens and paths do not enter canonical dump bytes. Dump failures
produce ERROR, never READY without a dump. The client waits for a matching
terminal event even if a dump event is invalid, then reports the failure.

`text_dump.TextDump` defines strict dump format 1: build versionCode, screen,
game language, state digest, physical image size/viewport and ordered elements.
Each element keeps rendered post-ellipsis text separately from translated full
input, optional known English/component keys, owner/glyph/visible bounds,
alpha, visibility, clip area/fraction/cause, applied ellipsis, overflow flags,
font/pixel scales, explicit decorative grouping, warnings and line/glyph spans.
Coordinates are physical top-left PNG pixels, rectangles are
`[left, top, right-exclusive, bottom-exclusive]`. Bounds outside a viewport are
retained; no coordinates or text are reconstructed from the screenshot.
Clipped area measures glyph quads, not opaque ink or arbitrary occlusion.

`l10n-capture --manifest` accepts protocol 1 or 2. For v2 it reads only the
matching declared output with `exec-out run-as com.unciv.app cat <path>`, checks
event SHA-256, strict JSON/schema, state/build/language/screen and dimensions,
and stores `<stem>.texts.json` beside `<stem>.png`. `<stem>.pair.json` is the
last, atomically written commit marker binding original PNG bytes, decoded
RGBA bytes, dump bytes, state and build provenance. A PNG alone is not a
successful v2 pair. Summary/gallery consumers use captured records, never
orphaned files from an interrupted write.

The existing forward/reverse D-039 loop is retained. Repeated dumps must be
byte-identical as well as PNGs being pixel-identical. Dump differences remain
in the summary and make the run unsuccessful; request IDs are not stripped
from files to manufacture equality.

`fixtures/stage2/screens-v2.json` pins the host-built replacement APK 1271048 (fork commit
`b534a8ae67c390412984869c7a03b168d532c36c`, APK SHA-256
`91d9a900f8204880e590de7fb90f0fc15e2aa5cf5d94a3ae77364497d7b0541e`).
It reuses every v1 screen/state/settings/save byte and route. It is a prepared
input, not evidence of installation or device acceptance. A changed build
requires a new manifest pin and exact-write approval.

The first real 1271047 attempt failed on Android component-metadata regex
compilation and produced no successful pairs. See
[evidence/47/device-attempt-1/report.md](evidence/47/device-attempt-1/report.md).
The replacement removes that runtime regex and adds direct binding coverage;
its host tests do not establish Android acceptance. A fresh device plan uses
a v1/fault/recovery primer before the 40-pair batch.


After capture, compare all 40 new PNGs against the original 1271045 run:

```sh
PYTHONPATH=src uv run l10n-reference compare-captures \
  --capture-run data/issue-47/capture --reference-run /path/to/issue-41/capture \
  --output data/issue-47/against-1271045.json
```

This validates PNG hashes from both summaries before decoded-pixel comparison.
It preserves missing/different results and returns 2 unless all pairs match.
This is an offline image comparison, not a detector/baseline run.

## Device gate (not authorized by plan approval)

While #45 owns the emulator, do not run any device command, including
preparation or inventory. Host unit tests, builds and local synthetic-page
checks are allowed.

After Anton releases the emulator, APK installation has its own exact
operation approval/backups. The v2 manifest must name the actual new APK and
fork hashes; keep 1271045's manifest intact. Then a fresh `--prepare-only`
creates the #41 settings/save backup and a device plan. In v2 this includes
the serial, a fresh request namespace and every exact temporary/final hook
output path in `planned_hook_output_operations`, plus conditional creation of
`files/l10n-hook` in `planned_hook_directory_operation`. Capture requires this plan
and checks it before settings writes. A repeated capture needs a fresh plan
and approval: do not reuse request IDs or delete existing device outputs.
The hook-output journal records attempted and verified writes separately
from settings replacement/restoration. It does not claim to know the final
file state of a request that failed before publication.

Device commands in [stage2-capture.md](stage2-capture.md) are recipes, not
execution evidence. No device work has been run for the offline implementation.

## Candidate generation

After separately approved captures:

```sh
PYTHONPATH=src uv run l10n-reference generate \
  --capture-run data/issue-47/capture --output-dir data/issue-47/review
```

Or generate one page using `--pair <capture-dir>/<stem>.pair.json`. Output
folders must be new. Open `index.html` (run) or `review.html` (one pair).
Original image/dump/pair bytes are copied into each portable review folder.
Hash validation occurs again before generation and confirmation.

The candidate JSON follows #10/D-033 rows: `id`, `section`, `text_seen`,
`region`, `visibility`, `primary_denominator`, plus geometry and source links.
Rules fixed before device results:

- Preserve repeated occurrences at all locations, including the same grid
  cell. Only explicit shadow/outline passes share one logical occurrence;
  retain all constituent draw IDs.
- A fully visible wrapped label is one unit with line breaks and line boxes.
  If any line is incomplete, keep its visible fragments diagnostic. Do not
  complete cropped characters or concatenate text across hidden gaps.
- A composed widget string is one unit. Combine separate actors only through
  explicit engine composition provenance; never through spatial proximity or
  translation-table reconstruction.
- Partially clipped units use only fully visible glyph spans and stay outside
  the primary denominator. A visible fragment that cannot be established is
  an empty pending row, which Anton must edit or remove before confirmation.
  Hidden full input is shown separately as provenance, never projected.
- Fully visible applied ellipsis/overflow can remain primary text; flags
  never create defect labels. Numeric/symbol-only units default to diagnostic;
  numbers in textual composed units remain in those units. Actual private-use
  icon glyphs/bullets are not transcribed as words.
- Regions use displayed glyph-box centres in D-025's 3×3 grid. Exact grid
  boundaries belong to the cell on the right/below; screen-edge cases clamp
  to the grid. Hidden ellipsis suffixes do not enlarge the display box.
- Unknown owner/other uncertainty is visible to Anton and defaults to
  diagnostic. A known absence of an English source key (`source_unavailable`)
  is provenance information, so fully visible established text can still be
  a primary candidate. Draw/scissor visibility does not prove that a later opaque
  widget did not cover text. Resolve missing draw coverage before acceptance.

These rules do not modify the #10 approved reference, D-037 replay, matching,
metrics, detector schema/prompt, goldens or the OCR baseline. D-025's outstanding
human scroll checks remain pending.

## Review, timing and confirmation

The local page supports text edits, primary/diagnostic selection, region edits,
removal and human-authored additions. It shows glyph/owner/clip boxes and
independent image zoom. Start review explicitly, pause/resume as needed, then
confirm as Anton and export. The page performs no network requests. Review
input is escaped as text, including strings that look like HTML/script.

The export preserves the exact reviewed candidate bytes and binds their
SHA-256, the original candidate hash, PNG/dump hashes, reviewer and per-screen
start/finish/active/elapsed timing. Edited candidates name their parent hash.
No agent or command automatically confirms a generated candidate.

```sh
PYTHONPATH=src uv run l10n-reference confirm \
  --review-dir data/issue-47/review/tech-picker__de \
  --bundle /path/to/Antons/exported/confirmation.json \
  --output-dir data/issue-47/confirmed/tech-picker__de
```

The command independently reads original PNG/dump/pair bytes, validates all
bindings and rejects later changes. It writes `reviewed-candidate.json`,
`approval.json` and `reference.json`, together with exact PNG/dump/pair bytes
and `initial-candidate.json` for portable provenance. The reference contains rows and the ordered
`screen_texts`/`screen_texts_source` projection, preserving repeated visible
occurrences. Empty unresolved units cannot be confirmed. A two-screen demo
does not approve the other eighteen candidates. No model calls or scoring
occur in these commands. Preparation time is separate from Anton's measured
review time; no historical timed comparison is invented.

## Host verification

`uv run pytest` uses synthetic draws/fake adb/logcat and skips device tests by
default. One browser-export interoperability test uses host Node.js if present
and reports a skip otherwise; Node is not a package/runtime dependency of the
tool. The ordinary page runs in a browser without a server or build step.
`scene_to_pixels` is retained as a small independent coordinate oracle for the
fork/checker contract tests; production dumps already carry physical pixels.
Ruff and wheel-content checks cover the Python CLI and packaged UI script.

Synthetic UI screenshots are UI evidence only, never device coverage,
candidate completeness, confirmed references, defect labels or QA time data.
