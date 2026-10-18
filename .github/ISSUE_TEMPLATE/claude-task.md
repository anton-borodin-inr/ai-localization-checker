---
name: Agent task
about: An implementation task for a coding agent, with acceptance criteria and a report back
title: "[Stage N] "
labels: claude-task
---

<!--
How to fill this in:
- Describe WHAT must change and HOW it will be checked, not how to write the code.
- The coding agent plans the implementation against the real code before writing it; Anton approves the plan.
- Remove any section that does not apply, except Acceptance criteria and Report.
-->

## Goal

<!-- One or two sentences: what the pipeline or the user can do after this task that they cannot do now. -->

## Context

- **Plan stage:** <!-- e.g. Stage 1. Vertical slice -->
- **Related decisions:** <!-- e.g. D-009, D-010 from docs/decisions.md -->
- **Relevant files or folders:** <!-- if known; otherwise "to be found during planning" -->
- **Inputs available:** <!-- screenshots, translation files, previous outputs -->

## Acceptance criteria

<!-- Each line must be checkable by a command, a test or a visible result. -->

- [ ] 
- [ ] 
- [ ] Tests for the new behaviour pass: `pytest ...`

**How to verify:** <!-- the exact command(s) Anton will run, and what he should see -->

## Constraints

- Do not read, copy or reference the hold-out set (it is stored outside the repository).
- Do not change metric or matching code without updating the hand-computed golden tests.
- A timeout, an API error or an invalid model response must never be reported as "no defects".
- No new dependencies without a one-line reason in the report.
- API spend for this task: <!-- e.g. max N requests / $X; "none" if no paid calls -->

## Out of scope

<!-- What must NOT be done in this task, even if it looks related. -->

-

## Definition of done

- [ ] Acceptance criteria above are met and verified
- [ ] Tests and linters pass
- [ ] Any decision made during the task is added to `docs/decisions.md` with status `Proposed`
- [ ] Report below is filled in (as a comment on this issue or in the PR description)

---

## Report (filled in by the coding agent)

- **What changed:** <!-- files and behaviour, in a few lines -->
- **How it was verified:** <!-- commands run and their results -->
- **Deviations from the task:** <!-- what was done differently and why; "none" if none -->
- **Decisions proposed:** <!-- new D-XXX entries, if any -->
- **Open questions for Anton:** <!-- anything that needs a product or methodology call -->
- **API usage:** <!-- requests made and cost, if any -->
