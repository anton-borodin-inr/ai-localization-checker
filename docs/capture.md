# Capture one current screen

Issue #2 adds capture only: no navigation, language switching, detection or model calls.
Use the existing Stage 0 environment from [environment.md](environment.md).

## Run

From the repository root:

```bash
uv sync
scripts/prepare_emulator.sh
scripts/check_env.sh
npm run appium
```

Keep that project-local server running. With Unciv already showing the intended
screen, run in another terminal:

```bash
uv run l10n-capture --screen main-menu --lang en --variant original \
  --output-dir data/captures
```

For the Stage 0 APK and landscape screen, the result is:

```text
data/captures/main-menu__en__2400x1080__original__1271.png
```

`screen`, `lang` and `variant` describe the current screen; the command does not
navigate or verify the supplied language. Resolution is read from the device's
current display info; build is the installed `com.unciv.app` APK `versionCode`.
Filename fields start with an ASCII letter or digit and allow letters, digits,
periods, hyphens and underscores, but no `__` delimiter within a field.

The output folder must resolve inside this checkout's `data/`. Existing images
are protected: use `--overwrite` explicitly to replace one. Use `--serial
emulator-5554` when more than one emulator is connected. The default Appium URL
is `http://127.0.0.1:4723`; `--server` overrides it.

Only `$ANDROID_HOME/platform-tools/adb` is used, with the documented macOS SDK
location as the fallback when `ANDROID_HOME` is unset. Run
`scripts/prepare_emulator.sh` after every emulator boot. Capture refuses an active
or unknown display cutout and never changes the AVD, app settings or orientation.
The Python client attaches with `noReset`, `autoLaunch=false` and `skipUnlock`.
Unciv must already be in the foreground.

Cutout validation is fail-closed: a built-in display device line with a cutout
field is accepted only when its insets are zero. If the line or its cutout field
is missing, only an explicitly disabled Pixel 7 overlay is accepted. Missing, enabled or indeterminate overlay state
fails. Both environment scripts use `scripts/cutout.sh`; Python follows the
same policy, covered with shared test cases. PNG structure, CRCs and dimensions
are checked before saving; dimensions must match the current device screen.

## Verify

```bash
uv run pytest
uv run pytest --run-device -m device
uv run ruff check . && uv run ruff format --check .
```

The first command skips device tests by default and requires no emulator or
Appium. The second explicitly captures from a prepared device into a unique
folder under `data/device-tests/`.

For the negative server check, stop your project-local Appium server and run:

```bash
uv run l10n-capture --screen main-menu --lang en --variant server-stopped \
  --output-dir data/captures
```

Expected: exit 1, an actionable Appium connection error, no traceback and no PNG.
A stopped or unavailable emulator similarly produces an actionable error. An
invalid field, unknown cutout, absent Unciv or mismatched PNG size is also an error.

## Informational timing

```bash
uv run python scripts/benchmark_capture.py --output-dir data/timing
```

This performs 10 captures through an existing Appium session, then 10 through
SDK `adb exec-out screencap -p`. Each sample sums PNG retrieval and file-write
wall time (`perf_counter`). Validation is outside the timed intervals and runs
before each file is saved. There is no warmup or `fsync`; filesystem cache and
method order can affect results. Session setup is measured separately. This is
not an end-to-end CLI timing or a decision to choose either transport.

Observed on 2026-10-17, MacBook Pro M3 Pro, existing API 34 AVD, Unciv 4.22.10
(versionCode 1271), English main menu at 2400 x 1080, Appium 3.3.1,
uiautomator2 7.1.2, Appium-Python-Client 6.0.7:

| Method | Captures | Mean retrieval + write |
|---|---:|---:|
| Appium | 10 | 0.172879 s |
| SDK adb | 10 | 0.185464 s |

Appium session setup: 1.453809 s. Raw samples and PNGs are local in
`data/issue-2/timing/`; none are committed. These measurements are input to the
Stage 1 decision, not evidence of a general performance advantage.
