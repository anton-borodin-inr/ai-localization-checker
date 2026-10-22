# Issue 47 — revised device plan after Android crash

**Awaiting Anton’s separate exact-operation approval. The replacement APK is host-built only; it has not been installed or run.**

The first approved attempt installed 1271047, then crashed before any PNG/dump pair. The app is stopped, adbd is shell, and original settings plus all four saves were independently verified restored. The old failure evidence and tokens remain intact. This is a fresh proposal, not reuse of the first approval.

## Pinned source and target

- Device: `emulator-5554` / `unciv_api34`, API 34 arm64-v8a, 420 dpi, disabled cutout; required capture size 2400×1080.
- Installed source: **1271047**, SHA-256 `ecd8c424dc09500f32edd075df71903ab64f6ba9c7ba985bc536e80f21e2c438` (failed first-attempt build).
- Replacement target: **1271048**, APK SHA-256 `91d9a900f8204880e590de7fb90f0fc15e2aa5cf5d94a3ae77364497d7b0541e`.
- Fork: `b534a8ae67c390412984869c7a03b168d532c36c`. Checker: `2e6f595506c8df47e70e270f510793658e2bed1a`. Manifest SHA-256: `b80d9a8c976fdff19cb97d300b264efdcc926ea4baeb88d45e7cdbcea929276a`.
- Source/target certificate SHA-256: `b4752f8cee80842f55883ca2a9b62ca75c898df5a1b7cefd63959ba1b8fecb99`. Verify actual signatures and all pins before installation.
- Original settings SHA-256 `7fc6dff53a9ff0b1a87e75c530edcf98fc000ee3dfa6f04d6feccd7085f9bfa7`, uid/gid/mode/size `10196 10196 600 873`; original language German.
- Original settings/save backups remain private. No save copy, replacement or deletion is proposed.

| Save | Unchanged SHA-256 |
|---|---|
| `./Autosave` | `9d2a4cd5e1de2b2ae9102a2e6e6d15210e32ae5188c895f84e8a3a6ce19c3b4e` |
| `./Autosave-The Ottomans-1` | `62c62dcefb9065850dea34293a8a644a5ccea5397aa5bd5b1a12620a220e9e13` |
| `./issue-8-pair` | `9d2a4cd5e1de2b2ae9102a2e6e6d15210e32ae5188c895f84e8a3a6ce19c3b4e` |
| `./issue-40-belgrade-metissue-8-pair` | `2cf381aa7bf544961a302989c027045572b8d7036ab1840b01bc3ee4409c551e` |

## Install operation

```sh
/Users/antonborodin/Library/Android/sdk/platform-tools/adb -s emulator-5554 install -r /Users/antonborodin/Documents/Codex/2026-10-21/task-issue-47-https-github-com/outputs/Unciv-1271048-debug.apk
```

Use one data-preserving PackageManager update. Read back installed version/APK hash/signature and unchanged settings/saves before activating the target capture plan. No uninstall, data clear, downgrade, alternate APK or automatic rollback. Android chooses its internal installation-staging and `/data/app` paths.

## Primer gate before the 40-pair batch

On original German settings, use exact lifecycle requests 0/1/2:

1. V1 Tech Picker compatibility: matching PANES/READY, no dump.
2. V2 city-production forced construction failure: exactly one ERROR with its actual cause, before readiness timeout; inspect frozen output after ERROR.
3. V2 Tech Picker recovery/font reset: READY plus a valid hash-bound dump; inspect repeated image and frame observations after READY.

**If any primer step crashes, times out or fails its expected terminal/dump validation, stop before capture-template writes.** Preserve evidence and original data; no unlisted request, silent retry or replacement APK is permitted. A correct regex on the host is not proof of Android acceptance.

## Exact settings writes

All target `/data/user/0/com.unciv.app/files/GameSettings.json`; preserve metadata and independently verify readback. Normal execution has seven explicit writes:

| # | Operation | Payload SHA-256 |
|---:|---|---|
| 1 | replace_settings / pass 1 / en | `853e1a055177314c866ae4427e697adeb6f79cab051d31bff0d6160b149c1776` |
| 2 | replace_settings / pass 1 / de | `397ddd96452874b01d9f096311049c0d076492297d557a9fb7c3d2abf1f3cdea` |
| 3 | replace_settings / pass 2 / en | `853e1a055177314c866ae4427e697adeb6f79cab051d31bff0d6160b149c1776` |
| 4 | replace_settings / pass 2 / de | `397ddd96452874b01d9f096311049c0d076492297d557a9fb7c3d2abf1f3cdea` |
| 5 | restore_original_settings | `7fc6dff53a9ff0b1a87e75c530edcf98fc000ee3dfa6f04d6feccd7085f9bfa7` |
| 6 | legacy_real_capture_apply_english | `99f9b6b293c1e6268d6d18891805872e1546c177775680f2718e8c206dcb4b23` |
| 7 | legacy_real_capture_restore_original | `7fc6dff53a9ff0b1a87e75c530edcf98fc000ee3dfa6f04d6feccd7085f9bfa7` |

The four template writes are EN/DE in pass 1 then EN/DE in pass 2; write 5 restores original settings. The retained ordinary main-menu capture test adds the exact original-to-English copy and its exact restoration (writes 6/7).

At most one extra conditional restoration of the verified original bytes is included if a failed runner or ordinary-mode check leaves settings different. Stop first, restore the same original hash/uid/gid/mode, verify, and abort on failed readback. This does not authorize another template/language payload. Changed saves require a stop/report, with no automatic save overwrite.

## Hook outputs and requests

Conditionally create `files/l10n-hook` if absent. Every v2 output exclusively creates its listed `.json.tmp`, syncs it and atomically renames it to its listed `.json`. Refuse existing temporary/final files. Retain outputs, perform no cleanup and never reuse tokens.

There are 48 possible output pairs (96 exact paths): 40 capture requests and 8 v2 lifecycle requests. Failed/superseded requests may publish none. Prefix each relative path with `/data/user/0/com.unciv.app/` for its absolute app-private location.

| Check | Request | Temporary | Final |
|---|---|---|---|
| capture 1 / en / options-gameplay | `i47-66ac1a0468f962d64057241bfc44f5e5-1-0-0` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-1-0-0.json.tmp` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-1-0-0.json` |
| capture 1 / en / new-game | `i47-66ac1a0468f962d64057241bfc44f5e5-1-0-1` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-1-0-1.json.tmp` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-1-0-1.json` |
| capture 1 / en / tech-picker | `i47-66ac1a0468f962d64057241bfc44f5e5-1-0-2` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-1-0-2.json.tmp` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-1-0-2.json` |
| capture 1 / en / city-production | `i47-66ac1a0468f962d64057241bfc44f5e5-1-0-3` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-1-0-3.json.tmp` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-1-0-3.json` |
| capture 1 / en / empire-stats | `i47-66ac1a0468f962d64057241bfc44f5e5-1-0-4` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-1-0-4.json.tmp` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-1-0-4.json` |
| capture 1 / en / policy-picker | `i47-66ac1a0468f962d64057241bfc44f5e5-1-0-5` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-1-0-5.json.tmp` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-1-0-5.json` |
| capture 1 / en / victory-status | `i47-66ac1a0468f962d64057241bfc44f5e5-1-0-6` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-1-0-6.json.tmp` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-1-0-6.json` |
| capture 1 / en / civilopedia | `i47-66ac1a0468f962d64057241bfc44f5e5-1-0-7` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-1-0-7.json.tmp` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-1-0-7.json` |
| capture 1 / en / world | `i47-66ac1a0468f962d64057241bfc44f5e5-1-0-8` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-1-0-8.json.tmp` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-1-0-8.json` |
| capture 1 / en / city-state-diplomacy | `i47-66ac1a0468f962d64057241bfc44f5e5-1-0-9` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-1-0-9.json.tmp` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-1-0-9.json` |
| capture 1 / de / options-gameplay | `i47-66ac1a0468f962d64057241bfc44f5e5-1-1-0` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-1-1-0.json.tmp` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-1-1-0.json` |
| capture 1 / de / new-game | `i47-66ac1a0468f962d64057241bfc44f5e5-1-1-1` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-1-1-1.json.tmp` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-1-1-1.json` |
| capture 1 / de / tech-picker | `i47-66ac1a0468f962d64057241bfc44f5e5-1-1-2` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-1-1-2.json.tmp` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-1-1-2.json` |
| capture 1 / de / city-production | `i47-66ac1a0468f962d64057241bfc44f5e5-1-1-3` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-1-1-3.json.tmp` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-1-1-3.json` |
| capture 1 / de / empire-stats | `i47-66ac1a0468f962d64057241bfc44f5e5-1-1-4` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-1-1-4.json.tmp` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-1-1-4.json` |
| capture 1 / de / policy-picker | `i47-66ac1a0468f962d64057241bfc44f5e5-1-1-5` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-1-1-5.json.tmp` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-1-1-5.json` |
| capture 1 / de / victory-status | `i47-66ac1a0468f962d64057241bfc44f5e5-1-1-6` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-1-1-6.json.tmp` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-1-1-6.json` |
| capture 1 / de / civilopedia | `i47-66ac1a0468f962d64057241bfc44f5e5-1-1-7` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-1-1-7.json.tmp` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-1-1-7.json` |
| capture 1 / de / world | `i47-66ac1a0468f962d64057241bfc44f5e5-1-1-8` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-1-1-8.json.tmp` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-1-1-8.json` |
| capture 1 / de / city-state-diplomacy | `i47-66ac1a0468f962d64057241bfc44f5e5-1-1-9` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-1-1-9.json.tmp` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-1-1-9.json` |
| capture 2 / en / city-state-diplomacy | `i47-66ac1a0468f962d64057241bfc44f5e5-2-0-0` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-2-0-0.json.tmp` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-2-0-0.json` |
| capture 2 / en / world | `i47-66ac1a0468f962d64057241bfc44f5e5-2-0-1` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-2-0-1.json.tmp` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-2-0-1.json` |
| capture 2 / en / civilopedia | `i47-66ac1a0468f962d64057241bfc44f5e5-2-0-2` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-2-0-2.json.tmp` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-2-0-2.json` |
| capture 2 / en / victory-status | `i47-66ac1a0468f962d64057241bfc44f5e5-2-0-3` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-2-0-3.json.tmp` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-2-0-3.json` |
| capture 2 / en / policy-picker | `i47-66ac1a0468f962d64057241bfc44f5e5-2-0-4` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-2-0-4.json.tmp` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-2-0-4.json` |
| capture 2 / en / empire-stats | `i47-66ac1a0468f962d64057241bfc44f5e5-2-0-5` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-2-0-5.json.tmp` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-2-0-5.json` |
| capture 2 / en / city-production | `i47-66ac1a0468f962d64057241bfc44f5e5-2-0-6` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-2-0-6.json.tmp` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-2-0-6.json` |
| capture 2 / en / tech-picker | `i47-66ac1a0468f962d64057241bfc44f5e5-2-0-7` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-2-0-7.json.tmp` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-2-0-7.json` |
| capture 2 / en / new-game | `i47-66ac1a0468f962d64057241bfc44f5e5-2-0-8` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-2-0-8.json.tmp` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-2-0-8.json` |
| capture 2 / en / options-gameplay | `i47-66ac1a0468f962d64057241bfc44f5e5-2-0-9` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-2-0-9.json.tmp` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-2-0-9.json` |
| capture 2 / de / city-state-diplomacy | `i47-66ac1a0468f962d64057241bfc44f5e5-2-1-0` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-2-1-0.json.tmp` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-2-1-0.json` |
| capture 2 / de / world | `i47-66ac1a0468f962d64057241bfc44f5e5-2-1-1` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-2-1-1.json.tmp` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-2-1-1.json` |
| capture 2 / de / civilopedia | `i47-66ac1a0468f962d64057241bfc44f5e5-2-1-2` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-2-1-2.json.tmp` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-2-1-2.json` |
| capture 2 / de / victory-status | `i47-66ac1a0468f962d64057241bfc44f5e5-2-1-3` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-2-1-3.json.tmp` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-2-1-3.json` |
| capture 2 / de / policy-picker | `i47-66ac1a0468f962d64057241bfc44f5e5-2-1-4` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-2-1-4.json.tmp` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-2-1-4.json` |
| capture 2 / de / empire-stats | `i47-66ac1a0468f962d64057241bfc44f5e5-2-1-5` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-2-1-5.json.tmp` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-2-1-5.json` |
| capture 2 / de / city-production | `i47-66ac1a0468f962d64057241bfc44f5e5-2-1-6` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-2-1-6.json.tmp` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-2-1-6.json` |
| capture 2 / de / tech-picker | `i47-66ac1a0468f962d64057241bfc44f5e5-2-1-7` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-2-1-7.json.tmp` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-2-1-7.json` |
| capture 2 / de / new-game | `i47-66ac1a0468f962d64057241bfc44f5e5-2-1-8` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-2-1-8.json.tmp` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-2-1-8.json` |
| capture 2 / de / options-gameplay | `i47-66ac1a0468f962d64057241bfc44f5e5-2-1-9` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-2-1-9.json.tmp` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-2-1-9.json` |
| forced-construction-failure | `i47-66ac1a0468f962d64057241bfc44f5e5-lc-1` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-lc-1.json.tmp` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-lc-1.json` |
| recovery-and-font-reset | `i47-66ac1a0468f962d64057241bfc44f5e5-lc-2` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-lc-2.json.tmp` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-lc-2.json` |
| cold-supersession-A | `i47-66ac1a0468f962d64057241bfc44f5e5-lc-3` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-lc-3.json.tmp` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-lc-3.json` |
| cold-supersession-B | `i47-66ac1a0468f962d64057241bfc44f5e5-lc-4` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-lc-4.json.tmp` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-lc-4.json` |
| cold-supersession-C | `i47-66ac1a0468f962d64057241bfc44f5e5-lc-5` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-lc-5.json.tmp` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-lc-5.json` |
| warm-supersession-A | `i47-66ac1a0468f962d64057241bfc44f5e5-lc-6` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-lc-6.json.tmp` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-lc-6.json` |
| warm-supersession-B | `i47-66ac1a0468f962d64057241bfc44f5e5-lc-7` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-lc-7.json.tmp` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-lc-7.json` |
| warm-supersession-C | `i47-66ac1a0468f962d64057241bfc44f5e5-lc-8` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-lc-8.json.tmp` | `files/l10n-hook/i47-66ac1a0468f962d64057241bfc44f5e5-lc-8.json` |

The companion JSON contains complete launch argv, exact base64 state and state digest for every lifecycle request. V1 request 0 produces no hook file.

## Execution order and observations

1. PRIMER before any capture template write: v1 compatibility, forced v2 construction failure and v2 Tech Picker recovery, using lifecycle requests 0/1/2 on original German settings.
2. If any primer check crashes, times out or fails its expected terminal/dump validation: abort all remaining launches and template writes, verify/restore original data within the listed recovery, and report. No silent retry.
3. Only after primer passes, run the exact 40-pair capture batch; retain all mismatches and restore original German settings.
4. Force-stop and send cold supersession A/B/C consecutively without -W and without waiting for terminals between requests; then observe all correlated events
5. Send warm supersession A/B/C consecutively; observe retired callbacks and exactly-once terminals. Already-terminal requests cannot count as superseded; if the timing fails to exercise loading, report unverified rather than silently retry.
6. Launch ordinary mode without extras while warm to exercise leave; observe menu, send KEYCODE_BACK then KEYCODE_BACK to open/dismiss exit confirmation without confirming exit; force-stop
7. Run retained real main-menu capture test on new build; it applies compact English copy of original and restores the exact original bytes
8. Read-only final settings/all-save/build verification; stop app and unroot adbd

Cold and warm supersession bursts send A/B/C consecutively without `-W` or readiness waits between launches. Expect one superseded terminal for each still-unfinished A/B and READY for C. Already-completed requests cannot be counted as a supersession pass; preserve unexercised timing rather than silently adding retries.

The ordinary warm launch uses no hook extras to leave capture mode. Two Back events open/dismiss the main-menu exit confirmation; do not confirm Exit or change game settings. The retained device test supplies an ordinary cold start. Compare repeated screenshots and read-only frame evidence after READY/ERROR; identical pixels alone do not establish absence of render work.

Capture command, only after the primer passes and exact expected plan bytes have been verified/promoted:

```sh
env PYTHONPATH=src uv run --offline --cache-dir /private/tmp/issue47-uv-cache l10n-capture --manifest fixtures/stage2/screens-v2.json --serial emulator-5554 --lang en --lang de --repeat 2 --timeout 90 --device-plan /Users/antonborodin/Documents/Codex/2026-10-21/task-issue-47-https-github-com/work/device-phase-2/capture-device-plan.json --output-dir data/issue-47/capture-approved-2
```

Applicable device pytest (two settings writes above):

```sh
env PYTHONPATH=src uv run --offline --cache-dir /private/tmp/issue47-uv-cache pytest --run-device tests/test_capture_device.py -q -rs
```

Existing `test_hook_device.py` remains pinned to 1271045 and is not weakened. Target v1 transport is tested explicitly by primer request 0. Preserve failed/unrun statuses honestly.

## Checks, recovery and final state

- Temporary root/unroot and force-stop; SDK screencaps; foreground/cutout/density/build/hash checks; unique logcat barriers and reads, never log clearing.
- Read-only `dumpsys gfxinfo ... framestats` without reset and SurfaceFlinger frame/layer data if available. Read only declared published outputs via app-UID `cat`.
- A capture timeout/uncertain launch allows a force-stop before the next already scheduled capture request. No additional request/token batch is included. Stop on new crashes or changed build/input pins.
- Finish with **1271048 installed**, original settings bytes/metadata and all four save hashes unchanged/restored, app stopped, adbd shell, new hook outputs retained. Keep backups/journals through failures.
- No provider/model calls or spend; no baseline/OCR, hold-out, translation, detector, metric, matching or golden changes; no push/PR/issue closure.
- Generate unconfirmed candidates only from successful pairs. Anton alone confirms references/timings and the remaining two D-025 scroll checks; operation approval is not reference approval.

## Comparison source

Use the independently hash-verified effective #41 set (18 original pairs plus 2 corrected New Game pairs, including their repeats), with explicit provenance. Do not call it one full run after correction. Require zero changed decoded pixels versus each corresponding old image and repeat, and byte-identical repeated dumps. Keep discrepancies; do not normalize them away.

Reference summary SHA-256: `42e1882fe04b5739f7b4e7f628fe27c9a80e9a6426b74b9bf7558efa38119aec`.

## Approval binding

Plan ID: `issue47-device-2-66ac1a0468f962d64057241bfc44f5e5`.
Machine-readable plan `issue-47-device-plan-2.json`, SHA-256 `b5b78e4262618b992330cd16c1638b413a58a8dd085536eb801c7c9561de62f8`.
Expected post-install capture plan SHA-256: `56d4738ede3e9a0427459125855358533d4fb8a9cf7d79b090f89681e44cf9bb`. It is an expected target description until actual post-install verification; no new random paths may replace those approved here.

Approve the one pinned update, seven normal settings writes plus the stated contingent original-byte restoration, conditional directory creation, 48 possible hook-output pairs and the exact primer/capture/lifecycle/input/read/recovery operations above. Changed APK/manifest/settings/fixtures/commands invalidate this proposal before dependent writes.
