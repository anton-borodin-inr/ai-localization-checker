# Repeatable Stage 2 capture

The current clean-build recipe uses
[`fixtures/stage2/screens-v2.json`](../fixtures/stage2/screens-v2.json): protocol
v2, APK versionCode 1271048, SHA-256
`91d9a900f8204880e590de7fb90f0fc15e2aa5cf5d94a3ae77364497d7b0541e`.
See [engine-text-reference.md](engine-text-reference.md) for PNG/dump pairs.
Every recipe on this page uses that v2 manifest and build. The legacy v1
manifest remains supported; its separate build requirements are documented in
the [fixture notes](../fixtures/stage2/README.md). Do not switch manifests or
install a legacy APK to follow this page.
The v2 manifest retains the exact D-039 fixtures, states and settings. Both
committed saves must already be installed under their exact names/hashes.
No detector, mutations or labels are part of these capture recipes.

On this Mac, the existing hidden editable `.pth` problem in `environment.md`
currently requires prefixing CLI commands with `PYTHONPATH=src`. This is a local
source-path workaround; it does not change packaging or fix the flag setter.

## Select screens explicitly

Every `--manifest` invocation, including `--prepare-only`, requires exactly one
selector: `--split dev`, `--split holdout`, or repeatable `--screen-id ID`.
`--split` and `--screen-id` are mutually exclusive. Missing selection fails
before device access; there is no implicit full-manifest run or `--all` option.
For example, a smaller dev selection can use
`--screen-id city-production --screen-id tech-picker` in place of `--split dev`
in **both** preparation and capture. Its forward order is still Tech Picker
then City Production: manifest order, not option order, is authoritative.

The runner reads `split.json` beside the supplied manifest for either selector,
including explicit IDs, so `--screen-id` cannot bypass the hold-out guard.
[`fixtures/stage2/split.json`](../fixtures/stage2/split.json) has integer
`schema_version: 1` and disjoint `dev` / `holdout` arrays covering exactly the ten
D-039 source screens. It is the only executable split-membership declaration;
see the [fixture notes](../fixtures/stage2/README.md). The shared
`screen_split.load_split(path, screen_ids)` loader is the validation entry point
for future tools; do not duplicate membership lists in capture or later tools.

Selection determines the device plan, forward/reverse requests, comparisons,
gallery and contact sheet. Within each pass, languages remain outside the
screen loop. All existing build, fixture, state, readiness, image, dump and
restoration checks remain in force for selected screens.

## Output boundaries (manifest mode only)

A manifest run may write to an external host root or inside this checkout's
`data/`; other in-repository destinations are rejected. Output roots containing
the checkout are also rejected, so overwrite cannot relocate the repository.
Containment uses filesystem identity, including case aliases and existing
ancestors of not-yet-created destinations, rather than path spelling alone.
Symlink run folders and symlink ancestors are rejected. If **any** selected ID
belongs to hold-out, both preparation and capture require external output:
even `data/` is rejected before device access. This also applies to mixed
explicit-ID selections.

For external output, all host backups, `device-plan.json`, host temporary
files, journals and capture artifacts stay external; nothing is written to the
repository or its `data/`. Use external folders for both preparation and
capture. Prefer fresh folders. Capture's `--overwrite` preserves the previous
run in an external sibling `.previous-<uuid>` folder when the output is
external; it never relocates that run into the repository. Preparation always
requires a fresh folder. These permissions apply only to manifest capture:
legacy single-screen capture and detector/evaluation path restrictions are
unchanged.

## Before agent-operated device writes (dev only)

First pass offline tests. Then wait for Anton to start and release the prepared
emulator and authorize preparation; do not start or take over an emulator as
part of an offline check. The prepared emulator must already have the clean
APK pinned by the selected manifest. Preparation is itself device work:

```sh
uv run l10n-capture --manifest fixtures/stage2/screens-v2.json --split dev \
  --prepare-only --output-dir data/issue-57/preflight
```

This checks APK/version, 420 dpi, dimensions and disabled cutout. With temporary
adb root it force-stops the app, backs up settings bytes/metadata and all saves,
and verifies readback. It leaves the app stopped and adbd as shell. It writes
**no app data**. Private backups remain in the selected output folder (directory
0700; files 0600). `device-plan.json` lists exact settings hashes and selected
screen orders. For v2 it also lists every temporary/final device hook output
and its D-055 cleanup authority. The hook directory must already exist; an
absent directory fails before writes, without creating/removing it. The plan
also binds the complete package-root starting inventory and directory identity.

The plan binds the **original, unfiltered manifest hash**, selected IDs, split
name (or explicit-ID selection), and split-file hash, as well as the existing
build, settings, saves and operation checks. Editing the manifest or registry,
changing selected IDs/split, or changing other bound inputs requires fresh
preparation and approval. A filtered manifest is not a substitute for binding
the original bytes. Obtain Anton's separate approval of the exact device plan
under D-024 before capture or the device test; plan/implementation approval
alone is insufficient. No selected capture is authorized without that approval.

## Capture and compare (dev only)

Only after approval of that exact plan:

```sh
uv run l10n-capture --manifest fixtures/stage2/screens-v2.json --split dev \
  --lang en --lang de --repeat 2 --timeout 90 \
  --device-plan data/issue-57/preflight/device-plan.json \
  --output-dir data/issue-57/capture
```

Omitting `--lang` uses the manifest language list. `--serial` selects an emulator.
`--device-plan` checks the prepared selection and operations before app-data
writes. A repeated v2 capture requires a fresh plan and separate approval;
do not reuse request IDs or manually delete prior device outputs. D-055 removes
only the exact new outputs of the current verified plan, never older files.
Two passes are mandatory: forward then reverse screen order, keeping languages
outside the screen loop. Normally there are four settings pushes and four cold
starts; the first request launches directly into hook mode. One final write
restores original settings byte for byte. Every write attempt/readback is
journaled. Backups remain after success and failure. No app installation, save
copy or data deletion occurs. Failed restoration retains backups and reports
an error requiring manual recovery; adbd is unrooted on exit. The sole D-055
deletion exception is the current plan's new final/temporary hook files after
their actual retained host bytes/hashes are verified. No save, settings,
pre-existing hook file or directory is a cleanup target.

App-data/settings/SaveFiles backup and readback reads have an exact 300 s hang
limit; native 30 s defaults, environment limits and hook deadlines are unchanged.
Private numbered `reads/*.json`/`.bin` receipts survive preparation, inventory-only,
readback, failed and final reads. They bind purpose/root/path, actual bytes/hash,
monotonic duration, throughput, outcome/completion, limit and `over_60s`. Report
every read over 60 s, including failures. Zero-duration throughput is `null`.
Failed/incomplete reads and malformed/truncated tars stop without retries.

After settings restoration, D-055 cleanup force-stops the package and proves
its stopped state under the exclusively released device/operator boundary;
do not allow a concurrent root/ADB operator. It retains complete before-cleanup
inventory and verifies the **entire** eligible host-pulled set before any unlink.
Unpulled planned final/temp bytes are retained exactly or cleanup fails closed.
Safe identities, no symlinks/hard links/ancestor aliases, and a guarded exact
private-root unlink protect against substitution by the stopped app writer.
No wildcard, recursive removal, namespace sweep or hook-directory deletion is
authorized. `hook-cleanup.json` plus summary record exact attempted/deleted/absent
states and host bindings, including partial failures. A fresh complete post
inventory must equal start under D-051 only, with no new-output exemption.
Cleanup/telemetry/verification failures are fatal, never successful captures or
permission to continue. Primary and cleanup/cancellation errors are retained
separately; successful cleanup cannot repair failed image/dump qualification.

A unique Android log marker establishes a fresh logcat barrier before each
request. The D-038 extras are sent, with a unique request id and padded
UTF-8/base64 JSON; v2 also sets `l10n_protocol=2`. Only matching screen **and**
request ids can finish it. PANES must equal the manifest instruction set;
READY needs at least two quiet frames. `am start -W` is not screen readiness.
No fixed settle delay is used. The client deadline must exceed the hook's
60-second readiness timeout.

ERROR records failure and no PNG, then continues. Timeout or uncertain launch
force-stops the app before another request, preserving the existing recovery
policy from #44. City-construction failures may surface as
`reason=readiness_timeout` after 60 seconds; preserve that result. Hook changes
require Anton's new protocol decision, outside this task.

SDK adb captures full PNGs with foreground, cutout, build, dimensions, decoded
image and settings-byte checks. D-003/D-016 filenames are placed in `pass-1/`
and `pass-2/`. V2 additionally validates the matching dump and atomically binds
PNG/dump hashes in a pair sidecar; a lone PNG is not a successful pair.

For five dev screens × EN/DE × two passes, the expected output is **20 PNG/dump
pairs and 10 comparisons**. `summary.json` contains selected states, matching
events/errors, hashes and the write journal. Comparisons report changed-pixel
count/share and bounding box (right/bottom exclusive), plus repeated dump-byte
equality for v2. Missing images are `unavailable`, never identical.
Non-identical results remain visible; fixes require a follow-up decision.
Exit 0 means all pairs identical and restoration successful; 2 means
incomplete/non-identical. Invalid manifest/input or preparation failures give
1. CLI usage errors, including a missing selector, give 2 before device access.

Open `gallery.html` or `contact-sheet.png` for the **10 selected primary
images**, not the whole manifest. These are capture evidence, not
localization-defect judgments. English-specific states use explicit
`language_states` file/hash entries and are listed in the Report. Adding a
language is configuration only, followed by layout verification.

## Hold-out recipe — Anton or a separate owner-controlled session only

**Documentation only; not authorization or execution evidence.** Coding agents
working on dev must not access the protected external hold-out data, perform
this recipe, create labels or run hold-out evaluation. Anton supplies
`$CAPTURE_ROOT` as a new, owner-controlled **external absolute path**, outside
the repository and the dev agent's working folder. No protected location is
named or inspected here. All future hold-out mutations, captures, labels and
runs stay in that owner-controlled external storage.

After Anton has released the prepared emulator and authorized preparation,
the owner/separate session prepares into the supplied external root:

```sh
: "${CAPTURE_ROOT:?Set an external absolute output root in the owner session}"
uv run l10n-capture --manifest fixtures/stage2/screens-v2.json --split holdout \
  --prepare-only --output-dir "$CAPTURE_ROOT/preflight"
```

**Stop here.** Anton must separately review and approve the exact
`$CAPTURE_ROOT/preflight/device-plan.json`, including the selected IDs and all
settings/hook-output writes. Only after that approval may the owner/separate
session run:

```sh
uv run l10n-capture --manifest fixtures/stage2/screens-v2.json --split holdout \
  --lang en --lang de --repeat 2 --timeout 90 \
  --device-plan "$CAPTURE_ROOT/preflight/device-plan.json" \
  --output-dir "$CAPTURE_ROOT/capture"
```

The external-output guard applies equally if the owner selects hold-out IDs
with `--screen-id`. Do not copy the resulting plans, backups, captures or other
hold-out artifacts into the repository or the dev agent's working folder.
The clean historical Stage 2 evidence already committed remains untouched;
it does not authorize future hold-out work by a dev agent.

## Verification

Offline gates (no emulator required; device tests are skipped):

```sh
uv run pytest
uv run ruff check .
uv run ruff format --check .
git diff --check
```

After those gates, wait for Anton to start/release the emulator, prepare a
fresh `--split dev` EN/DE v2 plan as above (using an external preflight folder
when all verification outputs must stay external), and obtain separate exact
plan approval. The targeted manifest device test consumes that plan and a
caller-supplied external output folder; replace the placeholders with those
approved paths:

```sh
uv run pytest --run-device tests/test_screen_capture_device.py \
  --capture-device-plan <approved-plan> --capture-output-dir <external-output>
```

This test always uses dev screens only, EN/DE, and v2 forward/reverse passes:
20 PNG/dump pairs and 10 comparisons. It is not permission to prepare or approve
a plan automatically. Do not substitute bare unrestricted `--run-device` for
this scoped verification. The retained ordinary-APK main-menu smoke is legacy
coverage, not one of the dev screen IDs and not issue #57's device evidence.
Report actual commands, results and skips; if device work is not authorized,
report it as not run with the reason. All commands on this page are recipes,
not a claim that they were run.

Outstanding human checks under Accepted D-025: victory-status horizontal
clipping, and whether the Civilopedia category bar actually scrolls.
The D-024 manual-capture path and Stage 1 slice replay remain available.
