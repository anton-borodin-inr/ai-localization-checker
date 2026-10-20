# End-to-end vertical slice

Issue #14 joins the existing OCR baseline, DeepSeek vision check and D-026
evaluator. It does not change their rules, prompt, response schema or thresholds.
The inputs are captured PNGs; this command neither captures nor installs an app.

## Run both detectors

From a checkout with the DeepSeek key already configured in its ignored `.env`:

```sh
uv run --env-file .env --no-editable l10n-slice run \
  --images docs/evidence/8/final \
  --labels docs/evidence/8/final \
  --reference docs/experiments/issue-10/reference-amendment-candidate.json \
  --approval docs/experiments/issue-10/reference-amendment-approval.json \
  --manifest docs/evidence/8/pair-manifest.json \
  --inventory docs/evidence/12/tech-picker.json \
  --unciv-fork /path/to/Unciv \
  --workspace data/runs/issue-14 \
  --max-requests 1
```

The folder is an argument. Every PNG in it must have an unambiguous matching
human label, manifest capture and confirmed reference entry. Preflight verifies
PNG/label/reference hashes, build commits and translation hashes before any
provider is initialized. Use the Unciv fork containing both commits from #8;
Tesseract with `eng` and `deu` is needed for a fresh baseline run. No downloads
or dependency additions are performed by this command.

`--no-editable` avoids the host's D-019 editable-install problem. The command
prints the session directory. Exit 0 means the sequence completed with every
detector result checked; 2 means a completed table includes not_checked results;
1 means a preflight, accounting or recording failure. Neither exit 0 nor
readability `readable` is a claim of detector quality.

One new session contains:

- `inputs/`: byte-identical reference, approval, manifest, inventory and labels;
- `baseline/<run-id>/` and `vision/<run-id>/`: original detector records;
- `bundle.json`: relative paths and SHA-256 hashes of every recorded file,
  expected screenshots, matching settings and per-image associations;
- `budget.json`: task ledger snapshot, including prior attempts in the same workspace;
- `comparison.json` and `comparison.md`: per-image and aggregate results.

These records can be moved together. Original image paths in run metadata are
provenance, not replay dependencies. The PNGs remain in #8 evidence and are
bound by SHA-256; replay does not need images, Unciv, Tesseract or a key.

## Request and spend accounting

Use the **same workspace for every live invocation of this task**, including
failed attempts; changing it starts a separate ledger and is not an allowance
for additional requests. DeepSeek only; at most 10 requests and USD 0.10 across
the task. Each actual vision run has `RequestBudget(1)`; the CLI rejects any
other requested cap. There is no automatic rerun of a screenshot.

Before each possible send the persistent ledger reserves one request and
USD 0.01. This operational reserve exceeds the frozen peak-tariff estimate of
USD 0.0073728 for **an assumed** 8192 input tokens and the provider's enforced
4096 output-token cap. Input/image token count is not enforced or known locally
before sending: the reservation is not a provider billing guarantee. The three
fixed slice images and prompt are checked before sending. Returned usage
replaces the reservation with the peak estimate. This is a tariff estimate,
not a billing receipt; off-peak estimates remain in the original records.

A failed request counts. If usage is unavailable, its cost stays unknown and
the reservation remains charged; no further requests are sent. A cost above
the reservation also stops further sends. Screens remaining after a budget
stop receive recorded zero-request not_checked results, not clean results.
The table lists each budget stop. An interrupted reserved attempt blocks a
new invocation pending accounting review; never delete the ledger to retry.
An exclusive workspace lock prevents concurrent slice invocations. A crash
may leave that lock in place and requires inspection before recovery.

## Offline replay

```sh
uv run --no-editable l10n-slice replay \
  --bundle docs/evidence/14/records/bundle.json \
  --output data/issue-14-replay/comparison
```

Replay validates every referenced record's hash, image identity, human label
provenance, reference approval and run/result consistency. It also revalidates
the saved DeepSeek response using the existing parser and response schema,
checking findings and readability against the recorded result. It calls
`match_screen`, `score_screen` and `score_screens` with the frozen default
matching configuration. No new API or OCR calls are made, and no environment
key is read. Invalid or inconsistent bundles fail explicitly.

`partial`/`unreadable` observations remain in the original raw response only.
Only checked findings enter matching. FN on checked screens and
`fn_on_not_checked` are separate; recall_all includes both. Undefined ratios
are JSON null / Markdown `null`, never zero or one. Counts are summed before
aggregate ratios. The JSON includes finding details, FP/hallucination indices,
duplicates, matches, confusion tables, per-run token usage, cost and time.
Baseline time covers its complete run; vision time sums provider attempts.
Baseline API cost is zero; local compute cost has not been measured.

## Reference boundary

The human-confirmed amended #10 reference (16/20/20 primary transcription
units) is the sole source of `screen_texts`. Its candidate status text is
historical; the separate confirmation file binds Anton's approval to its exact
hash. Every supplied `rows[*].text_seen` is passed unchanged, including rows
excluded from the transcription denominator as clipped diagnostics. Every
supplied numeric diagnostic is also retained once. Input order and repeated
entries are preserved; there is no deduplication, OCR supplementation,
reconstruction of occurrences or use of `assembled_full_text`.

This is not an exhaustive occurrence inventory. Numeric diagnostics have no
occurrence counts or regions; split phrases omit some punctuation and
cross-unit combinations. Hallucination counts for **both** detectors are
conditional on this reference. The issue report lists concrete gaps from
inspection of the three images. These observations never become screen_texts
or labels without Anton's decision. Empty labels are only those already
provided by Anton for the two clean controls.

The slice can demonstrate an executable chain and particular recorded results
on three variants of one source screen. It cannot establish detector quality,
superiority, general readability, stability, the untranslated class, or QA time
savings. Any interpretation or Stage 2 recommendation is a draft for Anton.
