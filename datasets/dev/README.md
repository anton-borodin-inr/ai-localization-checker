# Stage 3 Dev Dataset

Labeled dev screenshots for v1 evaluation (D-049, D-062). Hold-out screens are never stored in this repository (D-010).

## Provenance

- **Source run:** `d061-dev-retry` (all 34 screenshots accepted by Anton on 2026-11-19)
- **Checker commit:** `d6556f4dc2b7356192caecbf9ad58ec2894f4122`
- **Unciv builder commit:** `5fd67dbd034f22183ace9631dedacc9cf3649850`
- **Resolution & languages:** `2400×1080` (D-014), `en` and `de` (D-021)
- **Dev screens (D-049):** `city-production`, `civilopedia`, `empire-stats`, `options-gameplay`, `tech-picker`
- **Builds (`variant` / `versionCode`):**
  - Clean control (10 PNGs): `batch-37517e5f3dc66819` / `1862826555`
  - Mutated batches (24 PNGs): `batch-99984bb52ea65c2f` / `1869508724`, `batch-e45e29bd1f0f9039` / `1887578114`, `batch-e46946a0afe9ec07` / `1892114822`

## Counts (schema_version 2, confirmed by Anton)

34 screenshots (10 clean controls with empty `labels: []`, 24 mutated) and 33 labels:

| Class | EN | DE | Total |
|---|---:|---:|---:|
| `overflow` | 3 | 3 | 6 |
| `wrong_language` | 7 | 10 | 17 |
| `truncated_text` | 3 | 3 | 6 |
| `other` (broken placeholder) | 2 | 2 | 4 |
| **Total** | **15** | **18** | **33** |

## Review note

Anton confirmed all 34 screenshots and edited three multi-line labels to keep only the line carrying the defect (excluding the separate second-line counter):

- `tech-picker__de__2400x1080__batch-e46946a0afe9ec07__1892114822.png` (`other`): `[amount] erforschen` / `Bogenschießen erforschen`
- `tech-picker__en__2400x1080__batch-99984bb52ea65c2f__1869508724.png` (`other`): `Research [amount]` / `Research Archery`
- `city-production__en__2400x1080__batch-99984bb52ea65c2f__1869508724.png` (`wrong_language`, `bottom-right`): `Arbeiter` / `Worker`
