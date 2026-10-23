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
- **Status:** Superseded by D-026
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
- **Status:** Superseded by D-034
- **Decision:** The v1 provider (D-006) is `gemini-3.6-flash` on the Gemini API free tier. Requests use structured output (`application/json` with the finding schema), temperature 0 and `media_resolution` `MEDIA_RESOLUTION_HIGH`. The SDK's own retries are disabled; one retry after HTTP 429 is allowed only within the per-run request cap. The default timeout is 180 s (`--timeout`), and a server-side `504 DEADLINE_EXCEEDED` is reported as `timeout`.
- **Why:** The SDK sends the timeout to the server as `X-Server-Timeout`; with 60 s, the first image call (run `20261017T182052Z-fb1925`) was cut off by the server after 59.2 s with no response. Every generation request to `gemini-3.8-flash` ended in 504: two image requests (60 s and 180 s) and a one-line text-only probe (30 s). The same text probe on `gemini-3.6-flash` answered in 1.8 s, while the key and `models.list` worked. `media_resolution` is set explicitly because the API default is not recorded and can change; HIGH matches the 1078 image tokens of the live run. Disabling SDK retries makes the request cap count real requests.
- **Alternatives considered:** `gemini-3.8-flash` (504 on the free tier); the paid tier with 3.8 (out of scope for issue #3); `gemini-3.5-flash-lite` (weaker on small text, which D-014 must check).
- **Consequences:** Every run records the requested model id, the `model_version` the API returns and all request settings, including `media_resolution` and `timeout_s`. Free-tier inputs may be used by Google to improve its products. 3.8 can be re-checked with `scripts/gemini_probe.py text`.

## D-018 — Draft v0 finding schema

- **Date:** 2026-10-17
- **Status:** Accepted; its rule that `other` findings never match is superseded by D-026
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
- **Status:** Accepted
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

## D-026 — Matching and metrics: type-free detection plus a confusion table

- **Date:** 2026-10-19
- **Status:** Accepted
- **Accepted by:** Anton
- **Decision:** Findings are matched to labels in two levels. **Detection** ignores the defect type: a finding matches a label when its text identifies the label. **Classification** reports, for matched findings, a confusion table of label type against finding type, including `other`. Rules:
  - Text match: near-exact text (for example one misread letter) or a long enough beginning of the visible text matches; a single word that does not identify the label does not. The threshold is a parameter, constrained by golden cases 08a–08c.
  - Region: used only to separate identical texts on the same screen; for a unique text the region is ignored.
  - Duplicates: several findings about the same label are collapsed into one and are not FP.
  - `other`: an `other` finding at the right text is a detection TP and appears in the confusion table as "type not determined".
  - Hallucination: a finding whose text is not on the screen at all is a FP and is also counted separately.
  - Not checked: recall is reported twice, on checked screens only and on all screens (labels on `not_checked` screens count as FN), together with the number of `not_checked` screens.
  - Zero denominators give undefined precision or recall, never 0 or 1.
- **Why:** From the QA point of view, a finding at the right place with the wrong category still points the engineer to a real bug (Anton). A single type-strict number would hide that value, while a type-free number alone would hide whether the model understands what is broken; truncation and missing translation are fixed differently. Two levels show both. Recall on all screens shows what QA really gets; recall on checked screens shows model quality without API failures.
- **Alternatives considered:** Type-strict matching (D-009); type-free matching without a confusion table; counting duplicates as FP; exact-region or neighbour-region matching.
- **Consequences:** Supersedes D-009, and D-018's rule that `other` never matches. Golden cases are in `tests/golden/matching_cases.json`. Issue #13 implements these rules; per-class figures are derived from the confusion table.

## D-027 — Labeling technical text in v1

- **Date:** 2026-10-19
- **Status:** Accepted
- **Accepted by:** Anton
- **Decision:** In v1, a raw string key or identifier shown instead of translated text is labeled `untranslated` with `note` "raw key". A broken placeholder (for example `[amount]` shown literally, or a wrong substitution) is labeled `other` with a note describing it. A separate class for technical text is considered after v1.
- **Why:** In Unciv, keys are English source strings, so a missing translation shows English text (`untranslated`); raw identifiers are unlikely but possible in other apps. Broken placeholders are possible in Unciv templates and are planned as Stage 3 mutations. D-006 and D-020 keep v1 at two classes; with type-free detection (D-026), a detector that finds such a defect still gets a TP.
- **Alternatives considered:** A third class now (outside v1 scope); labeling broken placeholders as `untranslated` (mixes different fixes).
- **Consequences:** `docs/labeling.md` lists the rule. The notes allow splitting the classes later without relabeling.

## D-028 — The coding agent may run live free-tier calls within the issue budget

- **Date:** 2026-10-19
- **Status:** Superseded by D-035
- **Accepted by:** Anton
- **Decision:** The coding agent runs the live provider calls of a task itself, instead of handing a command to Anton. Conditions: the issue states a request budget; calls go only through the project's commands with the per-run request cap; only the free-tier key; never the hold-out set; the agent never reads or prints `.env` or the key (`uv run --env-file .env` loads it); every run is recorded under `data/runs/` and the report lists run ids and `requests_sent`.
- **Why:** Anton does not want to run the live calls by hand for every experiment. The free tier has no spend, the request cap already exists in code and every request is recorded, so the agent's report can be checked against the run records rather than taken on trust.
- **Alternatives considered:** Keep live calls with Anton (previous rule; slower, a manual step in every experiment); allow paid calls (no billing in v1).
- **Consequences:** The hard rule in CLAUDE.md and AGENTS.md changes; issue constraints for #10 and #14 change accordingly. Review checks `data/runs/*/run.json` (or a committed summary of it) against the report. Free-tier inputs may be used by Google (already accepted in D-017).

## D-029 — Provisional text matching and duplicate representatives

- **Date:** 2026-10-19
- **Status:** Proposed
- **Decision:** For issue #13, normalize text to NFC, collapse whitespace and map `…` to `...`, preserving case, accents and other punctuation. Near-exact similarity is `1 - Levenshtein distance / max string length`, including the ellipsis, with configurable default threshold 0.90; empty strings never match. The prefix alternative requires a finding ending in an ellipsis: remove the terminal ellipsis from both texts, trim, then require an exact prefix with at least two whitespace-separated words and at least 0.50 coverage of the label's visible body. Prefix coverage and minimum words are also configurable (minimum words cannot be below two). Following Anton's PR #27 review (2026-10-20): a finding is scored against both `text_seen` and `text_expected` of a label, with the same rules; findings are assigned to labels one-to-one, maximizing the number of matched labels and then the total exact score; hallucination presence requires whole words.
- **Why:** Anton approved these provisional conventions in the issue #13 implementation plan. They satisfy golden cases 08a (one substitution in 21 characters), 08b (11/18 prefix coverage) and 08c (one word without an ellipsis). The PR #27 review showed three gaps in the first version: a model reporting the full intended text of a truncated label was a FP and a hallucination (now golden case 12); a greedy choice turned a finding into a duplicate although it identified a free label (now golden case 13); and a literal substring made any fragment, even one letter, "present". They specify D-026 without choosing the final threshold before the slice.
- **Alternatives considered:** Exact text only (misses 08a); arbitrary substring detection matching (accepts 08c); a new fuzzy-matching dependency (unnecessary for the small v0 inputs).
- **Consequences:** A finding's score for a label is the best of its two texts (maximum of accepted similarity and prefix coverage). The assignment is exact: it maximizes matched labels, then the total score as exact fractions; among equal assignments, findings are decided in input order, each preferring its lowest-index label. Identical normalized visible text occurrences, including clean occurrences listed in `screen_texts`, require the same grid cell; unique text ignores region. An unassigned finding that identifies a label is a collapsed duplicate (every label it identifies is already matched); the assigned finding is the representative and supplies the confusion-table type, without using type or confidence. An unassigned finding that identifies no label is a hallucination only when its body (terminal ellipsis removed) does not occur as whole words in a visible text, near-exact similarity does not establish presence, and it identifies no label's `text_expected`. Presence is weaker than label identification, so 08c is a FP without being a hallucination; a single letter inside a word is a hallucination. These conventions are documented in [matching-metrics.md](matching-metrics.md); final tuning remains Anton-owned.

## D-030 — Offline baseline v0 source context and frozen comparison rules

- **Date:** 2026-10-19
- **Status:** Proposed
- **Decision:** Baseline v0 resolves each screenshot to its own build commit through the filename and pair manifest, then renders a source-backed screen inventory with plain text, square-bracket arguments and curly-brace fragments. Use local Tesseract with fixed OEM 1 / PSM 11, `eng` for English and `deu+eng` for German; exact normalized comparison and a proper-prefix threshold of four letters and 50% of expected length. The approved implementation plan specified these settings before slice runs. Full details and rule precedence are in [baseline.md](baseline.md).
- **Why:** Comparing injected screenshots against clean-build strings would hide the actual lost suffix. Unciv's composed UI text cannot be checked against literal dictionary values alone. A small declared source inventory supplies the screen context that a translation file lacks, without deriving expectations from human labels or detector findings.
- **Alternatives considered:** EasyOCR (additional Python/model runtime); a whole-dictionary missing-text check (most entries are unrelated to this screen); clean translations for every screenshot (incorrect provenance); tuning away viewport/ellipsis candidates (would hide baseline false positives).
- **Consequences:** Tesseract plus English/German traineddata are system prerequisites; no new Python dependency. Human labels are never read by the baseline. Missing text carries the expected string as `text_seen` (from `baseline-v0.1`, after the PR #28 review; marked by index in `missing_rule_findings` in the run output), heuristic confidence 0.5 and an expected-slot region; observed candidates use OCR-box centre and mean word confidence. Missing or prefix text remains a truncation candidate, including scroll clipping and harmless ellipsis. Exact foreign alternatives/source fallbacks give untranslated candidates, recognized literal placeholders give `other`. Unsupported required rendering or failed OCR is `not_checked`. D-023/D-025 remain the human defect boundary; D-026 matching and metrics are untouched. Report every clean-control finding and preserve run records, with zero live provider requests.

## D-031 — Propose an explicit visible-text readability result

- **Date:** 2026-10-19
- **Status:** Accepted
- **Decision:** Propose a response-level `readability` value (`readable`, `partial`, `unreadable`), with `unreadable_regions` and a short reason. `partial` or `unreadable` makes the screen `not_checked`; raw partial observations may remain diagnostic evidence but never become a clean checked result. This is a proposal, not a production schema change in issue #10.
- **Why:** The current D-018 response describes defects only. An empty findings list cannot distinguish a clean screen from unreadable text. Issue #10 separated ordinary transcription from findings to measure reading, but a validated experimental response still does not prove all visible text was readable.
- **Alternatives considered:** A synthetic defect class for unreadability (mixes check failure with a localization defect); treating empty readings as sufficient proof (cannot identify partial omissions); adding a confidence threshold now (not calibrated).
- **Consequences:** A later schema task must define and test this mapping under D-013, including readable clean screens, partial text, blocked responses and deliberate viewport boundaries. Readability concerns text inside the visible viewport, not hidden scroll content or untranscribed icons. Anton accepts the final fields and criteria; D-018 remains unchanged until then.

## D-032 — Keep the current capture resolution; HIGH sufficed for Gemini on the clean screen

- **Date:** 2026-10-20
- **Status:** Proposed
- **Decision:** Retain D-014's 2400×1080 capture provisionally. Do not integrate tiling into the detector from issue #10 alone. For Gemini (D-017), issue #10 supports `MEDIA_RESOLUTION_HIGH` as sufficient for reading the clean German screen; `ULTRA_HIGH` was an experimental alternative, not a new default. `media_resolution` is a Gemini setting: since DeepSeek became the v1 provider (#32), the D-014 readability question for DeepSeek is covered by the DeepSeek runs of PR #29 and the #32 confirmation run, not by this entry.
- **Why:** On the German clean screen, Gemini HIGH and ULTRA_HIGH both read 16/16 primary reference units, with 1078 versus 2170 image tokens. ULTRA_HIGH read English clean 20/20 and German injected 20/20 (amended reference) and found the existing Mining defect in the correct region, but no HIGH counterpart exists for those screens and no complete three-crop variant succeeded. Of 27 Gemini free-tier requests, 19 failed (14 HTTP 503, 5 HTTP 429). Summary: [issue-10-small-text.md](experiments/issue-10-small-text.md).
- **Alternatives considered:** Switch to ULTRA_HIGH (no measured gain on the paired clean input, twice the image tokens); adopt three crops now (three requests, less shared context, ambiguous region mapping, incomplete comparison); reduce capture resolution (changes the representative UI without supporting evidence).
- **Consequences:** No Accepted decision is superseded and production defaults do not change. HIGH was not observed on the injected screen (all attempts returned 503); the defect-detection case for HIGH is still open. This is a preliminary result on one source screen, not proof that HIGH suffices for all v1 screens or that tiling cannot help. Final conclusions remain Anton's.

## D-033 — Keep small-text coverage separate from defect recall

- **Date:** 2026-10-19
- **Status:** Proposed
- **Decision:** Measure ordinary text transcription against a build-pinned reference confirmed by Anton before calls, separately from findings and the D-026 defect metrics. Preserve any later human-confirmed correction as an explicit version, including original scores: issue #10 corrected two omitted injected controls after all Gemini calls, changing that denominator from 18 to 20 without changing labels or thresholds. Exact comparison preserves case and accents after NFC/whitespace normalization; fuzzy uses a 0.90 SequenceMatcher threshold and comparable-length spans, with exact-only matching for short units. The protocol is summarized in [issue-10-small-text.md](experiments/issue-10-small-text.md); the code is `reading_metrics.py`, and Anton-confirmed examples are in `tests/golden/small_text_cases.json`.
- **Why:** D-018's `text_seen` describes suspected defects, not every visible string. Absence from findings cannot measure whether ordinary text was read. The reference lists deliberately clipped diagnostics separately, so invisible or incomplete viewport content does not inflate primary misses. Source/APK byte checks bind translations to each screenshot's build.
- **Alternatives considered:** Derive the reference from model output (circular); require every normal label to be a defect (changes finding semantics); call text coverage defect recall (misleading); penalize unique text for a wrong region (contradicts the separation in D-026).
- **Consequences:** Transcription needs its own response field (readings) next to the unchanged finding objects. Reference units are counted once across tile overlap; research-button text cannot stand in for a separate tree label. Failed variants have unavailable coverage, with partial evidence kept separate. This does not change D-026/D-029 matching, their thresholds, existing human labels or goldens.

## D-034 — v1 provider: DeepSeek `deepseek-flash`

- **Date:** 2026-10-20
- **Status:** Accepted
- **Accepted by:** Anton
- **Decision:** The v1 provider (D-006) is DeepSeek `deepseek-flash` on the official API (`https://api.deepseek.com/chat/completions`). Requests use non-thinking mode, temperature 0, `response_format` `json_object`, image `detail: original` with the PNG bytes sent unchanged, `max_tokens` 4096, a 120 s timeout, no streaming, no redirects and no transport retries; one retry after HTTP 429 is allowed only within the per-run request cap. The detector prompt and the finding schema (D-018) stay unchanged; JSON object mode does not enforce a schema, so a versioned format wrapper (`deepseek-json-object-v1`) appends the `ModelOutput` JSON Schema to the prompt, and the response is validated strictly and locally, never repaired. This supersedes the provider part of D-017.
- **Why:** The Gemini paid tier cannot be paid for from Anton's account (cross-country billing errors), and the Gemini free tier was unstable in #10 (19 of 27 requests failed with HTTP 503/429). In #29, 12 DeepSeek requests all returned a response, `detail: original` read the German clean screen 16/16, and the total cost was about USD 0.004–0.009. 4096 output tokens leave room for a findings list while bounding the worst-case cost of a request.
- **Alternatives considered:** Gemini paid tier (cannot be billed); Gemini free tier (unstable); the local Qwen adapter (#30; 2 of 14 validated responses in #10, dropped for now); `json_schema` response format (not offered by the DeepSeek API).
- **Consequences:** `l10n_checker.deepseek` is the only module that calls the DeepSeek API. Every run records the requested model, the model name the API returns (only the alias; no immutable model revision is available), `system_fingerprint` if present, all request settings, prompt and wrapper versions, token usage with cache hit/miss, and an estimated cost from a tariff snapshot kept in the code. After the #32 confirmation run, the Gemini adapter is removed and D-017 is set to `Superseded by D-034`. DeepSeek processes the screenshots under its own terms; they are screenshots of an open-source game.

## D-035 — The coding agent may run live paid calls within the issue budget in requests and USD

- **Date:** 2026-10-20
- **Status:** Accepted
- **Accepted by:** Anton
- **Decision:** The coding agent runs the live provider calls of a task itself, instead of handing a command to Anton. Conditions: the issue states a budget in requests and USD; calls go only through the project's commands with the per-run request cap; only the provider key named in the issue, within the issue budget in requests and USD across all runs of the task, failed requests included; never the hold-out set; the agent never reads or prints `.env` or the key (`uv run --env-file .env` loads it); every run is recorded under `data/runs/` and the report lists run ids, `requests_sent`, token usage and the estimated cost. This supersedes D-028 and restates all its conditions except the free-tier one.
- **Why:** D-034 moves v1 to a paid provider, so the "free-tier key only" condition of D-028 cannot hold. The DeepSeek account uses a small prepaid balance, which is the hard ceiling; the issue's USD budget and the per-run request cap keep each task far below it. The other D-028 reasons stay: the request cap exists in code, every request is recorded, and the report can be checked against the run records.
- **Alternatives considered:** Keep D-028 and give Anton every paid call (a manual step in every experiment); amend D-028 in place (the decision log does not edit accepted entries).
- **Consequences:** The hard rule in CLAUDE.md and AGENTS.md changes. Review checks `data/runs/*/run.json` (or a committed copy) against the report, including token usage and estimated cost.

## D-036 — Response schema v1 and labeling prompt v1

- **Date:** 2026-10-20
- **Status:** Accepted
- **Accepted by:** Anton
- **Decision:** Implement the D-031 acceptance recorded in issue #35: require `readability` (`readable`, `partial`, `unreadable`), `unreadable_regions` (3×3 cells) and `readability_reason` (string or null) alongside the unchanged D-018 finding objects. Enforce empty regions for `readable` and at least one for `partial`; `unreadable` allows none. Only `readable` produces checked findings; the other two produce `not_checked` with `unreadable_text`, retaining observations only in the raw diagnostic response. Prompt v1 expresses D-023/D-025/D-027 from `labeling.md`, plus the visible-viewport readability contract; response schema is `v1`, and the DeepSeek format wrapper is `deepseek-json-object-v2`.
- **Why:** Issue #35 explicitly authorizes the schema extension and labeling rules before confirmation calls. An empty defect list cannot establish that the screen was readable. The old detector prompt also lacked the accepted defect boundaries.
- **Alternatives considered:** Infer readability from findings (cannot distinguish a clean screen from unreadable text); expose partial findings as checked output (violates D-013); repair missing fields (hides an invalid model response); adjust the prompt after confirmation results (would tune it to the slice).
- **Consequences:** This proposes the v1 response that replaces D-018's v0 draft response while preserving every finding field. It updates the prompt/schema/wrapper versions used in D-034's #32 implementation; the provider and request settings remain those of D-034. New fields and consistency are strictly validated locally. Matching, metrics, labels, goldens and the OCR baseline are unchanged. The prompt and sent-schema hashes are frozen before live calls and recorded with every run; the three v1 screenshots are compared with #32 by identical PNG hashes. D-031's status is changed to Accepted on Anton's explicit instruction in issue #35; its original text is preserved.

## D-037 — Vertical-slice reference projection and replay evidence

- **Date:** 2026-10-20
- **Status:** Accepted
- **Accepted by:** Anton
- **Decision:** For issue #14, project the hash-confirmed amended #10 reference into `screen_texts` using every supplied `rows[*].text_seen` (including clipped diagnostics) and each supplied numeric diagnostic, preserving order and repeated entries. Never use hidden `assembled_full_text`, OCR, model output or inferred occurrences. Keep a portable hash-indexed bundle of input snapshots and detector records for offline replay through the unchanged evaluator.
- **Why:** Anton requires #10 as the sole source and owns any additions. Its 16/20/20 primary counts measure transcription coverage, not all visible occurrences. Excluding its known clipped diagnostics would discard available human-confirmed visible text, while reconstructing missing text or repetition would invent reference data.
- **Alternatives considered:** Primary rows only (discards supplied diagnostics); OCR or detector-derived completion (circular); completing counts, punctuation or spans from inspection (requires Anton's confirmation); changing matching to compensate (outside #14).
- **Consequences:** Every table names the reference and states its limitations. The report lists concrete gaps without filling them. Raw responses, readability, hashes, API accounting and matching settings remain auditable. No Accepted decision or detector/evaluator behavior changes. Number assigned after rebasing onto main e2b268c, which includes PR #37 and has D-036 as its last numbered entry.

## D-038 — Deterministic Android screen launch state protocol

- **Date:** 2026-10-21
- **Status:** Accepted
- **Accepted by:** Anton
- **Decision:** The Stage 2 Unciv hook accepts three Android string extras: `l10n_screen`, a unique `l10n_request`, and `l10n_state_b64` (standard padded base64 of UTF-8 JSON). State schema version 1 fixes `save`, `selection`, `tab`, `expanded_sections`, `scroll`, `scroll_to`, `camera` and `new_game`. Source-key anchors are preferred over absolute Scene2D offsets; unavailable, ambiguous or out-of-range state fails explicitly. Every request, including `onNewIntent`, reloads the save and rebuilds the screen. `L10N_SCREEN_READY <id> request=<request>` is emitted only after state application and at least two quiet rendered frames with no pending tracked UI work or actions; failures emit `L10N_SCREEN_ERROR` and leave a blank screen. Language remains the normal Unciv setting.
- **Why:** The companion capture task [#41](https://github.com/anton-borodin-inr/ai-localization-checker/issues/41) needs a stable contract from [#40](https://github.com/anton-borodin-inr/ai-localization-checker/issues/40). Base64 avoids adb shell quoting failures for names with spaces or Unicode; anchors adapt to English/German layout differences; fresh reconstruction prevents order-dependent captures; frame-based readiness avoids a fixed settle delay. Anton approved these requirements in the issue #40 implementation plan on 2026-10-21.
- **Alternatives considered:** Raw JSON extras (shell quoting); offsets alone (language-dependent content heights); reusing previous screen state (selection/scroll leakage); readiness at construction or after a fixed delay (unfinished layout or asynchronous previews).
- **Consequences:** The implementation and full field semantics live in the separate [Unciv fork PR](https://github.com/anton-borodin-inr/Unciv/pull/1), based on `899367522cea36d6063c84b02b41eedfa9a0d0e9`. Version the protocol when changing its contract. The hook is Android debug-only, suppresses transient hints/popups and freezes capture animation without persisting hook settings or autosaves. Fixture/settings/manifest/capture-loop ownership remains with #41; the expressly authorized Belgrade-met save is a documented fixture candidate, not an accepted fixture. Verified on fork commit `c66d109fbe574cb3a9824fe3e346f0b0bd0ae4b2`, versionCode 1271045: all ten German screens reached `L10N_SCREEN_READY` and repeated A → B → A with 0 changed pixels, and twelve invalid-input cases produced `L10N_SCREEN_ERROR` with a blank screen ([issue #40 report](https://github.com/anton-borodin-inr/ai-localization-checker/issues/40#issuecomment-6316485767)). English layout is not verified yet and belongs to #41. D-003, D-014, D-016, D-021, D-022 and D-024 remain unchanged. Number assigned against main `d6b392b`, where D-037 is the last entry.

## D-039 — Stage 2 screen fixtures and order-sensitive repeatability

- **Date:** 2026-10-21
- **Status:** Accepted
- **Accepted by:** Anton
- **Decision:** Capture these ten source screens: `options-gameplay`, `new-game`, `tech-picker`, `city-production`, `empire-stats`, `policy-picker`, `victory-status`, `civilopedia`, `world`, `city-state-diplomacy`. The main game screen replaces the exploratory map editor. Screen 09 explicitly accepts the empty notification list on turn 1 of `issue-8-pair`. Screen 10 alone uses the separate `issue-40-belgrade-metissue-8-pair` save, SHA-256 `2cf381aa7bf544961a302989c027045572b8d7036ab1840b01bc3ee4409c551e`; every other in-game screen uses the unmodified base save. Both language settings templates carry the same fixed, non-personal `lastGameSetup`, because Unciv shows the New Game "Reset to defaults" button only when it is non-null (`NewGameScreen.kt:107` at `877b0dc`); the D-038 `new_game` state still sets every displayed field.
- **Why:** Anton approved the #41 plan and both fixture choices on 2026-10-21. The Belgrade save preserves normal first-contact effects (+30 gold), so it must not replace the base economy on other screens. Same-order repeats cannot expose order dependence; Anton requires the second pass in reverse screen order.
- **Alternatives considered:** Map editor (replaced by World); fabricate notifications or advance/change the base game (unnecessary for the accepted empty list); use the Belgrade save everywhere (changes economy); two same-order passes (weaker verification).
- **Consequences:** Commit fixtures, provenance and fixed settings with a hash-pinned manifest. Each of two passes keeps languages outside the screen loop and starts a fresh app per language; pass 1 is forward, pass 2 reverse. Compare decoded pixels for each screen/language pair, retaining failures and non-identical results. Use D-038 unchanged. No detector, truncation check, labels or split is performed. D-025's two outstanding human scroll checks remain report items. Number checked against main `eb5616d` before implementation; recheck before merge.

## D-0XX — Additive hook protocol v2 and rendered text outputs

- **Date:** 2026-10-21
- **Status:** Proposed
- **Decision:** Keep D-038 Accepted for v1 and opt into protocol v2 with `l10n_protocol=2`, retaining state schema v1 and existing events. V2 additionally publishes a deterministic engine text dump and a hash-bearing DUMP event before READY. Bind dump and PNG hashes in capture sidecars; list every temporary/final dump path as a hook output in the separately approved device plan.
- **Why:** Issue #47 needs build-pinned rendered strings and clipping geometry without deriving references from OCR/model output. A file avoids logcat line-size limits. Request IDs and timing belong to transport provenance, outside deterministic dump bytes. Anton approved the implementation plan on 2026-10-21.
- **Alternatives considered:** Replace v1 or change D-038 in place (breaks the Accepted contract); log the entire dump (size limits); traverse label strings only (includes undrawn text and hidden ellipsis suffixes).
- **Consequences:** Actual draw/cache observation and the four #44 robustness fixes live only in the separate fork. The checker supports v1 and v2, retains D-039 fixtures/order, checks dump identity and repeated bytes, and records outputs separately from settings/saves. Device work waits for emulator release and exact-operation confirmation. See [engine-text-reference.md](engine-text-reference.md). This entry remains D-0XX until rebasing before merge alongside #45/#48.

## D-0XX — Engine candidates, occurrence units and hash-bound human review

- **Date:** 2026-10-21
- **Status:** Proposed
- **Decision:** Generate unconfirmed D-033-compatible rows from rendered engine draws: preserve occurrences, group only explicit decorative duplicates, retain wrapped/composed logical units, and put partially clipped/uncertain/numeric-only units in diagnostics. Never complete a hidden span from source input. Anton edits/adds/removes units and confirms exact candidate, PNG and dump hashes; record active/elapsed review time per screen.
- **Why:** Engine source scales reference preparation without inheriting OCR/model omissions, but visibility and unit choices still require human QA ownership. Separating source input from rendered/visible text prevents invisible content from inflating the reference. Anton approved these rules before device results.
- **Alternatives considered:** Deduplicate strings (loses occurrences); infer composed text from nearby boxes (invents units); use full input for clipped rows (introduces hidden text); automatically accept engine output (removes human confirmation).
- **Consequences:** Local review pages and `l10n-reference` generate candidates and validate explicit human export separately. Confirmed projection preserves order/repeats and primary versus clipped diagnostics. D-033 remains Proposed; the approved #10 reference and D-037 replay are unchanged. No detector, baseline, matching, metric, golden, label or split changes. See [engine-text-reference.md](engine-text-reference.md). Assign the next free number only when rebasing before merge.

## D-0XX — Same-build non-interference and recorded cross-build pixel differences

- **Date:** 2026-10-23
- **Status:** Proposed
- **Decision:** For #47, require (1) zero changed pixels between v1 and v2 on the same build, (2) zero changed pixels between repeated captures, and (3) recording any cross-build difference with its changed-pixel count, exclusive bounding box and maximum channel delta, plus a visual check for changes to text or layout. A cross-build difference does not block acceptance by itself. This replaces the approved plan's zero-pixel comparison against 1271045. Anton approved this criterion on 2026-10-23; this decision entry remains Proposed pending coordinated merge.
- **Why:** 1271048 intentionally changes shared rendering paths (post-READY freeze from #44 fix 4, loading-draw suppression and the font subclass), and font-atlas allocation is incremental. A cross-build zero-pixel gate cannot separate dump interference from these intended changes. Existing checks that isolate the dump passed: v1 and v2 on 1271048 matched in attempt 3, and 20/20 forward/reverse repeats matched in pixels and dump bytes in attempt 2. These are bounded observations, not proof of every rendering path.
- **Alternatives considered:** Retain zero pixels against 1271045 (the intended lifecycle changes remain, and three device rounds plus a diagnostic APK did not identify a cause); adopt a numeric tolerance (an arbitrary threshold).
- **Consequences:** Record Tech Picker under this D-0XX: EN 40 pixels, `[751,469,768,484]`, maximum channel delta 1; DE 72 pixels, `[214,239,237,258]`, maximum channel delta 2. Alpha is unchanged; the retained visual check found no change to text or layout. Criteria (1) and (2) are met by existing evidence. The original comparison's exit 2/status `failed` is retained as history, not converted into an identical result. Root-cause investigation stays closed. Post-READY freeze versus continuous redraw in 1271045 is an unisolated hypothesis recorded only for history, not a demonstrated cause. D-038 and D-039 remain Accepted and unchanged. See [the pixel summary](evidence/47/pixel-summary.md) and [the delivery report](evidence/47/report.md). Assign the next free number when rebasing before merge alongside the other two #47 D-0XX entries.
