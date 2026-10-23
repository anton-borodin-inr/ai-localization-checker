# Engine text candidates (issue 47)

The selected production build is fork `b534a8a` / APK 1271048. Existing
[device evidence](evidence/47/device-attempt-2/report.md) covers 40 PNG/dump pairs,
20 identical repeats, v1 compatibility, failure/recovery and restoration.
Cross-build Tech Picker differences are **recorded under D-0XX**
("Same-build non-interference and recorded cross-build pixel differences"),
not an acceptance blocker by themselves. See the [pixel summary](evidence/47/pixel-summary.md)
and [delivery report](evidence/47/report.md) for history and exact limits.
All 20 regenerated candidates remain unconfirmed; Anton owns reference and
D-025 scroll acceptance. This round performs no device work or APK build.

This is an offline candidate/review workflow. Engine output is not an approved
reference, a detector or a defect label. D-038 remains Accepted for protocol v1;
the additive v2 contract, candidate rules and non-interference criterion are
three Proposed D-0XX entries in the decision log.
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
It reuses every v1 screen/state/settings/save byte and route. Existing device
results are bound to these exact bytes. A changed build requires a new manifest
pin and exact-write approval.

## Non-interference checks

Require identical decoded pixels for v1 versus v2 on the same build and for
repeated captures; repeated v2 dumps must also be byte-identical. Existing
same-build v1/v2 evidence is the four German Tech Picker cold/warm arms in
[attempt 3 analysis](evidence/47/device-attempt-3/analysis.json), not a new
20-screen paired v1/v2 run.

Compare against the original 1271045 captures offline to record cross-build
differences:

```sh
PYTHONPATH=src uv run l10n-reference compare-captures \
  --capture-run data/issue-47/capture --reference-run /path/to/issue-41/capture \
  --output data/issue-47/against-1271045.json
```

This validates PNG hashes from both summaries before decoded-pixel comparison.
It preserves missing/different results and returns 2 unless all pairs match.
That raw comparison result is unchanged. Under the third D-0XX, record the
count, bounding box, maximum channel delta and text/layout visual check; a
cross-build difference alone does not block acceptance. This is an offline
image comparison, not a detector/baseline run.

## Device gate

Future device operations require Anton to release the emulator and approve
the exact plan. APK installation has its own exact
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
execution evidence. The historical executions and restoration checks are recorded in the
[report](evidence/47/report.md); no device operation is part of this revision.

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
  numbers in textual composed units remain in those units. Actual
  icons are removed only when identified by that element's
  `icon_glyph:<hex>` warnings; no Unicode range is guessed. Collapse horizontal
  whitespace after removal, preserving line breaks and other symbols.
- Regions use displayed glyph-box centres in D-025's 3×3 grid. Exact grid
  boundaries belong to the cell on the right/below; screen-edge cases clamp
  to the grid. Hidden ellipsis suffixes do not enlarge the display box.
- Unknown owner/other uncertainty is visible to Anton and defaults to
  diagnostic. A known absence of an English source key (`source_unavailable`)
  is provenance information, so fully visible established text can still be
  a primary candidate. `icon_glyph:*` and `markup_input` also retain their
  warnings without demoting otherwise established text. Other warnings keep
  the row diagnostic. Draw/scissor visibility does not prove that a later opaque
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
