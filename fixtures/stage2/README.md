# Stage 2 capture inputs

Owned by issue #41 and Proposed D-039. Anton approved these fixtures on
2026-10-21. They are capture states, not labels or a dataset split.

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
`issue-40-evidence-1271045.zip`. English has not yet been verified. Language
overrides are complete, separately hash-pinned state files, never hidden merges.
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
