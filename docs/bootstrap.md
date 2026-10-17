# Bootstrap: AI Localization Checker repository

You are setting up a new repository for Anton in the current, almost empty folder. It contains this file, `CLAUDE.md`, `decisions.md` and `claude-task.md`.

Start in plan mode: read this file and the three others, then present a short plan and wait for Anton's approval. Work through the steps in order. Stop and ask before anything that publishes, cannot be undone, or needs credentials.

## Settings

Anton may edit these values before starting.

```
REPO_NAME:      ai-localization-checker
VISIBILITY:     public
LICENSE:        MIT, copyright holder "Anton Borodin", year 2026
DESCRIPTION:    Vision-LLM localization defect detector for mobile games, evaluated against an OCR baseline
TOPICS:         qa, test-automation, localization, llm, vision-language-model, android, appium, game-testing, evaluation
HOLDOUT_DIR:    ~/l10n-holdout
UNCIV_UPSTREAM: yairm210/Unciv
PACKAGE_NAME:   l10n_checker
```

## Step 1 — Check the environment

- `git --version`, and `git config --global user.name` / `user.email` are set.
- `gh auth status` shows a logged-in account. If not, stop and ask Anton to run `gh auth login` himself. Never handle tokens or passwords.
- Python tooling: if `uv` is installed, use it (it can also provide Python 3.11+). If not, ask Anton whether to install it with Homebrew or to use `python3 -m venv` + pip.

Report what you found before changing anything.

## Step 2 — Hold-out folder and its guard

1. With Anton's approval, create `HOLDOUT_DIR` outside the repository and put one file in it: `CANARY.txt` with the text `canary`.
2. Create `.claude/settings.json`:

   ```json
   {
     "permissions": {
       "deny": ["Read(~/l10n-holdout/**)", "Read(./.env)"],
       "blockReadsOutsideWorkingDirectories": true
     }
   }
   ```

3. Verify the guard: try to read `~/l10n-holdout/CANARY.txt` with the Read tool and with `cat`. Both must be refused. Report the exact result. If either read succeeds, stop and tell Anton.

This guard covers Claude Code's own tools and the shell commands it recognizes, not scripts that open files themselves. That is why the final hold-out run is Anton's manual step.

## Step 3 — Repository files

- Keep `CLAUDE.md` at the root. Fill in the three `<filled in during bootstrap>` commands with the real ones for the chosen tooling; change nothing else in it.
- Move `decisions.md` → `docs/decisions.md` and `claude-task.md` → `.github/ISSUE_TEMPLATE/claude-task.md` without changing their content.
- Move this file to `docs/bootstrap.md` (it stays as a record of how the repository was set up).
- `LICENSE`: the standard MIT text with the holder and year from Settings.
- `.gitignore`: the standard Python template plus `data/`, `runs/`, `*.apk`, `.env`, `.claude/settings.local.json`, `allure-results/`, `allure-report/`.
- `pyproject.toml`: project `REPO_NAME`, `requires-python >= 3.11`, package `PACKAGE_NAME` under `src/`, dev dependencies `pytest` and `ruff`. Nothing else yet; Appium and the other dependencies come with the Stage 0 task.
- `src/l10n_checker/__init__.py` with a version string, and `tests/test_smoke.py` with one test that imports the package.
- `tests/golden/` with a `README.md` of two lines: what golden tests are for and that their expected values are computed by hand by Anton.
- `README.md` skeleton:
  - title and a one-paragraph description from `CLAUDE.md`;
  - status: "Work in progress — Stage 0";
  - empty sections: Problem, Approach, Results, Limitations, How this was built;
  - "How this was built" contains one sentence saying the code is written with Claude Code, with links to `docs/decisions.md` and `docs/bootstrap.md`.
  - Invent no results, numbers or claims.

## Step 4 — Verify locally

- Install dependencies, then run the tests and the linter. Both must pass.
- `git init` (if needed), main branch `main`, one commit: `chore: bootstrap repository`.

## Step 5 — Publish (ask first)

Ask Anton once, showing `REPO_NAME`, `VISIBILITY` and the file list. After a clear yes:

- `gh repo create REPO_NAME --public --source=. --remote=origin --description "DESCRIPTION" --push`
- Add the topics with `gh repo edit --add-topic ...`.
- Create the label: `gh label create claude-task --description "Implementation task for Claude Code"`.
- Fork the Unciv upstream on GitHub **without cloning**: `gh repo fork UNCIV_UPSTREAM --clone=false`. The clone and the Unciv build belong to Stage 1.

## Step 6 — Report

Report in the same format as the template's Report section:

- what changed;
- how it was verified, including the canary result;
- deviations from this file;
- open questions;
- links to the new repository and the fork.

End by asking Anton to run `/status` and confirm that project settings appear under "Setting sources".

Do not create issues or start Stage 0. The tasks are written separately.
