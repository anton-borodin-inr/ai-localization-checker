# Capture the main menu in a requested language

Issue #2 added capture of the current screen; issue #9 adds setting the language
before launch. There is still no navigation (Stage 2), detection or model call.
Use the existing Stage 0 environment from [environment.md](environment.md).

## Run

From the repository root:

```bash
uv sync
scripts/prepare_emulator.sh
scripts/check_env.sh
npm run appium
```

Keep that project-local server running. Unciv must have been launched once, so
that its settings file exists. In another terminal:

```bash
uv run l10n-capture --screen main-menu --lang en --lang de --variant original \
  --output-dir data/captures
```

For the Stage 0 APK and landscape screen, the result is:

```text
data/captures/main-menu__en__2400x1080__original__1271.png
data/captures/main-menu__de__2400x1080__original__1271.png
```

`--lang` takes `en` (Unciv `English`) or `de` (Unciv `German`), see D-021, and
can be repeated; languages are captured in the given order. If one fails, the
command stops with exit 1 and lists the files saved before the failure. The
`lang` field of the filename is the requested code. `screen` and `variant` are
labels: after launch Unciv always shows its main menu, so `--screen` should be
`main-menu` until navigation exists. Resolution is read from the device's
display info after Unciv has launched; build is the installed `com.unciv.app` APK `versionCode`
(D-016). Filename fields start with an ASCII letter or digit and allow letters,
digits, periods, hyphens and underscores, but no `__` delimiter within a field.

The output folder must resolve inside this checkout's `data/`. Existing images
are protected: use `--overwrite` explicitly to replace one. Use `--serial
emulator-5554` when more than one emulator is connected. The default Appium URL
is `http://127.0.0.1:4723`; `--server` overrides it. Only
`$ANDROID_HOME/platform-tools/adb` is used, with the documented macOS SDK
location as the fallback when `ANDROID_HOME` is unset.

## What one capture does

The method is the one verified in [#7](unciv-text-rendering.md): write the
top-level `language` key into `/data/user/0/com.unciv.app/files/GameSettings.json`
while Unciv is stopped, then launch it. For each requested language:

1. **Checks, no device changes:** filename fields, output folder, one booted
   emulator, display cutout disabled, `versionCode`, and that no PNG for this
   screen, language, variant and build exists at any resolution (unless
   `--overwrite`).
2. **`adb root`**, confirmed with `whoami == root`. Reading and writing the
   app's private file needs root.
3. **Backup:** force-stop Unciv, read the settings file and its
   `uid gid mode size`. A host copy goes to `data/capture-backups/<UTC time>-<lang>/`
   (mode 600). A missing file is an error; the command never creates it.
4. **Write:** the original JSON with only `language` set (`English` is also
   written explicitly), sent with `adb exec-in 'cat > …'`.
5. **Confirm from the device:** read the file back. Its bytes must equal what was
   written, its `language` must be the requested one, and owner, group and mode
   must be unchanged. Otherwise: `Language … not applied`, and Unciv is not
   launched.
6. **Restart:** Unciv must not be running; `am start -W` must report
   `Status: ok`, `pidof` must find the process and Unciv must be the top resumed
   activity. Otherwise: `Unciv did not restart`.
7. **Wait** `--settle` seconds (default 8, as in #7). LibGDX draws on one canvas
   with no UI tree to wait on, so a fixed wait is used.
8. **Screenshot** through an Appium session (D-015). The screen size, and so
   the filename, is read only now: before launch the device may still be in the
   launcher's portrait orientation. Then: Unciv in the foreground,
   cutout checked before and after, PNG structure and size checked. The PNG is
   kept in memory.
9. **Language kept:** force-stop Unciv and read the file again; `language` must
   still be the requested one. This catches Unciv rejecting the file and falling
   back to default settings.
10. **Restore**, also after any failure in steps 3–9: force-stop, write the
    original bytes, read them back; bytes and `uid gid mode size` must equal the
    original. On success the host backup is deleted.
11. **`adb unroot`**, always, confirmed with `whoami == shell`.

The PNG is written only when every step succeeded, including restore and
unroot. Unciv is left stopped, so it cannot rewrite the restored file.

### adb root

adbd runs as root only inside steps 2–11 of one language, and every capture
ends with `adb unroot`, also when it fails, including a half-done `adb root`. The Appium session is opened after
`adb root` and closed before `adb unroot`, because restarting adbd drops the adb
port forwards uiautomator2 uses. The `adb-root` check in `scripts/check_env.sh`
also returns adbd to `shell` when it finishes. `scripts/prepare_emulator.sh` does
not use root.

### Display cutout

Capture never changes the cutout. It confirms it is disabled before any device
change and again before and after the screenshot; an active or unknown state
fails with a hint to run `scripts/prepare_emulator.sh`. Cutout validation is
fail-closed: a built-in display device line with a cutout field is accepted only
when its insets are zero. If the line or its cutout field is missing, only an
explicitly disabled Pixel 7 overlay is accepted. Missing, enabled or
indeterminate overlay state fails. Both environment scripts use
`scripts/cutout.sh`; Python follows the same policy, covered with shared test
cases.

### Manual restore

If restore fails, the error names the host backup. With the emulator running:

```bash
adb root
adb shell am force-stop com.unciv.app
adb exec-in 'cat > /data/user/0/com.unciv.app/files/GameSettings.json' \
  < data/capture-backups/<folder>/GameSettings.json
adb exec-out cat /data/user/0/com.unciv.app/files/GameSettings.json \
  | cmp - data/capture-backups/<folder>/GameSettings.json
adb unroot
```

`cmp` prints nothing when the bytes match. A backup folder left in
`data/capture-backups/` after a run that was killed is restored the same way.

## Verify

```bash
uv run pytest
uv run pytest --run-device -m device
uv run ruff check . && uv run ruff format --check .
```

The first command skips device tests by default and requires no emulator or
Appium; the language step is tested against a fake device. The second
explicitly captures the English main menu from a prepared device into a unique
folder under `data/device-tests/`, using `adb root` as described above.

For the negative server check, stop your project-local Appium server and run:

```bash
uv run l10n-capture --screen main-menu --lang en --variant server-stopped \
  --output-dir data/captures
```

Expected: exit 1, an actionable Appium connection error, no traceback and no PNG.
In this case the settings file is still restored and adbd unrooted. A stopped or
unavailable emulator similarly produces an actionable error. An invalid field,
unsupported language, unknown cutout, absent Unciv, language that was not
applied, failed restart or mismatched PNG size is also an error.

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
