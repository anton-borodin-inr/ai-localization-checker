# Repeatable Stage 2 capture

Inputs: [`fixtures/stage2/screens.json`](../fixtures/stage2/screens.json).
Protocol: [D-038 at fork merge 877b0dc](https://github.com/anton-borodin-inr/Unciv/blob/877b0dc/docs/l10n-hook.md).
No detector, mutations, labels or split are involved.

The prepared emulator must have the clean hook APK, versionCode 1271045,
SHA-256 `16b6e07eaa8f7ca35b71f361f0bdcceb7015987b60e796d15d2f3b53bb61af1a`.
Both committed saves must already be installed under their exact names/hashes.

On this Mac, the existing hidden editable `.pth` problem in `environment.md`
currently requires prefixing CLI commands with `PYTHONPATH=src`. This is a local
source-path workaround; it does not change packaging or fix the flag setter.

## Before agent-operated device writes

```sh
uv run l10n-capture --manifest fixtures/stage2/screens.json \
  --prepare-only --output-dir data/issue-41/preflight
```

This checks APK/version, 420 dpi, dimensions and disabled cutout. With temporary
adb root it force-stops the app, backs up settings bytes/metadata and all saves,
and verifies readback. It leaves the app stopped and adbd as shell. It writes
**no app data**. Private backups remain in the gitignored folder (directory 0700;
files 0600). `device-plan.json` lists exact settings hashes and screen orders.
Obtain Anton's separate device-operation approval under D-024 before capture
or device tests; plan approval alone is insufficient.

## Capture and compare

After approval:

```sh
uv run l10n-capture --manifest fixtures/stage2/screens.json \
  --lang en --lang de --repeat 2 --timeout 90 \
  --device-plan data/issue-41/preflight/device-plan.json \
  --output-dir data/issue-41/capture
```

Omitting `--lang` uses the manifest language list. `--serial` selects an emulator.
`--device-plan` verifies that settings, saves, build and manifest still match
the prepared operations before any app-data write. Changed inputs require
fresh preparation and approval.
Two passes are mandatory: forward then reverse screen order, keeping languages
outside the screen loop. Normally there are four settings pushes and four cold
starts; the first request launches directly into hook mode. One final write
restores original settings byte for byte. Every write attempt/readback is
journaled. Backups remain after success and failure. No app installation, save
copy or data deletion occurs. Failed restoration retains backups and reports
an error requiring manual recovery; adbd is unrooted on exit.

A unique Android log marker establishes a fresh logcat barrier before each
request. All three extras are sent, with a unique request id and padded
UTF-8/base64 JSON. Only matching screen **and** request ids can finish it.
PANES must equal the manifest instruction set; READY needs at least two quiet
frames. `am start -W` is not screen readiness. No fixed settle delay is used.
The client deadline must exceed the hook's 60-second readiness timeout.

ERROR records failure and no PNG, then continues. Timeout or uncertain launch
force-stops the app before another request: superseded requests on 1271045
have no terminal event (#44). City-construction failures may surface as
`reason=readiness_timeout` after 60 seconds; preserve that result. Hook changes
require Anton's new protocol decision, outside this task.

SDK adb captures full PNGs with foreground, cutout, build, dimensions, decoded
image and settings-byte checks. D-003/D-016 filenames are placed in `pass-1/`
and `pass-2/`. Prefer a fresh output directory. `--overwrite` preserves an old
run by moving it to a sibling `.previous-<uuid>` directory, preventing stale
images from standing in for failed new requests.

`summary.json` contains states, matching events/errors, hashes, write journal
and 20 decoded-RGBA comparisons. Changed-pixel count/share and bounding box
(right/bottom exclusive) are reported. Missing images are `unavailable`, never
identical. Non-identical results remain visible; fixes require a follow-up
decision. Exit 0 means all pairs identical and restoration successful; 2 means
incomplete/non-identical; invalid input or preparation failure gives 1.

Open `gallery.html` or `contact-sheet.png` for the 20 primary images. These are
capture evidence, not localization-defect judgments. English-specific states
use explicit `language_states` file/hash entries and are listed in the Report.
Adding a language is configuration only, followed by layout verification.

## Verification

```sh
uv run pytest
uv run pytest --run-device
uv run ruff check .
uv run ruff format --check .
git diff --check
```

Offline tests use fake adb/logcat. Device tests need separate approval: the
retained ordinary-APK test temporarily applies English then restores settings;
the hook test opens Tech Picker through the new client and force-stops without
app-data writes. The full 40-image command supplies end-to-end evidence.

Outstanding human checks under Accepted D-025: victory-status horizontal
clipping, and whether the Civilopedia category bar actually scrolls.
The D-024 manual-capture path and Stage 1 slice replay remain available.
