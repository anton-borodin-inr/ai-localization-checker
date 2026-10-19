# Labeling rules

Labels are written by Anton by looking at the whole screenshot and comparing what is visible with the translation source. They are never derived from detector output (D-012). Each rule below was decided by Anton; the decisions are recorded in D-023, [D-025](decisions.md#d-025--labeling-rules-scroll-clipping-and-region) and [D-027](decisions.md#d-027--labeling-technical-text-in-v1).

## File format

One `<screenshot-stem>.labels.json` next to each screenshot:

- `schema_version`: `1`
- `screenshot`: the exact PNG file name
- `language`: `en` or `de`
- `labels`: an array; each label has `defect_type` (`truncated_text` or `untranslated`), `text_expected`, `text_seen`, `region` and an optional `note`

An empty `labels` array means that Anton reviewed the whole screenshot and found no defect. It is never a placeholder.

## What counts as a defect

- **Ellipsis:** a label ending in an ellipsis is `truncated_text` when the full text is not visible anywhere else on the same screenshot (D-023).
- **Scroll clipping is not a defect:** text or elements cut off at the edge of a scrollable area (for example the technology description panel, or technologies at the edge of the scrollable technology tree) are not labeled when the full content becomes visible by scrolling. This was checked on the device for the issue 8 technology picker.

- **Technical text (D-027):** a raw string key or identifier shown instead of translated text is `untranslated` with `note` "raw key"; a broken placeholder (for example `[amount]` shown literally, or a wrong substitution) is `other` with a note describing it.

## Region

`region` is the cell of the 3×3 screen grid (`top-left` … `bottom-right`, D-018) that contains the **centre of the text's bounding box**. A text that spans two cells gets the cell of its centre, not the cell where it starts.

## Reviewed screenshots

| Screenshot | Labels | Reviewed by |
|---|---|---|
| `tech-picker__de__2400x1080__clean__1271001.png` | none | Anton |
| `tech-picker__de__2400x1080__injected__1271002.png` | 1 × `truncated_text` (Mining) | Anton |
| `tech-picker__en__2400x1080__clean__1271001.png` | none | Anton |
