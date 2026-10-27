# Proposed follow-up issue (unpublished)

Title: `Unciv hook: host integration coverage for request lifecycle`

The current production pin (`b534a8a`, APK 1271048) has helper-class lifecycle
tests and bounded device integration evidence. `L10nWorkTest.kt` does not
exercise `L10nScreenHook.render()`, `start()` or `fail()` directly.

Add host integration tests around the real hook with fake graphics, scheduler,
screen construction and dump publisher. Cover queued/loading supersession,
late callbacks, failure before/after state application, exactly one terminal
event, pending-work completion, dump-before-READY, terminal rendering policy,
and the next-request/leave transition. Include assertions that distinguish
hook control flow from helper behavior and document host versus Android/GL
limits. Review terminal back-buffer handling and background ownership reads
as explicit scenarios without presupposing their solution.

Keep this separate from #47 so it does not move the device-evidence pin. A
production fix, dependency or new APK/device run requires its own plan and
Anton approval. No issue was created remotely by this preparation.
