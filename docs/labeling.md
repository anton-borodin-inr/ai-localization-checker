# Labeling rules

Labels are written by Anton by looking at the whole screenshot and comparing what is visible with the translation source. They are never derived from detector output (D-012). Each rule below was decided by Anton; the decisions are recorded in D-023, [D-025](decisions.md#d-025--labeling-rules-scroll-clipping-and-region), [D-027](decisions.md#d-027--labeling-technical-text-in-v1), [D-044](decisions.md#d-044--v1-defect-classes-after-translation-only-probes) and D-046.

## File format

One `<screenshot-stem>.labels.json` next to each screenshot:

- `schema_version`: `2` (integer)
- `screenshot`: the exact PNG file name
- `language`: `en` or `de`
- `labels`: an array; each label has `defect_type` (`overflow`, `wrong_language`, `truncated_text` or `other`), `text_expected`, `text_seen`, `region` and an optional `note`

Files with `schema_version` `1` use the old classes (`truncated_text`, `overlap`, `untranslated`, `other`). They still load and are scored for detection only; they are not mapped to the new classes (D-046).

An empty `labels` array means that Anton reviewed the whole screenshot and found no defect. It is never a placeholder.

## Classes (D-044)

- **`overflow`:** text renders outside the bounds assigned to its own label or field, whether or not it collides with another element. Wrapping, or a growing container with fitting text, is not evidence of overflow.
- **`wrong_language`:** visible user-facing text is in a language other than the screen's intended language, including source-language fallback and foreign text in an active translation file. Legitimate proper names, shared words, symbols and numbers need context and are not labeled merely for differing from a dictionary entry.
- **`truncated_text`:** part of a user-facing string is unavailable on the screenshot because its label clips or shortens it, with the ellipsis and scroll-clipping rules below.
- **`other`:** another visible localization defect, always with a `note`; see the rules below.

## What counts as a defect

- **Ellipsis:** a label ending in an ellipsis is `truncated_text` when the full text is not visible anywhere else on the same screenshot (D-023).
- **Scroll clipping is not a defect:** text or elements cut off at the edge of a scrollable area (for example the technology description panel, or technologies at the edge of the scrollable technology tree) are not labeled when the full content becomes visible by scrolling. This was checked on the device for the issue 8 technology picker.

- **Missing translation (D-046):** in Unciv the keys are English source strings, so a missing translation shows English text; this is `wrong_language` (source-language fallback), without a special note.
- **Technical text (D-027, D-046):** a raw string key or identifier that is not text in any language (for example `TECH_MINING_NAME`) is `other` with `note` "raw key"; a broken placeholder (for example `[amount]` shown literally, or a wrong substitution) is `other` with a note describing it.
- **Separate-widget collision (D-046):** separate widgets that collide while each text stays inside its own bounds are `other` with `note` "widget collision", never `overflow`.
- **Text too small to read** is not a v1 class and is not labeled as `overflow`.

## Region

`region` is the cell of the 3×3 screen grid (`top-left` … `bottom-right`, D-018) that contains the **centre of the text's bounding box**. A text that spans two cells gets the cell of its centre, not the cell where it starts.

## Reviewed screenshots

| Screenshot | Labels | Reviewed by |
|---|---|---|
| `tech-picker__de__2400x1080__clean__1271001.png` | none | Anton |
| `tech-picker__de__2400x1080__injected__1271002.png` | 1 × `truncated_text` (Mining) | Anton |
| `tech-picker__en__2400x1080__clean__1271001.png` | none | Anton |
