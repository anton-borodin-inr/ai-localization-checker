# Decision log

Decisions that shape the project: scope, methodology, data and evaluation. Small implementation choices (naming, helper libraries) are not logged here.

## Rules

- One entry per decision. After acceptance, an entry is never edited except for its status.
- To change a decision, add a new entry that supersedes the old one, and set the old entry's status to `Superseded by D-XXX`.
- Claude Code reads this file before planning a task. A decision made during a task is added as a new entry with status `Proposed`; Anton accepts or rejects it.

## Template

```markdown
## D-XXX — Short title

- **Date:** YYYY-MM-DD
- **Status:** Proposed | Accepted | Rejected | Superseded by D-YYY
- **Decision:** what was decided, in one or two sentences
- **Why:** the reason or the evidence behind it
- **Alternatives considered:** what else was on the table and why it lost
- **Consequences:** what this changes in the plan or the code
```

---

## D-001 — Localization checker first, config-diff analyzer second

- **Date:** 2026-10-17
- **Status:** Accepted
- **Decision:** The first project is the visual localization checker on Unciv. The config-diff test-impact analyzer (Wesnoth / CDDA) is a separate, later project.
- **Why:** TODO (Anton)
- **Consequences:** Nothing in this repository depends on the config-diff analyzer.

## D-002 — Emulator instead of a physical device

- **Date:** 2026-10-17
- **Status:** Accepted
- **Decision:** All screenshots are captured on an Android emulator (arm64-v8a image, API 33–34, no Google Play, so that `adb root` is available).
- **Why:** TODO (Anton)
- **Consequences:** Settings files can be replaced through `adb` before launch; screen size and density are fully controllable.

## D-003 — Capture and analysis are separate steps

- **Date:** 2026-10-17
- **Status:** Accepted
- **Decision:** All screens are captured first; detectors then run over the folder of screenshots.
- **Why:** Detectors can be re-run and compared on exactly the same images without the emulator, which makes evaluation reproducible.
- **Consequences:** Screenshot file names are deterministic: `screen__lang__res__variant__build.png`.

## D-004 — A local model is allowed under the same criteria

- **Date:** 2026-10-17
- **Status:** Accepted
- **Decision:** A local vision model may be chosen if it passes the same quality and hallucination criteria as the cloud models.
- **Why:** The choice of model is decided by measured results, not by where the model runs.
- **Consequences:** Local models are evaluated with the same harness; they are an extension after v1.

## D-005 — Vertical slice before scaling

- **Date:** 2026-10-17
- **Status:** Accepted
- **Decision:** One screen × two languages × one injected defect goes through the whole chain (capture → baseline → model → metrics → table) before anything is scaled up.
- **Why:** Problems that could kill the approach (for example, small text becoming unreadable after the provider downscales the image) surface before time is invested in scale.
- **Alternatives considered:** Building each stage fully before the next one; rejected because the first metrics would appear only at the end.
- **Consequences:** Stage 1 of the plan is the vertical slice.

## D-006 — Scope of v1

- **Date:** 2026-10-17
- **Status:** Accepted
- **Decision:** v1 uses one provider, one screen resolution, 8–10 screens, 2 languages and 1–2 defect types. Results of v1 are reported as preliminary.
- **Why:** A finished small version is worth more than an unfinished large one. The source screen is the unit of the dev / hold-out split (D-010), so more screens matter more than more languages.
- **Alternatives considered:** 5 screens × 5 languages with several providers; moved to extensions.
- **Consequences:** Provider comparison, local models, more languages and resolutions, and ~100 defects per class are extensions after v1.

## D-007 — Usage scenario of v1

- **Date:** 2026-10-17
- **Status:** Accepted
- **Decision:** The tool flags suspicious places on screenshots; a QA engineer confirms or rejects each finding.
- **Why:** It defines both the requirements and how the benefit for QA is measured.
- **Consequences:** Still open: whether QA reviews only flagged places (then recall is the primary metric) or all screens with highlights (then precision and ranking matter more).

## D-008 — Matching findings by text, not by coordinates

- **Date:** 2026-10-17
- **Status:** Superseded by D-009
- **Decision:** Findings were to be matched to the labels only by the affected text (`text_seen`), using fuzzy string matching.
- **Why:** Vision models return imprecise coordinates.

## D-009 — Matching findings: type + text + coarse region

- **Date:** 2026-10-17
- **Status:** Accepted
- **Decision:** A finding matches a label only if the defect type matches. The affected text is the primary signal; a coarse screen region separates identical labels. The exact weights are set after the vertical slice (D-005).
- **Why:** Text-only matching breaks on identical labels in different places, duplicate findings and hallucinated text. Region-first matching would measure coordinate precision rather than detection, and would favour the OCR baseline, whose boxes are exact.
- **Alternatives considered:** Text only (D-008); region first.
- **Consequences:** Golden tests for matching cover truncated text, identical labels in different places, duplicate findings and hallucinated text.

## D-010 — Grouped dev / hold-out split, single-use hold-out

- **Date:** 2026-10-17
- **Status:** Accepted
- **Decision:** Data is split into dev and hold-out by source screen: variants of the same screen never appear in both sets. Prompt, rules and model are chosen on dev; hold-out is used once, for the final check of the frozen solution.
- **Why:** Mutated variants of one screen in both sets leak information. A hold-out set reused to fix things becomes a dev set.
- **Consequences:** The hold-out set is stored outside the repository and outside the agent's working folder. This protects against tuning to it, but independence of the evaluation comes from the two rules above.

## D-011 — Build Unciv from source from Stage 1

- **Date:** 2026-10-17
- **Status:** Accepted
- **Decision:** Unciv is built from source starting with the vertical slice; the F-Droid APK is used only for the first screenshots.
- **Why:** A source build is needed to inject defects and to add a debug hook that opens a screen directly, without coordinate-based navigation.
- **Consequences:** The debug hook is part of Stage 2.

## D-012 — Who owns labels and metric checks

- **Date:** 2026-10-17
- **Status:** Accepted
- **Decision:** Anton labels the data and writes the hand-computed examples that verify the metric code. Claude Code writes the metric and matching code.
- **Why:** If the agent labels data while looking at its own detector's output, the evaluation becomes circular. Hand-computed examples catch subtle errors in metric code.
- **Consequences:** Metric and matching code is always reviewed in detail, regardless of how confident the change looks.

## D-013 — A failed check is never "no defects"

- **Date:** 2026-10-17
- **Status:** Accepted
- **Decision:** A timeout, an API error or an invalid model response gives the screen the status "not checked". The report lists all screens that could not be checked.
- **Why:** Treating a failure as a clean result would hide defects and inflate precision.
- **Consequences:** Every run also stores the model version, the prompt and the settings.

## D-014 — v1 screen resolution: 1080 × 2400 at 420 dpi

- **Date:** 2026-10-17
- **Status:** Accepted
- **Decision:** v1 captures all screens on one AVD with the Pixel 7 device profile: 1080 × 2400 px, 420 dpi. Unciv runs in landscape, so screenshots are 2400 × 1080.
- **Why:** It is a typical modern phone profile, and the mid-high density keeps UI text at a realistic physical size, which is where truncation and overlap defects appear.
- **Alternatives considered:** A lower resolution (for example 720 × 1600) would survive provider downscaling better but is less representative; a tablet profile changes the layout Unciv chooses.
- **Consequences:** The vertical slice (D-005) must check whether text stays readable after the provider downscales a 2400-px image. If it does not, this decision is revisited. The display cutout is disabled on the emulator, so screenshots contain only the game.

## D-015 — Project-local Appium with its own APPIUM_HOME

- **Date:** 2026-10-17
- **Status:** Superseded by D-022
- **Decision:** Appium is pinned in the repository's `package.json` / `package-lock.json` and installed with `npm ci`; its drivers live in `./.appium` (`APPIUM_HOME`). The global Appium is not used.
- **Why:** The global Appium and `~/.appium` drivers are shared with other projects on the machine and can change under us. A pinned local install makes the environment reproducible and checkable.
- **Alternatives considered:** Reusing the global Appium 3.3.1 as is; rejected because its versions are not recorded in the repository and other projects may upgrade it.
- **Consequences:** Contributors need Node; `node_modules/` and `.appium/` are gitignored; the Appium server is started with `npm run appium`.

## D-016 — Capture build identifier and overwrite policy

- **Date:** 2026-10-17
- **Status:** Accepted
- **Decision:** Use the installed Unciv APK `versionCode` as the D-003 filename build field. Refuse an existing destination unless the user passes `--overwrite`.
- **Why:** The numeric APK code identifies the installed build; explicit overwrite protects a previous capture.
- **Alternatives considered:** `versionName`; automatic overwrite on every run.
- **Consequences:** A Stage 0 filename ends in `__1271.png`. Repeating the same capture requires a different output folder or explicit overwrite.

## D-017 — v1 model and request settings

- **Date:** 2026-10-17
- **Status:** Accepted
- **Decision:** The v1 provider (D-006) is `gemini-3.6-flash` on the Gemini API free tier. Requests use structured output (`application/json` with the finding schema), temperature 0 and `media_resolution` `MEDIA_RESOLUTION_HIGH`. The SDK's own retries are disabled; one retry after HTTP 429 is allowed only within the per-run request cap. The default timeout is 180 s (`--timeout`), and a server-side `504 DEADLINE_EXCEEDED` is reported as `timeout`.
- **Why:** The SDK sends the timeout to the server as `X-Server-Timeout`; with 60 s, the first image call (run `20261017T182052Z-fb1925`) was cut off by the server after 59.2 s with no response. Every generation request to `gemini-3.8-flash` ended in 504: two image requests (60 s and 180 s) and a one-line text-only probe (30 s). The same text probe on `gemini-3.6-flash` answered in 1.8 s, while the key and `models.list` worked. `media_resolution` is set explicitly because the API default is not recorded and can change; HIGH matches the 1078 image tokens of the live run. Disabling SDK retries makes the request cap count real requests.
- **Alternatives considered:** `gemini-3.8-flash` (504 on the free tier); the paid tier with 3.8 (out of scope for issue #3); `gemini-3.5-flash-lite` (weaker on small text, which D-014 must check).
- **Consequences:** Every run records the requested model id, the `model_version` the API returns and all request settings, including `media_resolution` and `timeout_s`. Free-tier inputs may be used by Google to improve its products. 3.8 can be re-checked with `scripts/gemini_probe.py text`.

## D-018 — Draft v0 finding schema

- **Date:** 2026-10-17
- **Status:** Accepted
- **Decision:** A finding has `defect_type` (`truncated_text`, `overlap`, `untranslated`, `other`), `text_seen`, `region` on a 3×3 screen grid and `confidence` in 0..1. The schema is a draft and is finalized in Stage 1.
- **Why:** The 3×3 grid is the coarse region D-009 needs to separate identical labels without measuring coordinate precision. `other` lets the model report a defect without forcing it into a v1 class; `other` findings never match a label.
- **Alternatives considered:** Normalized bounding boxes (measure coordinate precision, which D-009 avoids); only the v1 defect types.
- **Consequences:** Matching (Stage 1) uses type + `text_seen` + grid cell. Stage 1 decides whether the schema needs a way for the model to report unreadable text, so that such a screen is `not_checked` instead of `checked` with no findings.

## D-019 — Resolve source-test imports independently of editable .pth files

- **Date:** 2026-10-18
- **Status:** Accepted
- **Decision:** Set pytest's built-in `pythonpath = ["src"]` in `pyproject.toml`. Keep uv's editable installation and the supported Python range unchanged.
- **Why:** A clean install on Anton's Mac produced hidden `.pth` files that Python skipped, preventing test collection. A controlled hidden-file comparison failed without the source path and passed with it while the file remained hidden. The process that originally set the flag is still unknown.
- **Alternatives considered:** Pinning Python (3.12.4, 3.13.13 and 3.14.0 all skipped a hidden `.pth`); uv `link-mode = "copy"` (both clone and copy produced importable files in the controlled cache experiment, so a causal fix was not established); non-editable installation (plain `uv run` reinstalls the project as editable); wrappers or manual flag changes (investigation only).
- **Consequences:** `uv sync` then `uv run pytest` runs source tests without manual import setup. This does not repair an installed package's hidden hook or identify the flag setter; standalone import and CLI smoke checks remain separate from pytest. No dependency, interpreter pin or lockfile change is needed.

## D-020 — Candidate v1 defect types after Unciv source research

- **Date:** 2026-10-19
- **Status:** Accepted
- **Decision:** Require both `untranslated` and `truncated_text` as the two v1 classes; defer `overlap`. Keep the D-018 schema unchanged.
- **Why:** **source:** Unciv 4.22.10 / 1271 falls back to original text for missing translations and supports ellipsis on selected titles. **observed:** The English/Russian main-menu check confirmed language switching and wider buttons with fitting text. **assumption — evaluation rationale:** Truncation is the class where a vision model can add value over the OCR + translation-table baseline; untranslated alone risks a slice where the model cannot be shown to beat that baseline. Requiring both classes makes that comparison part of v1; it does not claim superiority before measurement. Evidence and pinned links are in [the research document](unciv-text-rendering.md).
- **Alternatives considered:** **assumption:** An untranslated-only slice (insufficient opportunity to demonstrate vision-model value over the baseline); overlap as a third class (deferred, outside D-006's two-class selection); deciding that all ellipsis or scroll-hidden text is defective here (deferred to Anton's label definitions).
- **Consequences:** **assumption — planned verification:** The observed failure and clean control are established in [#8](https://github.com/anton-borodin-inr/ai-localization-checker/issues/8), following the transfer of that criterion out of #7. Anton decides whether intentional ellipsis or content hidden in a scroll viewport counts as a defect when labels are defined; this PR leaves that boundary open. No Accepted decision is superseded, and this entry remains Proposed until Anton accepts it after review.

## D-021 — v1 languages: English and German

- **Date:** 2026-10-19
- **Status:** Accepted
- **Decision:** The two v1 languages (D-006) are English and German. Unciv's `language` value for the second language is `German`; filenames use `en` and `de`.
- **Why:** Unciv 4.22.10 translation completeness (`android/assets/jsons/translations/completionPercentages.properties` at `899367522`) is German 99, Russian 99, Finnish 56. Finnish would leave about half of the strings naturally untranslated, which would bury an injected defect. German over Russian: both English and German use the Latin script, so an `untranslated` English string cannot be spotted by a change of script alone, which keeps the `untranslated` class meaningful for the baseline-vs-model comparison (D-020). German strings tend to be longer than English ones, which makes natural `truncated_text` cases more likely; that class is required in v1 (D-020).
- **Alternatives considered:** Russian (99 %, but a script change makes `untranslated` trivial for the baseline); Finnish (56 %, too much natural untranslated text).
- **Consequences:** Anton does not read German. Labels are made by comparing the expected string from the translation file with what is visible on screen; telling intentionally shared terms (names, acronyms) from real untranslated text is harder and is handled when labels are defined. `l10n-capture` accepts `--lang en` and `--lang de` only.

## D-022 — Plain adb instead of Appium in the capture path

- **Date:** 2026-10-19
- **Status:** Accepted
- **Decision:** Replace the Appium session in `l10n-capture` with SDK `adb`: `exec-out screencap -p` for the PNG and `dumpsys activity activities` for the foreground check. Keep the project-local Appium install (D-015) until the change is made and verified; this entry does not make the change.
- **Why:** Facts gathered in issues #2 and #9 on Unciv 4.22.10 / 1271, API 34 AVD, Appium 3.3.1, uiautomator2 7.1.2:
  - **What Appium gives on a LibGDX canvas:** a `page_source` read on the main menu returned 10 nodes (`FrameLayout`, `LinearLayout`, `View`) and no text attribute. The whole game is one view, so Appium supplies only `current_package` and a screenshot, both of which adb provides directly. The language step (#9) already uses adb for the foreground check.
  - **Setup cost:** Node, `npm ci`, a driver install into `./.appium`, and a server process that must be running and must see `ANDROID_HOME` in its environment. The first #9 live run failed because the server was started without it; adb needs none of this.
  - **Capture time:** retrieval plus write was 0.173 s (Appium) vs 0.185 s (adb) per screenshot in #2, plus 1.45 s (#2) and 1.51 s (#9) of Appium session setup per session. A two-language run took 29.9 s end to end, of which 16 s is the fixed settle wait; the transport difference is small either way.
  - **Stability:** the language step needs `adb root` / `adb unroot`, which restarts adbd and drops the port forwards uiautomator2 uses. The capture code must therefore open the Appium session only between the two restarts; plain adb has no such ordering constraint.
- **Alternatives considered:** Keep Appium (D-015): adds no information on this app, costs a server and session per capture. Use Appium only where native Android UI appears (dialogs, permission prompts): not needed in v1, can be revisited for the second app (Stage 8).
- **Consequences:** If accepted, a follow-up task replaces `appium_session` in `capture.py` and `scripts/benchmark_capture.py`, removes `appium-python-client` and the Appium checks from the capture path and `check_env.sh`, and supersedes D-015. Until then, capture keeps working through Appium as documented in `docs/capture.md`.

## D-023 — Ellipsis defect boundary for Unciv

- **Date:** 2026-10-19
- **Status:** Accepted
- **Accepted by:** Anton
- **Decision:** An ellipsis counts as `truncated_text` when the full text is not visible anywhere else on the same screenshot. If the full text is visible elsewhere on that screenshot, the shortened label is not a defect.
- **Why:** **observed — issue 8 probe:** On Unciv 4.22.10, the long German Worker title wrapped in the construction list and remained fully visible in the selected-construction panel; the long German Mining title ended in an intentional ellipsis in TechButton. No text loss without a marker was observed in these two probes. **Anton's QA interpretation:** Losing the technology name on its button loses its meaning on that screen, which localization QA treats as a defect when the full name is unavailable elsewhere in the same screenshot.
- **Alternatives considered:** Exclude all intentional ellipsis from defects; count every shortened label even when another element on the same screenshot shows its full text; require text loss without a marker for the first slice.
- **Consequences:** The issue 8 pair uses only the Mining injection, with another technology selected so the full Mining name does not appear in the description panel or elsewhere in the screenshot. The OCR + translation-table baseline is expected to catch this case easily, so v1 may show no model advantage on this class; this is an expectation, not a measured result. Text loss without a marker is left for Stage 8 (second app). Probe images remain exploration only; Anton owns final labels. D-018's detector schema and D-020's two v1 classes remain unchanged.

## D-024 — Exploratory source-build probe and manual Stage 1 screen capture

- **Date:** 2026-10-19
- **Status:** Proposed
- **Decision:** Before selecting issue 8's final injection, build one exploratory German probe with Mining and Worker changes and versionCode 1271009. Anton manually opens both screens; probe images appear only as exploration in the Report and never enter labels or evaluation. The final pair uses only Anton's chosen injection, with separate clean/defective versionCodes. Capture uses SDK adb after manual navigation, retaining D-014 cutout checks and D-003/D-016 names. Propose a small human-written JSON label file with screenshot/language and labels containing type, expected text, visible text and a 3x3 region.
- **Why:** The current capture CLI relaunches into the main menu, while Stage 2 navigation/debug hooks are out of scope. TechButton ellipsis is predictable from source, but the Worker title can enlarge its panel; actual screen behavior must precede Anton's choice. Anton requested the preliminary probe after approving the initial plan.
- **Alternatives considered:** Choose solely from source predictions; inject artificial sentences; add a navigation/debug hook now; recreate a different game for each final screenshot.
- **Consequences:** Probe observations are not labels. Anton's accepted ellipsis boundary is recorded separately in D-023. The final pair shares pinned upstream base 899367522cea36d6063c84b02b41eedfa9a0d0e9; BuildConfig.kt changes are metadata only. Every app deletion/replacement and explicit app-data overwrite requires a separate confirmation. No detector/matching schema changes. This workflow proposal was originally numbered D-023 before acceptance and was moved to D-024 when Anton explicitly assigned D-023 to the defect boundary.

## D-025 — Labeling rules: scroll clipping and region

- **Date:** 2026-10-19
- **Status:** Accepted
- **Accepted by:** Anton
- **Decision:** Text or elements cut off at the edge of a scrollable area are not labeled as defects when the full content becomes visible by scrolling. A label's `region` is the 3×3 grid cell that contains the centre of the text's bounding box. The rules are kept in [labeling.md](labeling.md).
- **Why:** On the issue 8 German technology picker, the description panel cuts off the last line at the bottom edge and the technology tree cuts off a technology at the top edge; Anton checked on the device that scrolling shows the full content. The injected `Bergbau und Erzgew...` title lies across the border of the left and centre columns, so a rule is needed for matching (D-009) to be reproducible.
- **Alternatives considered:** Label scroll clipping as `truncated_text` (rejected: no text is lost to the player); region = the cell where the text starts (rejected: depends on reading direction and on small horizontal shifts).
- **Consequences:** The issue 8 German labels follow these rules. Detector findings on scroll-clipped text count as false positives. Future screens with fixed, non-scrollable clipping are judged separately.
