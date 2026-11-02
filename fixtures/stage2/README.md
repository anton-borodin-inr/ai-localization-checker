# Stage 2 capture inputs

Owned by issue #41 and Proposed D-039. Anton approved these fixtures on
2026-10-21. They remain capture states, not labels; issue #57 adds the separate
source-screen split registry below without changing these fixture bytes.

## Manifest pins and source-screen split

`screens.json` remains protocol v1 / clean versionCode 1271045;
`screens-v2.json` remains protocol v2 / clean versionCode 1271048. Both retain
all ten D-039 screens and exactly the same fixture, state and settings files.
Do not rewrite either manifest into a selected subset or modify the historical
Stage 2 evidence to implement the split.

`split.json` beside both manifests is the only executable split-membership
declaration. Its JSON object has integer `schema_version: 1` and `dev` /
`holdout` arrays of source-screen IDs. The arrays are disjoint, have no repeated
IDs and cover exactly the ten D-039 source screens:

| Interface type | dev | hold-out |
|---|---|---|
| Choice tree with fixed-size buttons | `tech-picker` (D-043) | `policy-picker` |
| Game screen with lists | `city-production` (D-043) | `world` |
| Menu with drop-downs and checkboxes | `options-gameplay` | `new-game` |
| Tables with numbers | `empire-stats` | `victory-status` |
| Long texts in panels | `civilopedia` | `city-state-diplomacy` |

This completes D-043's assignment: every interface type is represented on both
sides. Variants stay grouped by source screen under D-010. The shared
`screen_split.load_split(path, screen_ids)` loader validates the registry for
capture and future tools; do not hard-code another split-membership list.
Registry array order is not capture order: the manifest remains authoritative.
For dev, forward order is `options-gameplay`, `tech-picker`, `city-production`,
`empire-stats`, `civilopedia`, and the second pass reverses it within each
language. Languages remain outside the screen loop.

Manifest preparation/capture require mutually exclusive `--split dev|holdout`
or repeatable `--screen-id ID`; neither selector defaults to all screens.
The registry is read even for explicit IDs. Any selection containing a
hold-out ID requires external output in **both** modes, with in-repository
output rejected before device access. All host outputs remain external when
external preflight/capture folders are requested; this does not relax legacy
capture or detector/evaluation restrictions. Preparation and capture bind the
original manifest hash, selected IDs/split name and split-file hash; changes
need fresh preparation and Anton's separate exact-plan approval. See
[the capture recipes](../../docs/stage2-capture.md), including the owner-only,
documentation-only hold-out recipe using caller-supplied external absolute
`$CAPTURE_ROOT`. No dev agent is authorized to execute that recipe.

Existing clean Stage 2 captures and confirmed visible-text references of all
five hold-out screens are already committed under `docs/evidence/41`,
`docs/evidence/47/reference-confirmation/` and
`docs/evidence/47/manual-acceptance/`. They contain no mutations, labels or
detector/model runs and stay where they are as historical Stage 2 evidence.
Issue #45 used only the two D-043 dev screens, and its explorations remain
non-labels under D-024. Future hold-out mutations, captures, labels and runs
belong only in owner-controlled external storage outside the dev agent's
working folder; this registry does not authorize accessing that storage.

## Unchanged fixture provenance

- `saves/issue-8-pair`: SHA-256
  `9d2a4cd5e1de2b2ae9102a2e6e6d15210e32ae5188c895f84e8a3a6ce19c3b4e`.
  Anton manually founded Ottoman Istanbul and saved it during issue #8.
  Turn 1, population 1, empty production queue. Recovered unchanged from
  issue #40's verified external app-data backup. Every in-game screen except
  city-state diplomacy uses these same bytes.
- `saves/issue-40-belgrade-metissue-8-pair`: SHA-256
  `2cf381aa7bf544961a302989c027045572b8d7036ab1840b01bc3ee4409c551e`.
  **city-state-diplomacy only.** On debug 1271002, Resume loaded bytes equal
  to the base save. Open console with grave/keycode 68, execute
  `diplomacy meet the-ottomans belgrade`, dismiss first-contact popup, then
  Tab > Save Game under a new name. The GUI retained the old-name suffix.
  Retain normal contact effects, including +30 gold. No turn was advanced,
  unit moved, technology confirmed, production queued/bought or policy adopted.
  A Delete confirmation during name editing was cancelled; nothing was deleted.
  `provenance.json` preserves the original candidate provenance plus acceptance.
  The console command is **not** part of capture.

`states/` starts byte-for-byte from the ten `verification-states/*.json` in
`issue-40-evidence-1271045.zip`. Both English and German were verified in issue #41: every screen reached
READY and repeated identically in reverse order. No language override was
needed. Overrides, if added later, are complete, separately hash-pinned state
files, never hidden merges.
Every visible ScrollPane, including zero-range panes, needs one instruction;
camera is the protocol's world-map exception. The runner checks fresh PANES
events and never silently edits states in response to an error.

`settings/{en,de}.json` derive from pinned `GameSettings.kt` at fork merge
`877b0dc` and tutorial history from the verified #40 settings (SHA-256
`7fc6dff53a9ff0b1a87e75c530edcf98fc000ee3dfa6f04d6feccd7085f9bfa7`).
They explicitly fix gameplay toggles/history slider, default font, Small UI,
minimap and relevant display settings. Tutorials are disabled; known tutorial
history is retained. Hook mode suppresses transient hints and persists neither
settings nor autosaves. Unspecified fields use the pinned build's defaults.
No personal multiplayer id or console history is copied.

Both templates also retain the same fixed `lastGameSetup` object from that
verified #40 settings backup. At `NewGameScreen.kt:107` in `877b0dc`, its
non-null presence controls the visible "Reset to defaults" button. The first
#41 capture omitted it and was repeatable but differed from #40 on New Game.
The hook's D-038 `new_game` state still supplies the displayed setup fields;
the archived seed in `lastGameSetup` does not replace that state or start a game.
After the fix, four new EN/DE captures repeated with zero changed pixels, and
both German captures matched #40 pixel for pixel. The review gallery records
this correction's provenance separately from the original ten-screen run.
`lastGameSetup` contains no personal identifiers: its players are one
`{"playerType":"Human"}` object and three empty objects.

World explicitly has **empty notifications on turn 1**, accepted by Anton.
New Game is never started: the hook pins the displayed preview to seed 40;
setup `seed=0` does not promise a deterministic subsequently generated game.

Add a language with one entry in the manifest's `languages` list, including its
normal Unciv language name, settings path and hash. Screen `languages=null`
inherits that list. Verify layouts and report any necessary language overrides.

Installed saves must match registry names and hashes. Capture never replaces
them. On a new emulator, copy the committed files to
`/sdcard/Android/data/com.unciv.app/files/SaveFiles/` only after backup and
explicit authorization; read them back and verify the registry hashes.
