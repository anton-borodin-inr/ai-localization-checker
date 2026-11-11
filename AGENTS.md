# AGENTS.md

Project rules for coding agents other than Claude Code (for example OpenAI Codex). `CLAUDE.md` holds the same rules for Claude Code. **Everything below this paragraph is identical in both files:** a rule changed in one file is changed in the other in the same pull request.

## Project

**AI Localization Checker.** The tool captures screenshots of a mobile game (Unciv, Android emulator) in several languages and detects localization defects — truncated text, overlaps, untranslated strings — with a vision LLM. Its quality is measured against an OCR + translation-table baseline on a labeled dataset, together with the time it saves a QA engineer.

This is a portfolio project of Anton Borodin (Senior QA / QA Lead). The point is **measured quality and measured benefit for QA**, not "an LLM integration".

**v1 scope:** one provider, one screen resolution, 8–10 screens, 2 languages, 3 defect types (`overflow`, `wrong_language`, `truncated_text`; D-044). Results of v1 are preliminary. Everything else is an extension after v1.

**Stages:** 0 environment → 1 vertical slice → 2 screenshot pipeline → 3 labeled dataset → 4 baseline without LLM → 5 vision detector → 6 eval and QA benefit → 7 report and packaging → 8 check on a second app.

## Roles

- **Anton** owns labels, acceptance criteria, thresholds, hand-computed golden examples and final conclusions. He approves plans and decisions, and he alone decides whether a pull request is merged.
- **The coding agent** implements tasks from GitHub issues (label and template `claude-task`; the name is historical and applies to any agent). It writes a plan first and starts implementing only after Anton approves the plan.
- **Review:** every pull request is reviewed in an independent session that did not write the code, preferably by a different model than the author. The author never approves its own pull request.

## Before planning any task

- Read `docs/decisions.md`. Entries with status `Accepted` are binding. If a task conflicts with one, stop and say so instead of working around it.
- Read the whole issue, including **Constraints**, **Out of scope** and any issue it depends on.

## Hard rules

- Never read, list, copy or reference the hold-out set (`~/l10n-holdout`). Never run evaluation on it: the final hold-out run is done by Anton manually.
- Never create labels or ground truth from a detector's output.
- A timeout, an API error or an invalid model response produces the status "not checked", never "no defects".
- Changes to metric or matching code come with updated hand-computed golden tests. Never change a golden expected value to make a test pass — ask Anton.
- Never skip, weaken or delete a failing test to make it pass; report it instead.
- The agent never reads, prints or copies `.env`, never prints environment variables and never prints the API key. It may make live provider calls only when the issue states a budget in requests and USD, and then only: through the project's own commands with the per-run request cap set; with the provider key named in the issue, within the issue budget in requests and USD; never on the hold-out set; within the budget across all runs of the task, failed requests included. The key is loaded with `uv run --env-file .env`, never read by the agent. Every run is recorded under `data/runs/`, and the report lists each run id, its `requests_sent`, its token usage and its estimated cost. Without a budget in the issue, no live calls (D-035).
- Unciv code is never changed in this repository. Changes to Unciv live in the fork, which is a separate folder with its own session.
- No secrets in the repository. API keys come from environment variables (`.env`, gitignored).

## When to stop and ask

Implementation details inside the approved plan — helper functions, internal names, the order of steps, test structure — are the agent's choice. Stop and ask Anton before:

- adding a dependency;
- changing the task's scope, or doing anything listed under **Out of scope**;
- changing methodology: labels, metrics, matching, the data split, evaluation settings;
- changing or working around an `Accepted` decision;
- a destructive operation: deleting the labeled dataset, accepted references,
  screenshots or manifest entries awaiting Anton's decision, approved
  screenshots or their manifest entries, run records, final task reports, or
  anything the task did not create; force-push; history rewrite. Cleaning up
  disposable files the current task created is expected and needs no approval
  (see "What to keep vs. delete").

## Keep it simple (D-059)

This is a portfolio tool; v1 results are preliminary. Choose the simplest
solution that keeps results honest and reproducible. If a plan feels heavy,
propose a simpler variant with its trade-off before implementing.

Record the commit hash, exact command, config and seed in `run.json` for
reproducibility.

### Builds and app state

- Build only the APKs the approved method needs (D-050: frozen-builder clean
  control and mutated batches). Reuse a build across attempts instead of
  rebuilding; never keep more than the builds of the current run, and delete
  them when the run ends.
- Back up the prepared app state (save files, settings) once per task, not
  per run or per attempt. Restore by clearing app data/reinstalling and
  pushing that one snapshot.

### Do not

- Archive source code or environments: no copies of `src/`, `.venv`, Android
  SDK, JDK, Gradle caches, APK contents or full device file trees. A commit hash
  identifies the code; `uv.lock` and `docs/environment.md` identify the
  environment.
- Keep old producer versions or compatibility readers for old run formats. If
  current code cannot read an old run, re-run it or drop it.
- Build proof about proof: no per-file hashes, before/after inventories or
  byte-level re-authentication around every operation. A screenshot, its
  manifest entry and the run record are enough evidence for a capture.
- Add a decision for transient noise (e.g. AndroidX bookkeeping files). Ignore
  non-game state in code with a one-line comment.
- Bump run/evidence format versions for every change. Keep one current format.
- Add locks, guards, retries or timeouts unless a real failure was observed in
  this task.
- Commit hash catalogs, changed-file lists or archive checks under
  `docs/evidence/`. Evidence in the repo = a short report plus a few
  representative screenshots.
- Write long docs: a feature section fits on one screen; a decision fits in
  about 10 lines.

### What to keep vs. delete

Keep (project assets, never delete without asking Anton):

- the labeled dataset, accepted references and approved screenshots;
- screenshots handed to Anton for manual acceptance and their manifest until
  he decides on each one; then keep only the accepted screenshots and their
  manifest entries;
- one `data/runs/<run_id>/run.json` per run, with the exact command, commit,
  config, seed and any metrics. Preserve the D-035 accounting fields:
  `run_id`, `requests_sent`, token usage and estimated cost;
- the final report of each task.

Delete disposable artifacts when the task ends (no need to ask): intermediate
captures, failed and superseded attempts, the app-state snapshot after
restoration, temporary files, scratch scripts and debug dumps. Delete built
APKs when their run ends. If a failed attempt matters, describe it in the
report in two or three sentences instead of keeping its files.

### Limits

- Run outputs go to `data/runs/` (gitignored). Git worktrees go to
  `~/Developer/worktrees/`; scratch space to `~/Developer/sandbox/`.
  Never write under `~/Documents` or `~/Desktop` (they sync to iCloud).
- Stop and ask before a step that writes more than 1,000 files or 500 MB.
- The task report states the disk footprint left behind (files and MB).

## Honest reporting

Review checks the code, the diff and the command output, not the agent's description of them. Reports must hold up against all three.

- Report only commands actually run in this task, with their real result or exit code. A check that was not run is written as "not run" with the reason.
- Never write that tests or linters pass unless they were run after the last change.
- Report skipped tests with their count and reason. `uv run pytest` skips device tests by default; a task that changes capture or device code also reports a run with `--run-device`, or says why it was not run.
- List every file changed. A change outside the task's scope is either reverted or listed under **Deviations from the task** with the reason.
- If something failed or is uncertain, say so at the top of the report, not at the end.

## Workflow

- One task = one branch = one pull request. Small commits with conventional commit messages (`feat:`, `fix:`, `test:`, `docs:`, `chore:`).
- Run the tests and the linter before saying a task is done.
- A decision made during a task is added to `docs/decisions.md` with status `Proposed`.
- Finish every task by filling in the **Report** section of the issue template, as an issue comment or in the PR description.

## Stack and commands

- Python 3.11+, pytest, ruff; SDK adb for the emulator (D-022); Allure for reports.
- Install dependencies: `uv sync`
- Run tests (offline; device tests are skipped): `uv run pytest`
- Run tests including device tests (needs a running prepared emulator, see `docs/environment.md`): `uv run pytest --run-device`; device tests only: `uv run pytest --run-device -m device`
- Run linter: `uv run ruff check . && uv run ruff format --check .`

## Repository layout

- `src/l10n_checker/` — code
- `tests/` — tests; hand-computed golden tests go in `tests/golden/`
- `docs/decisions.md` — decision log
- `.github/ISSUE_TEMPLATE/claude-task.md` — task template
- `data/` — local screenshots and run outputs, gitignored

## Communication

- Talk to Anton in the language he writes in. All repository artifacts — code, comments, commits, issues, docs — are in English.
- When something needs Anton's decision, present the options with a recommendation and ask. Do not guess on methodology or scope.
