# Issue 47 — deferred Tech Picker pixel investigation

- **Recorded:** 2026-10-22.
- **Status:** Deferred at Anton's explicit request. Preserve the evidence and investigate later; stop further root-cause experiments, diagnostic APKs and device proposals for this difference.
- **Classification:** Observed cross-build image difference. Practical impact and root cause are unconfirmed; this is not an established localization defect.

## Observed difference

Comparing the retained 1271045/#41 images with 1271048 gives these results on a 2400×1080 image (2,592,000 pixels):

| Tech Picker language | Changed pixels | Exclusive bounding box | RGB channel change |
|---|---:|---|---|
| English | 40 | `[751,469,768,484]` | ±1 |
| German | 72 | `[214,239,237,258]` | Up to 2 in magnitude |

The differences lie on letter edges; alpha is unchanged. No change of text content or layout has been established. Readability or downstream checker impact has not been demonstrated. Do not infer that all reference content/geometry is accepted: human review remains pending.

The original 40-image comparison has 36 identical images and four differing Tech Picker images (two languages across two passes). Repeated PNGs and dumps within 1271048 were stable. These are retained measured results, not thresholds to tune.

## Completed checks and limits

- **Attempt 3:** German v1/v2 and cold/warm controls on 1271048 have identical pixels, all retaining the same 72-pixel difference. It does not establish a protocol-specific cause.
- **Attempt 4:** The exact old 1271045 APK reproduces its historical pixels with zero differences in the current environment; restoring exact 1271048 restores the 72-pixel delta. Binary dependence is established for this control cycle, but no particular source change is identified.
- **Attempt 5:** All eight current/owned-loading × telemetry off/on PNGs match retained 1271048. The alternate loading gate actually ran (23 ordinary-loading phases) and did not restore historical pixels. Selected CPU glyph/atlas/cache/batch inputs match between on-arms; raw traces differ in transport/chronology fields. This does not prove GPU equality or justify a loading-gate correction.
- **Host-only work:** Synthetic mechanism probes and actual Android atlas/raster metadata are retained. They do not establish the Android root cause. Any unfinished replay is reported separately as incomplete/not run; a prepared experiment is not a reason to continue after deferral.

## Acceptance status and scope

The approved implementation plan included zero changed pixels against 1271045 as a noninterference check. That comparison remains **failed**. Deferral is not a passing result, a tolerance change or approval to replace screenshots/reference bytes. Keep the original criterion and all failure/recovery evidence visible in delivery reports.

The difference does not by itself prove an incorrect engine dump. Issue 47's core acceptance work remains rendered text, geometry/clipping, review usability and Anton's explicit hash-bound reference confirmation. Engine output remains an unconfirmed candidate, never an automatically accepted reference. No labels, baseline/OCR, matching, metrics, goldens, translations or Accepted decisions change here. D-038 remains Accepted for v1; the two new D-0XX entries remain Proposed. No issue closure, push, PR or merge is implied.

No further pixel investigation is scheduled. Resume only after a new explicit instruction from Anton; any later device experiment still requires its own exact-operation approval. Do not build another diagnostic APK or launch another probe merely to finish this side investigation.

## Retained evidence and recovery state

- [Original 40-pair result and pixel deltas](device-attempt-2/report.md).
- [Same-APK v1/v2 diagnosis](device-attempt-3/report.md).
- [Exact old/new APK control](device-attempt-4/report.md).
- [Four-mode diagnostic matrix and CPU comparisons](device-attempt-5/report.md).
- [Host diagnostic checkpoint](diagnostic-host/report.md).

Full PNGs, raw sidecars, scripts, logs and hash manifests remain in the task output archives. Private settings/save backups remain private; do not delete or overwrite prior evidence.

Last device verification after attempt 5: exact **1271048** APK SHA-256 `91d9a900f8204880e590de7fb90f0fc15e2aa5cf5d94a3ae77364497d7b0541e`, original settings SHA-256 `7fc6dff53a9ff0b1a87e75c530edcf98fc000ee3dfa6f04d6feccd7085f9bfa7` and metadata `10196 10196 600 873`, all four saves unchanged, 45 prior dumps plus two diagnostic sidecars retained, app stopped, adbd shell, emulator released. No new device command is part of this deferral.

**Provider/model calls 0; spend USD 0.**
