# Issue 10 Report: Gemini and approved local Qwen comparison

**Combined actual generation requests_sent: 41/41 — Gemini 27, local Qwen 14/14.** Every failed send counts. Cloud quality comparison remains incomplete because of 503/429. Local status: 2 checked / 12 not_checked. Independent review and Anton's conclusions remain pending.

- [Local Report: side-by-side results, every local run, visual/region audit, checks and every changed file](local-model/report.md)
- [Preserved Gemini Report: complete metric tables and all 27 cloud runs](report-gemini.md)
- [Initial 15-call Report](report-initial.md)
- [Frozen cloud aggregate](combined-summary.json), [local aggregate](local-model/summary.json)

The local model is qwen/qwen3-vl-8b, MLX 8-bit. The same screenshot/crop bytes, prompt, response schema and confirmed reference (16/20/20) are used. HIGH/ULTRA_HIGH are Gemini-specific. Anton approved the local exception and initial 12-send plan, then timeout 400 s/cap 13 and finally 1800 s/cap 14 after the recorded timeouts. Gemini remains frozen at 27; no new cloud call was made. Production defaults, labels and comparison thresholds are unchanged.

D-029–D-032 are Proposed. See the linked Reports for What changed, How it was verified, Deviations, Decisions, Open questions and API usage. No self-approval or merge.
