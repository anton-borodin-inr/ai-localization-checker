# Vertical slice comparison

Variants of one source screen, not quality estimates.

Hallucination source: `docs/experiments/issue-10/reference-amendment-candidate.json`.

Reference #10 is a transcription inventory, not an exhaustive occurrence map. All rows/text_seen and supplied numeric diagnostics are used unchanged; clipped diagnostics are included, hidden assembled_full_text is excluded. Numbers lack occurrence counts/regions; split spans and punctuation may affect hallucination counts. See the human-review gap audit in the issue 14 report.

Baseline complete run elapsed; vision sum of provider attempt latency.

| image | detector | status | readability | findings | tp | fp | fn | fn_on_not_checked | precision | recall_checked | recall_all | hallucinations | not_checked_screens | estimated_peak_usd | latency_s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| tech-picker__de__2400x1080__clean__1271001.png | baseline | checked | null | 15 | 0 | 15 | 0 | 0 | 0.0 | null | null | 2 | 0 | 0 | 0.825 |
| tech-picker__de__2400x1080__clean__1271001.png | vision | checked | readable | 0 | 0 | 0 | 0 | 0 | null | null | null | 0 | 0 | 0.000097584 | 1.766 |
| tech-picker__de__2400x1080__injected__1271002.png | baseline | checked | null | 12 | 1 | 11 | 0 | 0 | 0.08333333333333333 | 1.0 | 1.0 | 2 | 0 | 0 | 0.828 |
| tech-picker__de__2400x1080__injected__1271002.png | vision | checked | readable | 1 | 1 | 0 | 0 | 0 | 1.0 | 1.0 | 1.0 | 0 | 0 | 0.000131184 | 1.768 |
| tech-picker__en__2400x1080__clean__1271001.png | baseline | checked | null | 14 | 0 | 14 | 0 | 0 | 0.0 | null | null | 2 | 0 | 0 | 0.545 |
| tech-picker__en__2400x1080__clean__1271001.png | vision | checked | readable | 0 | 0 | 0 | 0 | 0 | null | null | null | 0 | 0 | 0.000093984 | 1.358 |
| TOTAL | baseline | null | null | 41 | 1 | 40 | 0 | 0 | 0.024390243902439025 | 1.0 | 1.0 | 6 | 0 | 0 | 2.198 |
| TOTAL | vision | null | null | 1 | 1 | 0 | 0 | 0 | 1.0 | 1.0 | 1.0 | 0 | 0 | 0.000322752 | 4.892 |

FN excludes labels on not_checked screens; fn_on_not_checked lists them separately.
Undefined ratios are null. Baseline API cost is zero; local compute cost is not measured.
Readability is the model's report, not independently verified reading coverage.
Missing requested screenshots: [].
Budget stops: [].
