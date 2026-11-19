# Labeling rules

Labels are written by Anton by looking at the whole screenshot and comparing what is visible with the translation source. They are never derived from detector output (D-012). Each rule below was decided by Anton; the decisions are recorded in D-023, [D-025](decisions.md#d-025--labeling-rules-scroll-clipping-and-region), [D-027](decisions.md#d-027--labeling-technical-text-in-v1), [D-044](decisions.md#d-044--v1-defect-classes-after-translation-only-probes), D-046 and D-047.

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
- **Text too small to read (D-047):** text that Anton cannot read on the screenshot at 100% zoom is not labeled in v1, in any class. Small text that Anton can read is labeled normally: a defect on it (for example `truncated_text` or `wrong_language`) gets an ordinary label. A screenshot whose only issue is unreadable small text is reviewed with an empty `labels` array.

## Region

`region` is the cell of the 3×3 screen grid (`top-left` … `bottom-right`, D-018) that contains the **centre of the text's bounding box**. A text that spans two cells gets the cell of its centre, not the cell where it starts.

## Drafting and review (Stage 3, D-062)

Dev-set drafts come only from the accepted run's `mutation-manifest.json` and `acceptance.json`, never from a detector or LLM:

1. **Generate the review page:** `uv run l10n-label draft --run-dir <run-dir>` writes one self-contained `label-review.html` next to the accepted PNGs. Each qualified intended occurrence becomes a draft label (`region` from the centre of its text bounds on 2400×1080); clean controls start empty; manifest `review_flags` appear as hints.
2. **Review in the browser:** open `label-review.html` from disk. Confirm, edit or delete every draft, add any other visible defect (picking its 3×3 region cell), mark every screenshot reviewed, and export `label-review-export.json`.
3. **Write label files:** `uv run l10n-label write --export <export.json> --output-dir datasets/dev --acceptance <run-dir>/acceptance.json --copy-pngs-from <run-dir>` refuses any export with unreviewed screenshots, unconfirmed drafts, hold-out screens, or invalid schema v2 labels, and writes one `<stem>.labels.json` per screenshot validated with `matching.load_labels`.

## Reviewed screenshots

Stage 1 vertical slice (`docs/evidence/8/final/`, schema v1):

| Screenshot | Labels | Reviewed by |
|---|---|---|
| `tech-picker__de__2400x1080__clean__1271001.png` | none | Anton |
| `tech-picker__de__2400x1080__injected__1271002.png` | 1 × `truncated_text` (Mining) | Anton |
| `tech-picker__en__2400x1080__clean__1271001.png` | none | Anton |

Stage 3 dev set (`datasets/dev/`, schema v2, 34 screenshots / 33 labels from `d061-dev-retry`; Anton edited three multi-line labels to keep only the line carrying the defect, dropping the second-line counter: `[amount] erforschen`, `Research [amount]`, and `bottom-right` `Arbeiter`):

| Screenshot | Labels | Reviewed by |
|---|---|---|
| `city-production__de__2400x1080__batch-37517e5f3dc66819__1862826555.png` | none | Anton |
| `city-production__de__2400x1080__batch-99984bb52ea65c2f__1869508724.png` | `wrong_language` (Requiert au moins 2 habitants) | Anton |
| `city-production__de__2400x1080__batch-e45e29bd1f0f9039__1887578114.png` | `other` (Benötigt mindestens [count] Bevölkerung) | Anton |
| `city-production__de__2400x1080__batch-e46946a0afe9ec07__1892114822.png` | `wrong_language` (Requires at least 2 population) | Anton |
| `city-production__en__2400x1080__batch-37517e5f3dc66819__1862826555.png` | none | Anton |
| `city-production__en__2400x1080__batch-99984bb52ea65c2f__1869508724.png` | `wrong_language` (Arbeiter, `left`); `wrong_language` (Arbeiter, `bottom-right`, single-line edit) | Anton |
| `city-production__en__2400x1080__batch-e45e29bd1f0f9039__1887578114.png` | `other` (Requires at least [count] population) | Anton |
| `city-production__en__2400x1080__batch-e46946a0afe9ec07__1892114822.png` | `wrong_language` (Benötigt mindestens 2 Bevölkerung) | Anton |
| `civilopedia__de__2400x1080__batch-37517e5f3dc66819__1862826555.png` | none | Anton |
| `civilopedia__de__2400x1080__batch-99984bb52ea65c2f__1869508724.png` | `wrong_language` (New Game) | Anton |
| `civilopedia__de__2400x1080__batch-e46946a0afe9ec07__1892114822.png` | `wrong_language` (Nouvelle partie) | Anton |
| `civilopedia__en__2400x1080__batch-37517e5f3dc66819__1862826555.png` | none | Anton |
| `civilopedia__en__2400x1080__batch-e46946a0afe9ec07__1892114822.png` | `wrong_language` (Neues Spiel) | Anton |
| `empire-stats__de__2400x1080__batch-37517e5f3dc66819__1862826555.png` | none | Anton |
| `empire-stats__de__2400x1080__batch-99984bb52ea65c2f__1869508724.png` | `wrong_language` (Gains du sol) | Anton |
| `empire-stats__de__2400x1080__batch-e45e29bd1f0f9039__1887578114.png` | `wrong_language` (Tile yields) | Anton |
| `empire-stats__en__2400x1080__batch-37517e5f3dc66819__1862826555.png` | none | Anton |
| `empire-stats__en__2400x1080__batch-e45e29bd1f0f9039__1887578114.png` | `wrong_language` (Felderträge) | Anton |
| `options-gameplay__de__2400x1080__batch-37517e5f3dc66819__1862826555.png` | none | Anton |
| `options-gameplay__de__2400x1080__batch-99984bb52ea65c2f__1869508724.png` | `overflow` (Hilfe); `wrong_language` (Unités inactives) | Anton |
| `options-gameplay__de__2400x1080__batch-e45e29bd1f0f9039__1887578114.png` | `wrong_language` (Check for idle units); `overflow` (Verringern) | Anton |
| `options-gameplay__de__2400x1080__batch-e46946a0afe9ec07__1892114822.png` | `overflow` (Erhöhen) | Anton |
| `options-gameplay__en__2400x1080__batch-37517e5f3dc66819__1862826555.png` | none | Anton |
| `options-gameplay__en__2400x1080__batch-99984bb52ea65c2f__1869508724.png` | `wrong_language` (Untätige Einheiten anzeigen); `overflow` (Increase) | Anton |
| `options-gameplay__en__2400x1080__batch-e45e29bd1f0f9039__1887578114.png` | `overflow` (Help) | Anton |
| `options-gameplay__en__2400x1080__batch-e46946a0afe9ec07__1892114822.png` | `overflow` (Decrease) | Anton |
| `tech-picker__de__2400x1080__batch-37517e5f3dc66819__1862826555.png` | none | Anton |
| `tech-picker__de__2400x1080__batch-99984bb52ea65c2f__1869508724.png` | `truncated_text` (Mauerarbeiten und S...); `truncated_text` (Bergbau und Erzgew...) | Anton |
| `tech-picker__de__2400x1080__batch-e45e29bd1f0f9039__1887578114.png` | `truncated_text` (Baukunst und Gebäu...); `wrong_language` (Mining) | Anton |
| `tech-picker__de__2400x1080__batch-e46946a0afe9ec07__1892114822.png` | `wrong_language` (Minage); `other` ([amount] erforschen, single-line edit) | Anton |
| `tech-picker__en__2400x1080__batch-37517e5f3dc66819__1862826555.png` | none | Anton |
| `tech-picker__en__2400x1080__batch-99984bb52ea65c2f__1869508724.png` | `truncated_text` (Masonry and stone ...); `other` (Research [amount], single-line edit) | Anton |
| `tech-picker__en__2400x1080__batch-e45e29bd1f0f9039__1887578114.png` | `wrong_language` (Bergbau) | Anton |
| `tech-picker__en__2400x1080__batch-e46946a0afe9ec07__1892114822.png` | `truncated_text` (Construction and civ...); `truncated_text` (Mining and ore extra...) | Anton |
