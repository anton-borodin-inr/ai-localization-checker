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
- **Status:** Accepted
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

## D-017 — v1 provider settings: Gemini 3.8 Flash, structured output

- **Date:** 2026-10-17
- **Status:** Superseded by D-020
- **Decision:** The v1 provider (D-006) is the Gemini API free tier with `gemini-3.8-flash`. Requests use structured output (`application/json` with the finding schema), temperature 0, a 60 s timeout, and the SDK's own retries disabled; one simple retry after HTTP 429 is allowed only within the per-run request cap.
- **Why:** On 2026-10-17 it is the latest stable Flash model available on the free tier. Disabling SDK retries makes the request cap count real requests.
- **Alternatives considered:** `gemini-3.6-flash` (older, deprecated sooner); `gemini-3.5-flash-lite` (weaker on small text, which D-014 must check).
- **Consequences:** Every run records the requested model id and the `model_version` the API returns. Free-tier inputs may be used by Google to improve its products.

## D-018 — Draft v0 finding schema

- **Date:** 2026-10-17
- **Status:** Proposed
- **Decision:** A finding has `defect_type` (`truncated_text`, `overlap`, `untranslated`, `other`), `text_seen`, `region` on a 3×3 screen grid and `confidence` in 0..1. The schema is a draft and is finalized in Stage 1.
- **Why:** The 3×3 grid is the coarse region D-009 needs to separate identical labels without measuring coordinate precision. `other` lets the model report a defect without forcing it into a v1 class; `other` findings never match a label.
- **Alternatives considered:** Normalized bounding boxes (measure coordinate precision, which D-009 avoids); only the v1 defect types.
- **Consequences:** Matching (Stage 1) uses type + `text_seen` + grid cell.

## D-019 — Default request timeout of 180 s

- **Date:** 2026-10-17
- **Status:** Proposed
- **Decision:** The default Gemini request timeout is 180 s instead of the 60 s in D-017, and it is configurable with `--timeout`. A server-side `504 DEADLINE_EXCEEDED` is reported as `timeout`.
- **Why:** The SDK sends the timeout to the server as `X-Server-Timeout`. With 60 s, the first live call on the 2400×1080 main menu (run `20261017T182052Z-fb1925`) was cut off by the server after 59.2 s with no response.
- **Alternatives considered:** A lower thinking level (faster, but it changes model behaviour and is close to tuning); 120 s (risk of wasting another free-tier request).
- **Consequences:** Every run records `timeout_s` in its settings; the real latency is visible in `run.json`.

## D-020 — v1 model: Gemini 3.6 Flash on the free tier

- **Date:** 2026-10-17
- **Status:** Proposed
- **Decision:** The v1 model is `gemini-3.6-flash` on the Gemini API free tier. The other settings from D-017 stay: structured output, temperature 0, SDK retries disabled; the timeout follows D-019.
- **Why:** From this project, every generation request to `gemini-3.8-flash` hung until the deadline: two image requests (60 s and 180 s) and a one-line text-only probe (30 s), all ending in `504 DEADLINE_EXCEEDED`. The same text probe on `gemini-3.6-flash` answered in 1.8 s. The key and `models.list` worked, so the problem is 3.8 generation on the free tier.
- **Alternatives considered:** Enabling billing and keeping 3.8 on the paid tier; rejected for now because issue #3 allows the free tier only.
- **Consequences:** `DEFAULT_MODEL` is `gemini-3.6-flash`; `--model` still selects another model. Free-tier inputs may be used by Google to improve its products. 3.8 can be re-checked later with `scripts/gemini_probe.py text`.
