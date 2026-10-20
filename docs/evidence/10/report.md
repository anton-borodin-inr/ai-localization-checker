# Issue 10 Report: Gemini, Qwen and approved paid DeepSeek comparison

**53 generation requests_sent: 27 Gemini + 14 local Qwen + 12 DeepSeek.** No further call in these batches. Gemini quality comparison remains incomplete after 503/429; Qwen has 2/14 validated responses. DeepSeek has 11/12 validated responses, with its injected original rejected for extra reading confidence. Independent review and Anton's final conclusions remain pending.

- [DeepSeek Report: metrics, every finding, costs, all twelve runs, verification and every changed file](deepseek/report.md)
- [Preserved Gemini Report: all 27 cloud runs](report-gemini.md)
- [Preserved Qwen Report: all 14 local runs](local-model/report.md)

DeepSeek token-derived cost is $0.004356006 at the documented off-peak tariff, $0.008712012 conservatively at peak; the balance endpoint returned $2.00 before/after, so its observed $0.00 delta does not establish free calls. Conservative reserved budget $0.2359296 is below the approved $0.25 and is not the amount spent.

Original screenshots/crops, human-confirmed reference 16/20/20, labels and metrics remain unchanged. The DeepSeek JSON-mode format wrapper is a declared provider difference. Production remains Gemini. D-029–D-033 are Proposed. No self-approval or merge.
