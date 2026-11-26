# Stage 5: Thinking Mode (`low` and `high`) vs Disabled on the Dev Set

**Preliminary v1 caveat:** Tested on `deepseek-flash` over `datasets/dev` (`34` PNGs: `24` mutated, `10` clean controls; `33` labels: `overflow` 6, `wrong_language` 17, `truncated_text` 6, `other` 4; D-006, D-044, D-049, D-062). Prompt `v3`, schema `v2`, wrapper `deepseek-json-object-v3`, full image (`2400×1080`), and `detail: original` were unchanged; thinking mode was the only variable. `temperature` was omitted in thinking mode (ignored by DeepSeek). `THINKING_MAX_TOKENS = 16384` (timeout `120 s`; per-request reserve `\$0.3342336`, fitting under `--max-usd 0.70`) produced **zero `finish_reason="length"` cut-offs** across all `206` requests (observed peak per-image completion: `9,006` tokens / `42.4 s` in `low`, `12,177` tokens / `60.4 s` in `high`). Hold-out (`~/l10n-holdout`) was never read or run (D-010).

## 1. Comparison: `disabled` (#82) vs `low` vs `high` (`datasets/dev`, 34 PNGs, 33 Labels)

Per-class recall is D-026 type-free detection recall (`matched / total`). Except for `1` `overflow` label in `low` R1 (`Decrease` reported as `truncated_text`), every matched finding in all 9 runs also matched the exact label `defect_type`.

| Mode / Run | `not_checked` | Precision | Recall (all / chk) | `overflow` (/6) | `wrong_lang` (/17) | `truncated` (/6) | `other` (/4) | Clean FP (10 PNGs) | Halluc. (spliced) | Stability (`3/3` / `2/3` / `1/3` / `0/3`) | Reason. tok/PNG | Peak USD/PNG | Time/PNG |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|
| **`disabled` 3-run mean** ([#82](../stage5-vision-dev/README.md)) | **0.00** (0/102) | **0.773** | 0.586 / 0.586 | 0.00 (0.000) | 12.00 (0.706) | **6.00 (1.000)** | 1.33 (0.333) | **1.00** | **2.33 (0.33)** | 18 / 1 / 2 / 12 | **0** | **\$0.000308** | **1.49 s** |
| **`low` 3-run mean** | 0.33 (1/102) | 0.633 | **0.747 / 0.755** | 0.33 (0.056)\* | **15.33 (0.902)** | **6.00 (1.000)** | 3.00 (0.750) | 5.00 | 10.00 (1.67) | **22 / 3 / 2 / 6** | 1,573 | \$0.002212 | 8.78 s |
| ↳ `low` R1 ([run.json](../../../data/runs/stage5-vision-thinking-low-run1-20261126T124900Z/run.json)) | 0 | 0.634 | 0.788 / 0.788 | 1 (0.167)\* | 16 (0.941) | 6 (1.000) | 3 (0.750) | 3 | 9 (1) | — | 1,511 | \$0.002482 | 8.47 s |
| ↳ `low` R2 ([run.json](../../../data/runs/stage5-vision-thinking-low-run2-20261126T125400Z/run.json)) | 0 | 0.676 | 0.758 / 0.758 | 0 (0.000) | 15 (0.882) | 6 (1.000) | 4 (1.000) | 5 | 9 (2) | — | 1,895 | \$0.002424 | 10.12 s |
| ↳ `low` R3 ([run.json](../../../data/runs/stage5-vision-thinking-low-run3-20261126T130000Z/run.json)) | 1 (`partial`) | 0.590 | 0.697 / 0.719 | 0 (0.000) | 15 (0.882) | 6 (1.000) | 2 (0.500) | 7 | 12 (2) | — | 1,314 | \$0.001731 | 7.75 s |
| **`high` 3-run mean** | 0.67 (2/102) | 0.646 | 0.717 / 0.732 | 0.00 (0.000) | 14.67 (0.863) | 5.67 (0.944) | **3.33 (0.833)** | 3.33 | 9.00 (1.33) | 22 / 1 / 3 / 7 | 1,704 | \$0.002364 | 9.56 s |
| ↳ `high` R1 ([run.json](../../../data/runs/stage5-vision-thinking-high-run1-20261126T130500Z/run.json)) | 0 | 0.667 | 0.727 / 0.727 | 0 (0.000) | 15 (0.882) | 6 (1.000) | 3 (0.750) | 3 | 8 (1) | — | 1,288 | \$0.002205 | 7.49 s |
| ↳ `high` R2 ([run.json](../../../data/runs/stage5-vision-thinking-high-run2-20261126T130900Z/run.json)) | 1 (`invalid`) | 0.657 | 0.697 / 0.742 | 0 (0.000) | 14 (0.824) | 5 (0.833) | 4 (1.000) | 3 | 9 (2) | — | 2,189 | \$0.002774 | 11.85 s |
| ↳ `high` R3 ([run.json](../../../data/runs/stage5-vision-thinking-high-run3-20261126T131600Z/run.json)) | 1 (`invalid`) | 0.615 | 0.727 / 0.727 | 0 (0.000) | 15 (0.882) | 6 (1.000) | 3 (0.750) | 4 | 10 (1) | — | 1,635 | \$0.002112 | 9.34 s |

\*`0/6` exact-type `overflow` in all 6 thinking runs (`low` R1 flagged `Decrease` as `truncated_text`).
`not_checked` reasons: `low` R3 returned `readability="partial"` on `city-production__de` batch `e45e29bd` (`1` label → `fn_on_not_checked=1`); `high` R2 emitted an invalid `findings.1.region` value on `tech-picker__de` batch `e45e29bd` (`2` labels → `fn_on_not_checked=2`); `high` R3 emitted an unexpected top-level `type` field on clean `options-gameplay__de` (`0` labels).

## 2. `"Hilfe"` (`options-gameplay__de`, `batch-99984bb52ea65c2f`)

**`"Hilfe"` was not found as `overflow` (or any defect) in any run** (`0/3` in `low`, `0/3` in `high`, `0/2` in the initial probe). The saved `reasoning_content` shows the model reads `"Hilfe"` on the full image but misinterprets the overflowing text as a normal decorative/watermark label:

- **`low` R3** ([per_image.json](../../../data/runs/stage5-vision-thinking-low-run3-20261126T130000Z/per_image.json)): `"- \"Hilfe\" bottom left - German, fine."` (`low` R1 and R2 did not mention `"Hilfe"`.)
- **`high` R1** ([per_image.json](../../../data/runs/stage5-vision-thinking-high-run1-20261126T130500Z/per_image.json)): `"Actually the text \"Hilfe\" in bottom-left has \"Hilfe\" as large watermark help button."` / `"What about \"Hilfe\" watermark - fine."` (`high` R2 also wrote `"Also \"Hilfe\" fine."`; `high` R3 did not mention it.)

## 3. Hallucinations and Adjacent-Label Splicing (3-Run Totals)

Under D-029 whole-word presence, total hallucinations across 3 runs jumped from `7` (`disabled`) to `30` (`low`) and `27` (`high`):

| Hallucination pattern (3-run total / per-run mean) | `disabled` (#82) | `low` | `high` | Examples |
|---|---:|---:|---:|---|
| **Spliced adjacent labels** | **1** (0.33) | **5** (1.67) | **4** (1.33) | `"Unités inactives etzen"` (`1` / `3` / `2`: foreground + dimmed background `"Fortsetzen"`), `"turnDecrease"` / `"Notifications log max turn[s]Decrea[se]"` (`0` / `1` / `2`), `"Tile yields 2"` (`0` / `1` / `0`) |
| **2-line button counter joined** | 0 (0.00) | 2 (0.67) | 2 (0.67) | `"[amount] erforschen (0/24)"` (single research button's second-line counter joined to label `"[amount] erforschen"`) |
| **Clipped viewport / scroll edge** | 6 (2.00) | 19 (6.33) | 19 (6.33) | `"Spra"` / `"Spa"` (`5` / `12` / `11`), `"Nation"` (`0` / `4` / `5` from clipped `'Natio'`), `"Decrea"` (`1` / `1` / `1`), scroll-clipped `tech-picker__en` `"Temple of Artemis..."` (`0` / `2` / `2`; `high` R1 also joins header `"Wonders enabled:"`) |
| **Misread / typo text** | 0 (0.00) | 4 (1.33) | 2 (0.67) | `"In Uncv..."`, `"Civliopedia"`, `"Baukonst"`, `"by one one"` (`low`); `"Uncv"`, `"Mirage"` for `"Minage"` (`high`) |
| **Total hallucinations** | **7** (2.33) | **30** (10.00) | **27** (9.00) | Note: `#82` counted the 2 `"Spa"` misreads + 1 `"Unités inactives etzen"` as invented/garbled (`3` + `4` clipped = `7`). |

Adjacent-label splicing directly hurt recall: in `options-gameplay__de` batch `99984bb5`, `"Unités inactives"` dropped from `2/3` TP (`disabled`) to **`0/3`** in both `low` and `high` because thinking spliced dimmed background `"etzen"` onto it (`3/3` in `low`, `2/3` in `high`, plus both probe runs).

## 4. Probe Runs and Budget

Pre-sweep probe on `options-gameplay__de` batch `99984bb5` (`2` requests total, `\$0.005288` peak):
- `low` ([run.json](../../../data/runs/stage5-vision-thinking-probe-low-20261126T124100Z/run.json)): `2,004` prompt, `1,098` reasoning, `1,183` completion, `6.59 s`, `\$0.002021` peak (`"Unités inactives setzen"`, `"Spra"`; `"Hilfe"` dismissed as `"Fine"`).
- `high` ([run.json](../../../data/runs/stage5-vision-thinking-probe-high-20261126T124400Z/run.json)): `2,004` prompt, `2,137` reasoning, `2,222` completion, `11.59 s`, `\$0.003268` peak (`"Unités inactives etzen"`, `"Spra"`; `"Hilfe"` not mentioned).

Total task API usage across all `8` runs (`2` probe + `6` dev runs): **`206 / 220` requests**, **`\$0.471998` peak** (`\$0.235999` off-peak) out of the **`\$2.50`** budget.

## 5. Conclusion

**Negative / mixed result — keep `disabled` as default (no D-034 amendment proposed):**
- Thinking mode **did not solve `overflow`** (`0/6` exact in all 6 runs; `"Hilfe"` explicitly dismissed as a `"watermark"`).
- Thinking mode substantially improved recall on `wrong_language` (`12.0 → 15.3/17` in `low`, `14.7/17` in `high`) and `other` broken placeholders (`1.3 → 3.0–3.3/4`), raising overall recall from `0.586` to `0.747` (`low`) and `3/3`-stable labels from `18` to `22`.
- However, it **degraded precision by 13–14 pp** (`0.773 → 0.633–0.646`), multiplied **clean-screen FPs by 3.3–5.0×** (`1.0 → 3.3–5.0`), **hallucinations by 3.9–4.3×** (`2.3 → 9.0–10.0`, including `4–5×` more adjacent-label splices), introduced **`not_checked` failures** (`1` `partial` in `low`, `2` schema errors in `high`), and increased cost **7.2–7.7×** and latency **5.9–6.4×**.
- `high` offered no advantage over `low` (lower recall, more schema errors, similar reasoning token count with high run-to-run variance). `--thinking {disabled,low,high}` remains available on `l10n-eval` with `disabled` unchanged as the default.
