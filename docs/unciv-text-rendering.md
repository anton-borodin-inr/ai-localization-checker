# Unciv text rendering and pre-launch language selection

Research for issue #7, 2026-10-19. Scope: installed F-Droid APK 4.22.10 / 1271; read-only source inspection and one English-to-Russian settings-file check.

Follow-up observations from issue 8 are recorded in the final section below.
They extend the original issue 7 findings without turning its source-based
predictions into historical observations.

## Evidence and scope

- **observed — [O1]/[O2]:** The settings-file language check succeeded. English and Russian main menus were captured; the original settings bytes, owner and mode were restored, and adbd was returned to `shell`. See the command transcript below.
- **observed — [O1]/[O2]:** The inspected menu labels fit; the Russian left-column buttons are visibly wider. These screenshots do **not** demonstrate a long string breaking the layout.
- **assumption — planned verification:** The observed long-string failure and its clean control are to be established in [#8](https://github.com/anton-borodin-inr/ai-localization-checker/issues/8), following Anton's scope decision in the PR #19 review. Candidate screens here remain source-based proposals; observing a broken layout is not an acceptance criterion of #7.

Evidence labels apply to each bullet or table cell's claim:

- **source:** Read in the pinned code linked beside the claim. Version provenance also cites repository build metadata explicitly as **source (build metadata)**.
- **observed:** Seen in the named screenshot; filesystem/package facts additionally cite the adb transcript, because a screenshot cannot prove a hash or a restore. `[O1]` and `[O2]` below always refer to the full filenames in this table.
- **assumption:** Unverified inference, proposed experiment or recommendation; not a finding or a ground-truth label.

| ID | Screenshot filename | Evidence |
|---|---|---|
| [O1](evidence/7/main-menu__en__2400x1080__language-check-before__1271.png) | `main-menu__en__2400x1080__language-check-before__1271.png` | **observed:** English menu, including “Quickstart”, “Start new game”, “Options” and “Version 4.22.10”. |
| [O2](evidence/7/main-menu__ru__2400x1080__language-check-after__1271.png) | `main-menu__ru__2400x1080__language-check-after__1271.png` | **observed:** Russian menu, including “Быстрый старт”, “Начать новую игру”, “Настройки” and “Версия 4.22.10”. |
| [O0](evidence/7/main-menu__en__2400x1080__original__1271.png) | `main-menu__en__2400x1080__original__1271.png` (existing `data/issue-2/review-final/`) | **observed:** Existing Stage 0 English menu; inspected labels fit and no left black strip is visible. |

- **observed — [O1]/[O2]:** Both new PNGs are 2400 × 1080 (PNG header checked). They contain a left black strip. No cutout, density, resolution or orientation setting was changed during this task. They are language-check evidence, not D-014-compliant defect-evaluation captures. Cutout handling for evaluation captures is an acceptance criterion of [#9](https://github.com/anton-borodin-inr/ai-localization-checker/issues/9); [O1]/[O2] are retained without re-capture.
- **source:** The Android launcher applies display-cutout insets when `androidCutout` is false: [AndroidLauncher](https://github.com/yairm210/Unciv/blob/899367522cea36d6063c84b02b41eedfa9a0d0e9/android/src/com/unciv/app/AndroidLauncher.kt#L81-L96).
- **assumption:** The strip is consistent with that cutout path, but the overlay state was not independently queried in this check. No general rendering conclusion depends on the strip's cause.
- **observed — evidence delivery:** [O0], [O1], [O2] and [language-check.txt](evidence/7/language-check.txt) are committed in `docs/evidence/7/`. [O0] is copied from the existing `data/issue-2/review-final/` capture. Settings backups and the dumpsys file are not committed.

## Version and APK provenance gate

- **observed — [O1]/[O2] plus package command:** `adb shell dumpsys package com.unciv.app` reported `versionCode=1271 minSdk=21 targetSdk=36`, `versionName=4.22.10`, and `installerPackageName=null`. The visible version agrees. The installer field alone cannot identify the download repository.
- **source:** The history commit [3b3559c2df5dc6fa7151dfef265548078f326680](https://github.com/yairm210/Unciv/commit/3b3559c2df5dc6fa7151dfef265548078f326680) changes `appCodeNumber` **1270 → 1271** and `appVersion` **4.22.9 → 4.22.10** in `buildSrc/src/main/kotlin/BuildConfig.kt`.
- **source:** The tag **4.22.10** resolves to **899367522cea36d6063c84b02b41eedfa9a0d0e9**. Its [BuildConfig](https://github.com/yairm210/Unciv/blob/899367522cea36d6063c84b02b41eedfa9a0d0e9/buildSrc/src/main/kotlin/BuildConfig.kt#L4-L8) contains that version pair; [Android build configuration](https://github.com/yairm210/Unciv/blob/899367522cea36d6063c84b02b41eedfa9a0d0e9/android/build.gradle.kts#L29-L35) assigns those constants to `versionCode` and `versionName`. This is the source revision inspected throughout this document, not the version-bump commit or a moving branch.
- **source (build metadata):** [F-Droid main-repository metadata](https://gitlab.com/fdroid/fdroiddata/-/blob/master/metadata/com.unciv.app.yml), retrieved 2026-10-19, lists `versionName: 4.22.10`, `versionCode: 1271`, `commit: 899367522cea36d6063c84b02b41eedfa9a0d0e9`, `subdir: android`. Its build removes the desktop directory and desktop Gradle configuration. No UI-source patch is listed in that build entry.
- **source (build metadata):** [F-Droid main index](https://f-droid.org/repo/index-v2.json), retrieved 2026-10-19, associates that version with `/com.unciv.app_1271.apk`, size **27,531,553 bytes**, SHA-256 **`caddedb60a6dcaf0199950251e027cefe363b7d2388cbc4c5d4587edaa1de9f2`**. The project installation record in [environment.md](environment.md#unciv-apk) names `https://f-droid.org/repo/com.unciv.app_1271.apk`.
- **observed — [O1]/[O2] plus APK command:** `sha256sum` of the installed `base.apk` returned that exact hash. Together with the installation record and independent F-Droid index/build metadata, this establishes **F-Droid main repo**, not IzzyOnDroid, as the documented source of this installed APK. The package inspection and upstream version history are the two independent version checks; build metadata supplies the build-to-commit link. Rendering source was read only after they agreed.
- **source:** The pinned Unciv [dependency catalog](https://github.com/yairm210/Unciv/blob/899367522cea36d6063c84b02b41eedfa9a0d0e9/gradle/libs.versions.toml#L1-L10) selects **libGDX 1.14.2**. Where behavior is implemented by the library, links below use its tag's commit **6b164672625ff2f009d3628e592e032b9269f112**. No library was installed or upgraded for this research.

## How labels and buttons handle long text

- **source:** Unciv's [toLabel and toTextButton helpers](https://github.com/yairm210/Unciv/blob/899367522cea36d6063c84b02b41eedfa9a0d0e9/core/src/com/unciv/ui/components/extensions/Scene2dExtensions.kt#L291-L295) translate text and construct libGDX widgets; [toLabel overloads](https://github.com/yairm210/Unciv/blob/899367522cea36d6063c84b02b41eedfa9a0d0e9/core/src/com/unciv/ui/components/extensions/Scene2dExtensions.kt#L344-L368) set font/alignment but do not enable wrapping or ellipsis globally. libGDX [TextButton construction](https://github.com/libgdx/libgdx/blob/6b164672625ff2f009d3628e592e032b9269f112/gdx/src/com/badlogic/gdx/scenes/scene2d/ui/TextButton.java#L43-L54) creates a normal centered Label and sizes the button from preferred dimensions.
- **source:** These strategies are selected per widget. [Label wrapping contract](https://github.com/libgdx/libgdx/blob/6b164672625ff2f009d3628e592e032b9269f112/gdx/src/com/badlogic/gdx/scenes/scene2d/ui/Label.java#L269-L278) defaults to no automatic wrapping, accepts explicit newlines and disables wrapping when ellipsis is enabled. The numeric widths below are Scene2D layout units, not measured screenshot pixels.

| Behavior | Concrete Unciv use and source mechanism | Observation boundary |
|---|---|---|
| Wrapping and height growth | **source:** City construction descriptions set `wrap = true` and use a width of one quarter of the stage in landscape: [ConstructionInfoTable](https://github.com/yairm210/Unciv/blob/899367522cea36d6063c84b02b41eedfa9a0d0e9/core/src/com/unciv/ui/screens/cityscreen/ConstructionInfoTable.kt#L82-L94). Display options' explanatory text uses `WrappableLabel` with wrapping: [DisplayTab](https://github.com/yairm210/Unciv/blob/899367522cea36d6063c84b02b41eedfa9a0d0e9/core/src/com/unciv/ui/popups/options/DisplayTab.kt#L86-L112). [WrappableLabel](https://github.com/yairm210/Unciv/blob/899367522cea36d6063c84b02b41eedfa9a0d0e9/core/src/com/unciv/ui/components/widgets/WrappableLabel.kt#L41-L49) constrains preferred width; [Label layout](https://github.com/libgdx/libgdx/blob/6b164672625ff2f009d3628e592e032b9269f112/gdx/src/com/badlogic/gdx/scenes/scene2d/ui/Label.java#L154-L181) recalculates preferred height and invalidates parent layout. | **assumption:** These branches should reflow sufficiently long text rather than necessarily lose it; no such screen was opened in this task. Whether it still fits vertically is unverified. |
| Ellipsis | **source:** [TechButton](https://github.com/yairm210/Unciv/blob/899367522cea36d6063c84b02b41eedfa9a0d0e9/core/src/com/unciv/ui/screens/pickerscreens/TechButton.kt#L28-L33) disables wrap and enables ellipsis; its title cell is [140 units wide](https://github.com/yairm210/Unciv/blob/899367522cea36d6063c84b02b41eedfa9a0d0e9/core/src/com/unciv/ui/screens/pickerscreens/TechButton.kt#L73-L79). [PromotionButton](https://github.com/yairm210/Unciv/blob/899367522cea36d6063c84b02b41eedfa9a0d0e9/core/src/com/unciv/ui/screens/pickerscreens/PromotionButton.kt#L22-L35) combines ellipsis with a maximum label width. [CityScreenCityPickerTable](https://github.com/yairm210/Unciv/blob/899367522cea36d6063c84b02b41eedfa9a0d0e9/core/src/com/unciv/ui/screens/cityscreen/CityScreenCityPickerTable.kt#L57-L83) enables ellipsis and constrains the containing city-name table. [Label.setEllipsis](https://github.com/libgdx/libgdx/blob/6b164672625ff2f009d3628e592e032b9269f112/gdx/src/com/badlogic/gdx/scenes/scene2d/ui/Label.java#L343-L355) selects `...`; [GlyphLayout](https://github.com/libgdx/libgdx/blob/6b164672625ff2f009d3628e592e032b9269f112/gdx/src/com/badlogic/gdx/graphics/g2d/GlyphLayout.java#L224-L241) actually truncates when glyphs exceed the target width. | **assumption:** Sufficiently long titles can be shortened by this path. No ellipsis was observed in [O0]/[O1]/[O2]. Whether intended shortening counts as a defect requires Anton's acceptance rule. |
| Container grows with text | **source:** Main-menu buttons use an ordinary label with `minWidth(200f)` and `pack()`: [getMenuButton](https://github.com/yairm210/Unciv/blob/899367522cea36d6063c84b02b41eedfa9a0d0e9/core/src/com/unciv/ui/screens/mainmenuscreen/MainMenuScreen.kt#L96-L119). Columns fill horizontally, then the combined table is packed and put in an `AutoScrollPane`: [menu layout](https://github.com/yairm210/Unciv/blob/899367522cea36d6063c84b02b41eedfa9a0d0e9/core/src/com/unciv/ui/screens/mainmenuscreen/MainMenuScreen.kt#L151-L203). libGDX [Table preferred sizing](https://github.com/libgdx/libgdx/blob/6b164672625ff2f009d3628e592e032b9269f112/gdx/src/com/badlogic/gdx/scenes/scene2d/ui/Table.java#L827-L848) uses child dimensions; [pack](https://github.com/libgdx/libgdx/blob/6b164672625ff2f009d3628e592e032b9269f112/gdx/src/com/badlogic/gdx/scenes/scene2d/ui/WidgetGroup.java#L141-L147) sizes to preferred dimensions. | **observed — [O1]/[O2]:** Russian left-column buttons are wider and their labels remain inside them. This is a successful adaptation in these captures, not a defect. |
| Overflow outside a widget's bounds | **source:** A plain Label's [draw method](https://github.com/libgdx/libgdx/blob/6b164672625ff2f009d3628e592e032b9269f112/gdx/src/com/badlogic/gdx/scenes/scene2d/ui/Label.java#L230-L241) draws its glyph cache without clipping to its own rectangle. [GlyphLayout](https://github.com/libgdx/libgdx/blob/6b164672625ff2f009d3628e592e032b9269f112/gdx/src/com/badlogic/gdx/graphics/g2d/GlyphLayout.java#L218-L241) skips width-based wrap/truncate handling when neither is enabled. [Table clipping](https://github.com/libgdx/libgdx/blob/6b164672625ff2f009d3628e592e032b9269f112/gdx/src/com/badlogic/gdx/scenes/scene2d/ui/Table.java#L107-L125) is conditional, not inherent to every table. A concrete constrained plain label is TechButton's [turns label and 40-unit cell](https://github.com/yairm210/Unciv/blob/899367522cea36d6063c84b02b41eedfa9a0d0e9/core/src/com/unciv/ui/screens/pickerscreens/TechButton.kt#L35-L38) ([cell sizing](https://github.com/yairm210/Unciv/blob/899367522cea36d6063c84b02b41eedfa9a0d0e9/core/src/com/unciv/ui/screens/pickerscreens/TechButton.kt#L77-L78)); city construction names are also [plain labels](https://github.com/yairm210/Unciv/blob/899367522cea36d6063c84b02b41eedfa9a0d0e9/core/src/com/unciv/ui/screens/cityscreen/ConstructionInfoTable.kt#L76-L94). | **assumption:** If text exceeds the allocated bounds and no ancestor clips it, it can paint outside them. Collision with another element, or construction-panel expansion into another region, is not established by source inspection alone. No overlap was observed. |
| Clipping at an ancestor viewport | **source:** Picker descriptions are wrapped inside an `AutoScrollPane`, with bottom-table height capped: [PickerPane](https://github.com/yairm210/Unciv/blob/899367522cea36d6063c84b02b41eedfa9a0d0e9/core/src/com/unciv/ui/screens/pickerscreens/PickerPane.kt#L35-L71). [AutoScrollPane inheritance](https://github.com/yairm210/Unciv/blob/899367522cea36d6063c84b02b41eedfa9a0d0e9/core/src/com/unciv/ui/components/widgets/AutoScrollPane.kt#L43-L48) delegates to libGDX ScrollPane, whose [draw method](https://github.com/libgdx/libgdx/blob/6b164672625ff2f009d3628e592e032b9269f112/gdx/src/com/badlogic/gdx/scenes/scene2d/ui/ScrollPane.java#L544-L549) clips children to the viewport. The main-menu scroll pane uses the same mechanism. | **assumption:** Content beyond a scroll viewport can be invisible until scrolled. This is not proof of permanently inaccessible text or a truncation defect. No clipped translated label was demonstrated here. |

## D-018 defect types: what is established

| Type | Can it occur? | v1 interpretation proposed for Anton |
|---|---|---|
| `truncated_text` | **source:** Text shortening exists through the explicit ellipsis paths above, and ancestor viewports can clip. **assumption:** An unacceptable loss of required text on a selected screen is still unverified. There is no basis to say truncation is impossible throughout Unciv. | **assumption — proposal:** Required second v1 class alongside `untranslated`, to test potential vision-model value over the OCR + translation-table baseline. The observed failure and clean control belong to #8. Anton decides whether intentional ellipsis or content hidden in a scroll viewport counts as a defect when labels are defined; this PR does not decide that boundary. |
| `overlap` | **source:** Plain labels and tables do not provide a universal clipping safeguard. **assumption:** A sufficiently constrained layout could collide; this task did not establish a specific reproducible overlap. It is neither proven present nor ruled out globally. | **assumption — proposal:** Defer from initial v1 selection until a concrete example establishes that its cause and expected behavior can be controlled. |
| `untranslated` | **source:** [Translations.getText](https://github.com/yairm210/Unciv/blob/899367522cea36d6063c84b02b41eedfa9a0d0e9/core/src/com/unciv/models/translations/Translations.kt#L66-L80) falls back to the original input when a language entry is absent. [String.tr](https://github.com/yairm210/Unciv/blob/899367522cea36d6063c84b02b41eedfa9a0d0e9/core/src/com/unciv/models/translations/TranslationExtensions.kt#L58-L77) reads the selected language; [individual-word translation](https://github.com/yairm210/Unciv/blob/899367522cea36d6063c84b02b41eedfa9a0d0e9/core/src/com/unciv/models/translations/TranslationExtensions.kt#L184-L202) calls that fallback. **assumption:** A required missing translation can therefore leave source-language text in a target-language UI, but no such defect was observed in [O1]/[O2]. | **assumption — proposal:** Required v1 class alongside `truncated_text`. Anton must distinguish missing translations from names, numbers, acronyms and intentionally shared terms. A future source-build injection is required; it was not performed here. |

- **source:** Templates with `[]`, `{}` and conditionals are assembled by [translation dispatch](https://github.com/yairm210/Unciv/blob/899367522cea36d6063c84b02b41eedfa9a0d0e9/core/src/com/unciv/models/translations/TranslationExtensions.kt#L58-L77); a translation-table value need not equal the final visible string literally.
- **assumption — scope limit:** No global “cannot occur” classification is justified for any of the three types. The supported negative is narrower: automatic wrapping is disabled for the inspected ellipsized title labels. No model inference, detector output or new ground-truth label was used.

## Candidate screens for the vertical slice

These are **assumption — proposals**, not verified broken screens or a final screen selection.

| Candidate | Why investigate it next | Observation status for #8 |
|---|---|---|
| Technology picker | **source:** [TechPickerScreen](https://github.com/yairm210/Unciv/blob/899367522cea36d6063c84b02b41eedfa9a0d0e9/core/src/com/unciv/ui/screens/pickerscreens/TechPickerScreen.kt#L145-L160) lays out a technology grid and [creates TechButtons](https://github.com/yairm210/Unciv/blob/899367522cea36d6063c84b02b41eedfa9a0d0e9/core/src/com/unciv/ui/screens/pickerscreens/TechPickerScreen.kt#L204-L220). Fixed-width ellipsized titles sit alongside icons and turn counts; the picker has a wrapped, scrollable description. **assumption:** Useful to separate intended ellipsis from unacceptable information loss. | **assumption:** Not observed on emulator. A longer title is expected to abbreviate; that is not yet a demonstrated broken layout. |
| City screen, selected construction | **source:** [ConstructionInfoTable](https://github.com/yairm210/Unciv/blob/899367522cea36d6063c84b02b41eedfa9a0d0e9/core/src/com/unciv/ui/screens/cityscreen/ConstructionInfoTable.kt#L60-L102) combines a construction title, portrait, wrapped description and buy controls; the [city picker](https://github.com/yairm210/Unciv/blob/899367522cea36d6063c84b02b41eedfa9a0d0e9/core/src/com/unciv/ui/screens/cityscreen/CityScreenCityPickerTable.kt#L57-L83) has an ellipsized name. **assumption:** Offers dense text and both growing and constrained regions. | **assumption:** Not observed. A long title/description is a candidate stress point, not an established overlap or clipping defect. |
| Options → Display | **source:** [DisplayTab](https://github.com/yairm210/Unciv/blob/899367522cea36d6063c84b02b41eedfa9a0d0e9/core/src/com/unciv/ui/popups/options/DisplayTab.kt#L69-L112) contains many translated settings labels and wrapped explanations. **assumption:** Promising for a controlled untranslated string with nearby translated text as context. | **assumption:** Not observed. Wrapping may accommodate long text successfully; no broken layout is claimed. |

- **observed — [O0]/[O1]/[O2]:** Main menu is the available language-switch control; inspected menu text fits. It supplies no observed long-string failure for these candidates.
- **assumption — planned verification:** [#8](https://github.com/anton-borodin-inr/ai-localization-checker/issues/8) establishes an observed failure and clean control on a candidate screen through a source-build experiment (D-011). Anton owns the labels and defect boundary; this research does not claim that future experiment has been performed.

## Settings file and one emulator check

- **source:** The filename is `GameSettings.json`: [UncivFiles constant](https://github.com/yairm210/Unciv/blob/899367522cea36d6063c84b02b41eedfa9a0d0e9/core/src/com/unciv/logic/files/UncivFiles.kt#L34-L34). [Settings loading/saving](https://github.com/yairm210/Unciv/blob/899367522cea36d6063c84b02b41eedfa9a0d0e9/core/src/com/unciv/logic/files/UncivFiles.kt#L315-L340) uses local storage and deserializes `GameSettings`; an unreadable file falls back to fresh settings. The [Android launcher](https://github.com/yairm210/Unciv/blob/899367522cea36d6063c84b02b41eedfa9a0d0e9/android/src/com/unciv/app/AndroidLauncher.kt#L46-L54) passes `filesDir.path` to the [launcher settings reader](https://github.com/yairm210/Unciv/blob/899367522cea36d6063c84b02b41eedfa9a0d0e9/core/src/com/unciv/logic/files/UncivFiles.kt#L416-L427).
- **observed — [O1]/[O2] plus transcript:** The accessible file on this emulator was `/data/user/0/com.unciv.app/files/GameSettings.json`. Original metadata: owner/group `10192:10192`, mode `600`, size `93` bytes. The original JSON omitted `language`.
- **source:** The top-level key is `language`, defaulting to English: [GameSettings.language](https://github.com/yairm210/Unciv/blob/899367522cea36d6063c84b02b41eedfa9a0d0e9/core/src/com/unciv/models/metadata/GameSettings.kt#L126-L129). [UncivGame initialization](https://github.com/yairm210/Unciv/blob/899367522cea36d6063c84b02b41eedfa9a0d0e9/core/src/com/unciv/UncivGame.kt#L112-L115) loads settings before creating the initial screen.
- **observed — [O1]/[O2]:** With the process stopped, adding `"language":"Russian"` to a local copy of the original JSON and replacing the device file before launch changed the menu to Russian. No language-picker taps or other UI navigation were performed.
- **observed — [O1]/[O2] plus transcript:** The original file was backed up before either launch; all other JSON fields were preserved in the temporary variant. After [O2], Unciv was force-stopped, the exact original bytes were written back, read back and compared byte-for-byte. SHA-256 before and after: `3b55ab3dd62845e1c31374bb604446d0a3b672045ba030e90810d9354fabaa6d`; owner/group/mode/size were unchanged. The app was left stopped to avoid rewriting settings after the restoration check. No claim is made that launching an app leaves its incidental caches or logs byte-identical.
- **observed — operational limitation:** An initial non-root file access failed with `Permission denied`. Temporary `adb root` was explicitly authorized by Anton after automatic approval review rejected it; each root session ended with `adb unroot`, and `whoami` confirmed `shell`. No `prepare_emulator.sh`, overlay command, dependency installation or provider call was run.

### Recorded package evidence commands and relevant output

Editorial normalization: the original absolute SDK executable path is rendered as `adb` throughout this document and the committed log. All other recorded commands and outputs are unchanged, including Android device paths and historical relative working-file paths. These commands were not re-run in the documentation follow-up.

**observed — [O1]/[O2] plus command output:** The full `dumpsys` output was saved locally; relevant fields are reproduced without unrelated package state.

```text
$ adb devices -l
List of devices attached
emulator-5554          device product:sdk_gphone64_arm64 model:sdk_gphone64_arm64 device:emu64a transport_id:7

$ adb shell dumpsys package com.unciv.app > work/evidence/dumpsys-package.txt
[exit 0; relevant fields from the saved output]
    codePath=/data/app/~~ZMSXIkWYB5CmxFuwXVfpMw==/com.unciv.app-hsMb4H00GR4KHcMUmzVuhQ==
    versionCode=1271 minSdk=21 targetSdk=36
    versionName=4.22.10
    installerPackageName=null

$ adb -s emulator-5554 shell sha256sum /data/app/~~ZMSXIkWYB5CmxFuwXVfpMw==/com.unciv.app-hsMb4H00GR4KHcMUmzVuhQ==/base.apk
caddedb60a6dcaf0199950251e027cefe363b7d2388cbc4c5d4587edaa1de9f2  /data/app/~~ZMSXIkWYB5CmxFuwXVfpMw==/com.unciv.app-hsMb4H00GR4KHcMUmzVuhQ==/base.apk
[exit 0]
```

### Recorded backup, switch and restore transcript

**observed — [O1]/[O2] plus transcript:** The commands below were invoked by a local Python wrapper, using `subprocess` and a `finally` block for restoration/unroot. Binary stdout is saved to the named PNG/JSON rather than printed. There was an eight-second host-side wait after each `am start` before capture. The wrapper checked that the precheck file still equalled the backup, and that the final readback equalled it. The backup is not included because it contains unrelated user settings.

**observed — local preparation:** Between backup and replacement, the wrapper used Python's standard `json` module to add only `language`, asserting all other parsed fields were identical. On this original file the key was absent:

```python
settings = json.loads(original)
assert "language" not in settings
changed = dict(settings, language="Russian")
assert {k: v for k, v in changed.items() if k != "language"} == settings
```

```text
$ adb -s emulator-5554 root
restarting adbd as root
[exit 0]

$ adb -s emulator-5554 wait-for-device
[exit 0]

$ adb -s emulator-5554 shell whoami
root
[exit 0]

$ adb -s emulator-5554 shell 'stat -c '"'"'%u %g %a %s'"'"' /data/user/0/com.unciv.app/files/GameSettings.json'
10192 10192 600 93
[exit 0]

$ adb -s emulator-5554 exec-out cat /data/user/0/com.unciv.app/files/GameSettings.json > work/evidence/GameSettings.original.json
[stdout saved: 93 bytes]
[exit 0]

$ adb -s emulator-5554 shell sha256sum /data/user/0/com.unciv.app/files/GameSettings.json
3b55ab3dd62845e1c31374bb604446d0a3b672045ba030e90810d9354fabaa6d  /data/user/0/com.unciv.app/files/GameSettings.json
[exit 0]

$ adb -s emulator-5554 unroot
restarting adbd as non root
[exit 0]

$ adb -s emulator-5554 wait-for-device
[exit 0]

$ adb -s emulator-5554 shell whoami
shell
[exit 0]

$ adb -s emulator-5554 root
restarting adbd as root
[exit 0]

$ adb -s emulator-5554 wait-for-device
[exit 0]

$ adb -s emulator-5554 exec-out cat /data/user/0/com.unciv.app/files/GameSettings.json > work/evidence/GameSettings.precheck.json
[stdout saved: 93 bytes]
[exit 0]

$ adb -s emulator-5554 shell am force-stop com.unciv.app
[exit 0]

$ adb -s emulator-5554 shell am start -W -n com.unciv.app/.AndroidLauncher
Starting: Intent { cmp=com.unciv.app/.AndroidLauncher }
Status: ok
LaunchState: COLD
Activity: com.unciv.app/.AndroidLauncher
TotalTime: 376
WaitTime: 382
Complete
[exit 0]

$ adb -s emulator-5554 exec-out screencap -p > work/evidence/main-menu__en__2400x1080__language-check-before__1271.png
[stdout saved: 543471 bytes]
[exit 0]

$ adb -s emulator-5554 shell am force-stop com.unciv.app
[exit 0]

$ adb -s emulator-5554 shell 'cat > /data/user/0/com.unciv.app/files/GameSettings.json' < work/evidence/GameSettings.russian.json
[exit 0]

$ adb -s emulator-5554 shell sha256sum /data/user/0/com.unciv.app/files/GameSettings.json
68a7106791fb303420763fdf0281ccc1b11351ffaffa2308571a60618a5aa2c1  /data/user/0/com.unciv.app/files/GameSettings.json
[exit 0]

$ adb -s emulator-5554 shell am start -W -n com.unciv.app/.AndroidLauncher
Starting: Intent { cmp=com.unciv.app/.AndroidLauncher }
Status: ok
LaunchState: COLD
Activity: com.unciv.app/.AndroidLauncher
TotalTime: 198
WaitTime: 199
Complete
[exit 0]

$ adb -s emulator-5554 exec-out screencap -p > work/evidence/main-menu__ru__2400x1080__language-check-after__1271.png
[stdout saved: 523628 bytes]
[exit 0]

$ adb -s emulator-5554 shell am force-stop com.unciv.app
[exit 0]

$ adb -s emulator-5554 shell 'cat > /data/user/0/com.unciv.app/files/GameSettings.json' < work/evidence/GameSettings.original.json
[exit 0]

$ adb -s emulator-5554 exec-out cat /data/user/0/com.unciv.app/files/GameSettings.json > work/evidence/GameSettings.restored.json
[stdout saved: 93 bytes]
[exit 0]

$ adb -s emulator-5554 shell sha256sum /data/user/0/com.unciv.app/files/GameSettings.json
3b55ab3dd62845e1c31374bb604446d0a3b672045ba030e90810d9354fabaa6d  /data/user/0/com.unciv.app/files/GameSettings.json
[exit 0]

$ adb -s emulator-5554 shell 'stat -c '"'"'%u %g %a %s'"'"' /data/user/0/com.unciv.app/files/GameSettings.json'
10192 10192 600 93
[exit 0]

$ adb -s emulator-5554 unroot
restarting adbd as non root
[exit 0]

$ adb -s emulator-5554 wait-for-device
[exit 0]

$ adb -s emulator-5554 shell whoami
shell
[exit 0]
```

**observed — artifact integrity:** SHA-256 of the committed evidence files (PNG bytes unchanged; log normalized only as described above):

| File | SHA-256 |
|---|---|
| [language-check.txt](evidence/7/language-check.txt) | `1e162b513c82c1644ce0389d4f09ebc85591c9b4c34278ff38a5fd8d1c5b0b94` |
| [main-menu__en__2400x1080__language-check-before__1271.png](evidence/7/main-menu__en__2400x1080__language-check-before__1271.png) | `1c0ece0c73c672e3bb10e1c8948e7cee805306d27491b2a6f469a088c38999e0` |
| [main-menu__en__2400x1080__original__1271.png](evidence/7/main-menu__en__2400x1080__original__1271.png) | `3a1bcf8fc85003ee59bd8b5836ee10a557e3c37c1d3ed1b58cdcb0fd2248e3b8` |
| [main-menu__ru__2400x1080__language-check-after__1271.png](evidence/7/main-menu__ru__2400x1080__language-check-after__1271.png) | `52a598e470792e7a4545679d29830b7281cf3c0c216f6d5aa68703e9a7cc0fea` |

## Recommendation

**assumption — proposed, not accepted:** Require both `untranslated` and `truncated_text` for v1; defer `overlap`. Truncation is the class where a vision model can add value over the OCR + translation-table baseline; an untranslated-only slice risks being unable to demonstrate an advantage over that baseline. This is the rationale for the evaluation scope, not a measured claim of model superiority. Anton decides whether intentional ellipsis or content hidden in a scroll viewport counts as a defect when labels are defined, not in this PR. The observed failure and clean control are established in #8. Preserve D-018's schema and existing accepted decisions. See Proposed D-020 in [decisions.md](decisions.md#d-020--candidate-v1-defect-types-after-unciv-source-research).

[O0]: evidence/7/main-menu__en__2400x1080__original__1271.png

[O1]: evidence/7/main-menu__en__2400x1080__language-check-before__1271.png

[O2]: evidence/7/main-menu__ru__2400x1080__language-check-after__1271.png

## Issue 8 follow-up: observed German rendering probe

**Observed, 2026-10-19:** A separate fork probe based on the same upstream
commit `899367522cea36d6063c84b02b41eedfa9a0d0e9` (tag 4.22.10), fork commit
`190275d1e4490dceb682cf881f8c3433c1b53162`, used versionCode 1271009 and two
German translation changes. Both captures were 2400 x 1080 at 420 dpi, with
German persisted, Small UI, default font, multiplier 1, foreground/cutout
checks before and after, and PNG structure/CRC verification. The original
screenshots, exact commands and hashes are exploration in the
[issue 8 Report](evidence/8/report.md#exploration-only-probe-1271009), never
labels or evaluation inputs.

| Probe screen and injected value | Observed behavior | Limit of the observation |
|---|---|---|
| Technology picker, `Mining = Bergbau und Erzgewinnung` | The TechButton title ends in `...`, omitting the end of the name. The full name is not visible elsewhere in this capture; no target-title collision is visible. This follows the source's intentional-ellipsis path. | The clean source-build screenshot is still pending. Whether shortening is a defect is a human acceptance rule, not a detector conclusion. |
| City construction, `Worker = Arbeiter für Geländeausbau und Infrastruktur` | The construction-list title wraps onto two lines. The lower-right selected-construction panel shows the complete title on one line, without ellipsis, edge loss or visible collision. | Accommodation beyond the nominal title budget is consistent with the source's content-driven panel growth; its width change versus a clean build has not been measured. No `truncated_text` defect is demonstrated for Worker. |

**Observed scope limit:** Neither of these two probes showed text loss without
a marker. This does not establish that such loss is impossible elsewhere in
Unciv. A long string alone is not evidence of a defect: the Worker probe is an
example of successful adaptation.

**Accepted by Anton — D-023:** An ellipsis is `truncated_text` only when the
full text is not visible elsewhere on the same screenshot. If the full text
is visible elsewhere on that screenshot, the shortened label is not a defect.
Anton selected Mining for the final pair, with another technology selected to
keep the full Mining name out of the description panel.

**Expectation, not measured benefit:** The OCR + translation-table baseline is
expected to catch this marked-shortening case easily. v1 may show no advantage
of the model on this class. Text loss without a marker is deferred to Stage 8
(second app), as recorded in [D-023](decisions.md#d-023--ellipsis-defect-boundary-for-unciv).
