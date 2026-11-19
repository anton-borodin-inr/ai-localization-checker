# Stage 4 Dev Screen Inventories

Source-backed baseline inventories (`baseline.Inventory` schema v1) for the five Stage 3 dev screens (D-049), pinned to Unciv fork commit `b534a8ae67c390412984869c7a03b168d532c36c` and the Stage 2/3 capture states (`fixtures/stage2/states/*.json`).

## Inventory rule

- An inventory holds translatable UI text that is at least partly readable on the clean dev screenshot (`batch-37517e5f3dc66819` / `1862826555`) in EN or DE.
- Pure numbers, numeric counters (`(0/24)`, `31 8`, `160`, tile yields, stat counts) and icons are excluded (D-030).
- The dimmed backdrop behind a modal popup (`options-gameplay` main menu buttons and `Version`) is excluded as not part of the screen under test.
- Viewport-edge text that is at least partly readable on the clean screenshot in EN or DE is retained without scroll-edge masking (D-030). Completely off-viewport continuations (such as `wonder-ranged-production` on `tech-picker`) are excluded.
- Slot boxes are normalized `[0, 1]` widget search areas covering both EN and DE layouts, derived from the Anton-confirmed clean Stage 2 references (`docs/evidence/47/reference-confirmation/<screen>__{en,de}/reference.json` and `unresolved-diagnostics.json`) with uniform padding. On `civilopedia`, the five sidebar tutorial entries share the list-panel box `[0.0, 0.25, 0.30, 0.98]` because Unciv sorts them alphabetically per language.

## Screens and visibility check (EN vs DE clean controls)

All 114 slots across the five screens were checked against both clean dev screenshots (`en` and `de`) and verified to render via `TranslationTable.render()` against `b534a8a`:

| Screen | File | Slots | Visible in one language only | Partly clipped on clean screenshot |
|---|---|---:|---|---|
| `tech-picker` | `tech-picker.json` | 24 | None | `wonder-name`, `wonder-culture`, `wonder-food`, `wonder-archery-production` (bottom edge in EN and DE; DE wraps after `Bau von`) |
| `city-production` | `city-production.json` | 18 | None | None |
| `options-gameplay` | `options-gameplay.json` | 18 | None | `tab-language` (`Spra` in DE) |
| `empire-stats` | `empire-stats.json` | 36 | None | None |
| `civilopedia` | `civilopedia.json` | 18 | `article-double-aqueducts` (partly readable in EN; pushed below viewport in DE) | `tab-nations` (`Nation` in DE); `article-double-aqueducts` (bottom edge in EN) |
| **Total** | | **114** | **1 slot** | |
