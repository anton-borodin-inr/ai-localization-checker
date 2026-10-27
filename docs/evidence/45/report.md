# Issue 45 Report

**Limitations and outstanding work:** this is exploration on two dev screens, not a labeled evaluation or a detector-quality/baseline comparison. Two counter-overflow runs are `not_checked` because the model reports partial readability. The model also returns findings for visibly complete/native text and misses other reproduced mechanisms. No prompt/schema or mutation was retuned after the results. The class definitions below need Anton's edits/acceptance and independent review; no Accepted decision is changed.

**Device restored and free:** original hook APK 1271045 is installed and independently hash-verified. The existing D-038 hook device test passed. Original settings bytes/stat and all saves match the pre-task backup before and after the test. The app is stopped and the same AVD remains running. See [final verification](final-device-verification.json).

## What changed

- Checker branch `feat/45-defect-type-probes` from `63b65347b328363f2fdfd51a345a805a6e8c17f9`: task-specific guarded backup/capture/check helpers, focused tests, evidence and two Proposed D-0XX entries. [Exact changed-file list](changed-files.txt).
- Separate fork folder/branch `probe/45-defect-types` from `l10n-base-4.22.10` at `877b0dc2ee706dbbdb4a17e14b4522408d197390`. Only English/German translation files changed in its eight commits. **Never merge this probe branch into the clean base.** APKs use new versionCodes 1271451–1271458 via an external [Gradle init script](version-code.init.gradle); tracked Kotlin/Gradle metadata and the hook are unchanged.
- [Exact frozen mutations](probe-design.json) record every file, key, original/mutated value and operation relative to the clean base. Every variant replaces the previous variant's translation changes rather than accumulating them. [Build evidence](builds.json) and [APK verification](apk-verification.json) establish exact packaged translation bytes, identical signing certificate, arm64/DEX presence and source-only translation diffs.
- 19 unchanged original PNGs: 4 clean controls and 15 mutation images. [Gallery](gallery.html), [capture/READY/hash/run index](capture-index.json), [source/PNG observations made before each mutation's model calls](observations.json). The removed German Mining entry applies only to DE: source-English fallback cannot be wrong-language text in EN UI.
- Each image was sent twice through the unchanged v1 contract: 38 independent requests, 36 checked/readable and 2 not_checked/partial. [Every returned finding, status and readability](run-summary.md); [machine-readable diagnostics including reasons/regions](run-summary.json); raw response/result/run/prompt/sent-wrapper/CLI evidence under `run-records/<run-id>/`.
- No change to hook, l10n-capture, baseline/OCR, provider/detector implementation, prompt/schema v1, matching, metrics, labels, goldens or dependencies. Exploratory images never enter labels/evaluation. No other source screen was sent to DeepSeek.

## Per-candidate result

“Seen” below is a descriptive count of checked runs whose returned text refers to the injected target/mechanism; it is not a matching result, ground truth, precision or recall. A raw diagnostic finding from not_checked never counts as a checked detection. Baseline expectations are source-based and unmeasured; no OCR run was performed.

| Candidate | Reproduced in these widgets | What the frozen model returned | Obvious OCR + table expectation |
|---|---|---|---|
| Own-field overflow | Yes: turn label escapes its 40-unit cell in DE/EN and collides with technology titles. Worker: own-label overflow not demonstrated; wrapping/panel growth causes a separate-widget collision. | Turn probe: 2/4 runs checked/readable report `overlap`; other 2/4 partial/not_checked retain overlap only as diagnostics. Worker: 0/4 reports collision/overflow; 3/4 call the complete title `truncated_text`, 1/4 empty. There is no `overflow` schema class. Collision-free overflow detection was not tested. | No own-label/container geometry or overflow rule in the current baseline. OCR failures may trigger a missing/prefix rule, which does not establish overflow. |
| Wrong language | Yes: DE Mining fallback and foreign Worker in DE/EN. | 4/6 target-reporting checked runs: all foreign Worker runs use `untranslated`, both fallback runs empty. All foreign runs also flag three native-language unit names. There is no `wrong_language` schema class. | Can use missing-entry provenance and known EN/DE alternatives when expectations are independent. It cannot infer arbitrary foreign text from a polluted active table; Russian OCR is outside its EN/DE language setup. |
| Technical text / broken placeholder | Yes: failed template-name substitution on Research and literal token in Worker title. | 2/8 runs report target text: both DE Worker runs use `untranslated`, also flagging the native description. EN Worker 0/2 and Research DE/EN 0/4 are empty. No dedicated schema class; D-027 prescribes `other`, but the model did not use it here. All 8 checked/readable. | Existing `literal_placeholder` rule can emit `other` if OCR preserves brackets. It need not recognize a bracket-free `amount` as technical text, and cannot validate arbitrary substitutions just from text equality. |
| Truncated text | Yes: Mining ellipsis in DE/EN, no full title elsewhere. | 4/4 checked/readable runs use `truncated_text` for the ellipsized target, stable within these two repetitions. | Expected prefix/missing comparison against independent full text can catch this; D-023 full-text-elsewhere and D-025 viewport boundaries still need correct inventory/context. |
| Unreadably small text | No: long Research action and long Worker title retain ordinary font size and grow/wrap. | 0/8 explicit small-text reports across those two probes (all checked/readable). Research 4/4 empty; Worker 3/4 truncation reports concern a complete title. No dedicated schema class, no reproduced positive example. | No font-size/readability threshold. Missing OCR text cannot distinguish tiny text from occlusion or OCR failure. |

### Visible boundaries

- Turn overflow retains font size 14. The suffix is fully visible in unobstructed counters elsewhere; this is own-cell overflow/collision, not a truncation claim. Source concatenates number and hourglass without a separator, so replacing the icon also introduces number-word adjacency, e.g. `6Runden`; this confound is retained.
- Worker wraps to four lines in the list; the complete title fits the selected-construction panel after it grows. The city-name control occludes part of the grown description panel. This is a collision between widgets, not proof of text escaping its own label. The complete title is visible twice, so its model truncation findings conflict with the observed title and D-023 boundary.
- German fallback shows complete `Mining` among German technology names; no target clipping/collision. Foreign Worker is complete in list and panel. The Worker literal-token path strips brackets in the list (`Arbeiter amount` / `Worker amount`) while preserving `[amount]` in the selected panel. Research preserves the literal token in both languages.
- Mining shows `Bergbau und Erzgew...` / `Mining and ore extra...` within a fully displayed button; Archery is selected, so neither description nor Research action exposes the full Mining title. Unrelated clipping at tree/description scroll edges remains excluded under D-025.
- The long Research action fits by growing left and narrowing the description scroll viewport. It does not visibly shrink or lose the target text. [Pinned source inspection](source-inspection.json) covers TechButton, TechPickerScreen, PickerScreen/PickerPane, city construction labels and ordinary label/button helpers. Fixed `setFontScale` from a requested font size is not length-dependent fitting. No such fitting was found in this scope; this does not establish absence across all Unciv widgets. No additional device scrolling was performed to create new label decisions.

### Clean controls and stability

“Clean control” means no injected translation change, not an agent-created clean label. Of eight checked/readable control runs, one DE city-production run reports `truncated_text` for complete wrapped `Kann Land Verbesserungen auf Feldern bauen`, bottom-right, confidence 0.6; its repeat is empty. The other six runs are empty. Foreign-language probes flag native `Siedler`/`Späher`/`Krieger` in DE and `Settler`/`Scout`/`Warrior` in EN in all four runs, alongside the injected token. Preserve these discrepancies and both partial responses; do not rerun them away or derive labels from them. Two calls per image are a small stability probe, not a reliability estimate.

## How it was verified

- Original hook APK 1271045, settings and complete internal/external file archives were backed up before writes via `run-as`, without root. Independent readbacks and per-file hashes/metadata verified them; private backups are retained outside committed evidence. [Backup summary](pre-task-backup-summary.json).
- Every exact install/capture plan was separately approved in the task chat. Each in-place install checks source/target versionCode and APK SHA-256 plus original settings bytes/stat and all external saves before/after. No uninstall/clear data or save provisioning/writes. [Install audits](install-audits/) and [all app replacements/data-write attempts](device-operation-summary.json).
- Captures use the unchanged D-038 client, frozen state/templates, unique requests/log barriers and matching READY after >=2 quiet frames. Foreground, cutout, 420 dpi, build/hash, full PNG decode and 2400x1080 dimensions are checked; each block restores original settings in finally and verifies all saves. Frozen states select Archery/anchor Mining and Istanbul/Worker with an empty queue. English/German screen overrides are empty for these two screens.
- Total explicit settings-write attempts: 28, including 2 in the failed initial clean block and 26 in completed capture blocks. Exact operations/hashes/readbacks are retained. The failed first transfer stopped before hook/screenshot and still restored original bytes. No save files were written.
- Clean controls and probes belong to the same task session, with a documented emulator restart between controls and probes. Anton approved restarting the existing AVD without wipe, snapshot load/save or reset, plus standard cutout preparation. APK/settings/saves were verified against backup after reboot before the first successful probe install.
- [Evidence reconciliation](evidence-reconciliation.json) independently checks 19 PNG hashes against capture/run metadata, matching READY, exactly two runs per PNG, original local run metadata versus committed copies, every frozen prompt/sent hash and exact ledger usage/cost totals. No live provider call is made by this check.
- Final offline suite after task helper changes: `PYTHONPATH=src .venv/bin/python -m pytest -q`: **1455 passed, 2 skipped**, exit 0 ([output](pytest-final.txt)). The two default skips require --run-device. Ruff check and format check: exit 0, 84 files already formatted. The existing main-menu device test changes settings outside the approved blocks and was not run; task-specific captures provide direct device evidence.
- After restoration, `tests/test_hook_device.py` with `--run-device` passed: **1 passed**, exit 0 ([output](pytest-hook-device.txt)). It launches only tech-picker through D-038 under original settings, then stops the app. Before/after verification confirms original APK hash, byte-identical settings/stat and all four save files unchanged. Original APK SHA-256 `16b6e07eaa8f7ca35b71f361f0bdcceb7015987b60e796d15d2f3b53bb61af1a`; settings SHA-256 `7fc6dff53a9ff0b1a87e75c530edcf98fc000ee3dfa6f04d6feccd7085f9bfa7`, stat `10196:10196:600:873`.

## Deviations from the task

No scope deviation. The initial clean settings transfer failed readback before a hook request, was restored and corrected to `adb shell -T run-as tee`; failure evidence is retained. The first install preflight stopped while the emulator process was absent, then succeeded after the separately approved reboot/original-data checks. A cutout preflight stopped once and standard approved preparation was reapplied. Initial Gradle wrapper/cache attempts failed; copying an old cache was stopped and a fresh task-local cache downloaded the same pinned dependencies. All failure/build attempts remain in evidence. Committed build-log copies remove trailing whitespace only, with raw hashes in [log-normalization.json](log-normalization.json); local raw logs remain retained.

The original metadata is preserved except fields inherently updated by reads/install operations (for example access timestamps are not asserted); settings uid/gid/mode/size, save metadata captured by the inventory, and every required file byte/hash are checked. No data repair or rollback of saves was needed. No general claim about font scaling outside the inspected widgets is made.

## Decisions proposed

Two entries in docs/decisions.md, numbered on merging main: D-043 (dev-screen assignment) and D-044 (proposed v1 classes):

1. Record Anton's assignment of tech-picker and city-production to dev; assign no other screens.
2. Propose three primary semantic classes, superseding only D-006's type count and D-020's class list/overlap deferral if Anton accepts:
   - `overflow`: text renders outside its own assigned label/field bounds, with or without collision. Wrapping/container growth with fitting text is excluded; separate-widget collision is distinguished.
   - `wrong_language`: user-facing text is in another language than the intended screen, including source fallback or foreign content in the active file. Proper names/shared words/symbols/numbers require context.
   - `truncated_text`: some user-facing text is unavailable because its label clips/shortens it, retaining D-023's full-text-elsewhere exception for ellipsis and D-025's scroll exclusion.

Anton writes or edits the definitions/boundaries before acceptance. These are proposed semantic names, not a schema change: frozen wire classes remain overlap/untranslated/truncated_text/other. Naming/compatibility implementation needs a later scoped task after acceptance. D-027 stays binding: raw keys are untranslated with notes; broken placeholders are other with notes. Technical text has evidence but no new primary class here; unreadably small text lacks a positive example. The proposal is based on reproduced UI mechanisms, not a claim that the current model detects them reliably.

## Open questions for Anton

- Edit/accept/reject the three-class proposal and its boundaries; inspect the separate-widget collision before deciding whether it needs a later class.
- Publication was separately authorized and both branches were pushed. [Draft PR #49](https://github.com/anton-borodin-inr/ai-localization-checker/pull/49) contains the Report; no merge was performed. Independent review must inspect screenshots and raw runs before merge; the author does not approve its own PR.
- Labels, all remaining screen assignments, mutation generation, prompt/schema revisions and OCR comparison remain separate work.

## Retained support files

Task scripts and focused tests are retained to reproduce guarded capture/accounting and failure-restoration behavior. [Operational recipe snapshots](recipes/README.md) preserve exact build/install/export/verification sources as non-executable audit text; they are not new installed commands. The design initializer must never be rerun over the ledger. APK binaries, full original settings/saves, Gradle caches and raw build logs remain local and uncommitted. No temporary work product is added to production modules. The final original-build test reuses an existing test without modifying hook or capture code.

## API usage

38 / 100 requests; peak estimate **USD 0.015411696**; off-peak estimate USD 0.0077058480; unknown reserve USD 0; limit USD 1.00. All 38 attempts returned validated responses; two are not_checked due to partial readability. No API error, transport retry or invalid response occurred. No further calls are needed.

Usage totals: `{"prompt_tokens": 69768, "completion_tokens": 3147, "total_tokens": 72915, "prompt_cache_hit_tokens": 31616, "prompt_cache_miss_tokens": 38152}`.

Every invocation used `uv run --env-file .env --no-sync l10n-check --image <PNG> --runs-dir data/runs --max-requests 1`. The task wrapper verifies screen/capture provenance and frozen hashes, reserves worst-case request cost before the call, locks/reconciles the ledger and records unknown/failure outcomes without treating them as clean. Only the project provider module contacts DeepSeek. The agent never reads, prints or copies .env or the key. The ignored .env path is a symlink to the existing project key file, not a copy.

The unchanged provider uses deepseek-flash, non-thinking, temperature 0, original PNG detail, JSON object mode, max_tokens 4096, 120 s timeout and no transport retries. The API reports only a model alias plus system_fingerprint, not an immutable revision. Tariff verification and conservative USD 0.319488 per-request reserve are in [budget-policy.json](budget-policy.json); the provider tariff snapshot is retained per run. These are estimates, not billing receipts. [Official pricing](https://api-docs.deepseek.com/quick_start/pricing/).

| Run id | Screenshot | Requests | Prompt | Cache hit | Cache miss | Completion | Total | Peak USD | Off-peak USD |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| [20261021T185946Z-c21c92](run-records/20261021T185946Z-c21c92/run.json) | city-production__de__2400x1080__probe-clean__1271045.png | 1 | 1836 | 0 | 1836 | 63 | 1899 | 0.0006264 | 0.00031320 |
| [20261021T185948Z-4ba077](run-records/20261021T185948Z-4ba077/run.json) | city-production__de__2400x1080__probe-clean__1271045.png | 1 | 1836 | 1664 | 172 | 30 | 1866 | 0.000097584 | 0.0000487920 |
| [20261021T185950Z-bbbee4](run-records/20261021T185950Z-bbbee4/run.json) | tech-picker__de__2400x1080__probe-clean__1271045.png | 1 | 1836 | 0 | 1836 | 30 | 1866 | 0.0005868 | 0.00029340 |
| [20261021T185953Z-6b3140](run-records/20261021T185953Z-6b3140/run.json) | tech-picker__de__2400x1080__probe-clean__1271045.png | 1 | 1836 | 1664 | 172 | 30 | 1866 | 0.000097584 | 0.0000487920 |
| [20261021T185955Z-e3cd99](run-records/20261021T185955Z-e3cd99/run.json) | city-production__en__2400x1080__probe-clean__1271045.png | 1 | 1836 | 0 | 1836 | 30 | 1866 | 0.0005868 | 0.00029340 |
| [20261021T185957Z-cbf5a7](run-records/20261021T185957Z-cbf5a7/run.json) | city-production__en__2400x1080__probe-clean__1271045.png | 1 | 1836 | 1664 | 172 | 30 | 1866 | 0.000097584 | 0.0000487920 |
| [20261021T190000Z-d845c8](run-records/20261021T190000Z-d845c8/run.json) | tech-picker__en__2400x1080__probe-clean__1271045.png | 1 | 1836 | 0 | 1836 | 30 | 1866 | 0.0005868 | 0.00029340 |
| [20261021T190002Z-c1ff72](run-records/20261021T190002Z-c1ff72/run.json) | tech-picker__en__2400x1080__probe-clean__1271045.png | 1 | 1836 | 1664 | 172 | 27 | 1863 | 0.000093984 | 0.0000469920 |
| [20261021T191152Z-72ce18](run-records/20261021T191152Z-72ce18/run.json) | tech-picker__de__2400x1080__probe-overflow-turns__1271451.png | 1 | 1836 | 0 | 1836 | 406 | 2242 | 0.001038 | 0.0005190 |
| [20261021T191155Z-17b6ce](run-records/20261021T191155Z-17b6ce/run.json) | tech-picker__de__2400x1080__probe-overflow-turns__1271451.png | 1 | 1836 | 1664 | 172 | 447 | 2283 | 0.000597984 | 0.0002989920 |
| [20261021T191158Z-913f4c](run-records/20261021T191158Z-913f4c/run.json) | tech-picker__en__2400x1080__probe-overflow-turns__1271451.png | 1 | 1836 | 0 | 1836 | 165 | 2001 | 0.0007488 | 0.00037440 |
| [20261021T191204Z-2cd54a](run-records/20261021T191204Z-2cd54a/run.json) | tech-picker__en__2400x1080__probe-overflow-turns__1271451.png | 1 | 1836 | 1664 | 172 | 145 | 1981 | 0.000235584 | 0.0001177920 |
| [20261021T191708Z-c9f170](run-records/20261021T191708Z-c9f170/run.json) | city-production__de__2400x1080__probe-overflow-worker__1271452.png | 1 | 1836 | 0 | 1836 | 77 | 1913 | 0.0006432 | 0.00032160 |
| [20261021T191710Z-11f2ef](run-records/20261021T191710Z-11f2ef/run.json) | city-production__de__2400x1080__probe-overflow-worker__1271452.png | 1 | 1836 | 1664 | 172 | 77 | 1913 | 0.000153984 | 0.0000769920 |
| [20261021T191712Z-44af22](run-records/20261021T191712Z-44af22/run.json) | city-production__en__2400x1080__probe-overflow-worker__1271452.png | 1 | 1836 | 0 | 1836 | 30 | 1866 | 0.0005868 | 0.00029340 |
| [20261021T191714Z-e425ce](run-records/20261021T191714Z-e425ce/run.json) | city-production__en__2400x1080__probe-overflow-worker__1271452.png | 1 | 1836 | 1664 | 172 | 63 | 1899 | 0.000137184 | 0.0000685920 |
| [20261021T191932Z-d9ffa2](run-records/20261021T191932Z-d9ffa2/run.json) | tech-picker__de__2400x1080__probe-wrong-language-fallback__1271453.png | 1 | 1836 | 0 | 1836 | 30 | 1866 | 0.0005868 | 0.00029340 |
| [20261021T191934Z-724fbb](run-records/20261021T191934Z-724fbb/run.json) | tech-picker__de__2400x1080__probe-wrong-language-fallback__1271453.png | 1 | 1836 | 1664 | 172 | 27 | 1863 | 0.000093984 | 0.0000469920 |
| [20261021T192106Z-be2cea](run-records/20261021T192106Z-be2cea/run.json) | city-production__de__2400x1080__probe-wrong-language-foreign__1271454.png | 1 | 1836 | 0 | 1836 | 160 | 1996 | 0.0007428 | 0.00037140 |
| [20261021T192108Z-23a082](run-records/20261021T192108Z-23a082/run.json) | city-production__de__2400x1080__probe-wrong-language-foreign__1271454.png | 1 | 1836 | 1664 | 172 | 160 | 1996 | 0.000253584 | 0.0001267920 |
| [20261021T192110Z-eca08b](run-records/20261021T192110Z-eca08b/run.json) | city-production__en__2400x1080__probe-wrong-language-foreign__1271454.png | 1 | 1836 | 0 | 1836 | 156 | 1992 | 0.000738 | 0.0003690 |
| [20261021T192113Z-9ed206](run-records/20261021T192113Z-9ed206/run.json) | city-production__en__2400x1080__probe-wrong-language-foreign__1271454.png | 1 | 1836 | 1664 | 172 | 156 | 1992 | 0.000248784 | 0.0001243920 |
| [20261021T192526Z-a462f9](run-records/20261021T192526Z-a462f9/run.json) | tech-picker__de__2400x1080__probe-placeholder-tech__1271455.png | 1 | 1836 | 0 | 1836 | 27 | 1863 | 0.0005832 | 0.00029160 |
| [20261021T192529Z-130955](run-records/20261021T192529Z-130955/run.json) | tech-picker__de__2400x1080__probe-placeholder-tech__1271455.png | 1 | 1836 | 1664 | 172 | 27 | 1863 | 0.000093984 | 0.0000469920 |
| [20261021T192531Z-7bb89c](run-records/20261021T192531Z-7bb89c/run.json) | tech-picker__en__2400x1080__probe-placeholder-tech__1271455.png | 1 | 1836 | 0 | 1836 | 30 | 1866 | 0.0005868 | 0.00029340 |
| [20261021T192533Z-1179ee](run-records/20261021T192533Z-1179ee/run.json) | tech-picker__en__2400x1080__probe-placeholder-tech__1271455.png | 1 | 1836 | 1664 | 172 | 30 | 1866 | 0.000097584 | 0.0000487920 |
| [20261021T193656Z-4395d8](run-records/20261021T193656Z-4395d8/run.json) | city-production__de__2400x1080__probe-placeholder-city__1271456.png | 1 | 1836 | 0 | 1836 | 119 | 1955 | 0.0006936 | 0.00034680 |
| [20261021T193658Z-52cb3a](run-records/20261021T193658Z-52cb3a/run.json) | city-production__de__2400x1080__probe-placeholder-city__1271456.png | 1 | 1836 | 1664 | 172 | 119 | 1955 | 0.000204384 | 0.0001021920 |
| [20261021T193700Z-68873e](run-records/20261021T193700Z-68873e/run.json) | city-production__en__2400x1080__probe-placeholder-city__1271456.png | 1 | 1836 | 0 | 1836 | 30 | 1866 | 0.0005868 | 0.00029340 |
| [20261021T193702Z-8dbcb6](run-records/20261021T193702Z-8dbcb6/run.json) | city-production__en__2400x1080__probe-placeholder-city__1271456.png | 1 | 1836 | 1664 | 172 | 30 | 1866 | 0.000097584 | 0.0000487920 |
| [20261021T194040Z-e60d0f](run-records/20261021T194040Z-e60d0f/run.json) | tech-picker__de__2400x1080__probe-truncation-mining__1271457.png | 1 | 1836 | 0 | 1836 | 58 | 1894 | 0.0006204 | 0.00031020 |
| [20261021T194043Z-772638](run-records/20261021T194043Z-772638/run.json) | tech-picker__de__2400x1080__probe-truncation-mining__1271457.png | 1 | 1836 | 1664 | 172 | 69 | 1905 | 0.000144384 | 0.0000721920 |
| [20261021T194044Z-5800a2](run-records/20261021T194044Z-5800a2/run.json) | tech-picker__en__2400x1080__probe-truncation-mining__1271457.png | 1 | 1836 | 0 | 1836 | 68 | 1904 | 0.0006324 | 0.00031620 |
| [20261021T194047Z-e39bbe](run-records/20261021T194047Z-e39bbe/run.json) | tech-picker__en__2400x1080__probe-truncation-mining__1271457.png | 1 | 1836 | 1664 | 172 | 57 | 1893 | 0.000129984 | 0.0000649920 |
| [20261021T194220Z-cfcd3b](run-records/20261021T194220Z-cfcd3b/run.json) | tech-picker__de__2400x1080__probe-small-text-tech__1271458.png | 1 | 1836 | 0 | 1836 | 27 | 1863 | 0.0005832 | 0.00029160 |
| [20261021T194222Z-e17536](run-records/20261021T194222Z-e17536/run.json) | tech-picker__de__2400x1080__probe-small-text-tech__1271458.png | 1 | 1836 | 1664 | 172 | 27 | 1863 | 0.000093984 | 0.0000469920 |
| [20261021T194224Z-e02c81](run-records/20261021T194224Z-e02c81/run.json) | tech-picker__en__2400x1080__probe-small-text-tech__1271458.png | 1 | 1836 | 0 | 1836 | 30 | 1866 | 0.0005868 | 0.00029340 |
| [20261021T194226Z-1f0332](run-records/20261021T194226Z-1f0332/run.json) | tech-picker__en__2400x1080__probe-small-text-tech__1271458.png | 1 | 1836 | 1664 | 172 | 30 | 1866 | 0.000097584 | 0.0000487920 |
