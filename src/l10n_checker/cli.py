"""Command-line entry points for one screenshot: capture and vision check."""

import argparse
import os
import sys
from pathlib import Path

from l10n_checker.capture import (
    DEFAULT_SETTLE_S,
    LANGUAGES,
    CaptureError,
    Device,
    capture,
    output_directory,
)
from l10n_checker.vision import RequestBudget, redact, run_check


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Launch Unciv in each requested language and capture the screen."
    )
    parser.add_argument("--screen", required=True)
    parser.add_argument(
        "--lang",
        required=True,
        action="append",
        choices=sorted(LANGUAGES),
        help="Repeat for several languages; captured in the given order.",
    )
    parser.add_argument("--variant", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--serial")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--settle",
        type=float,
        default=DEFAULT_SETTLE_S,
        help="Seconds to wait after launch before the screenshot.",
    )
    args = parser.parse_args()
    sdk = Path(os.environ.get("ANDROID_HOME", str(Path.home() / "Library/Android/sdk")))
    device = Device(sdk / "platform-tools/adb", args.serial)
    saved = []
    for lang in args.lang:
        try:
            target = capture(
                device,
                args.output_dir,
                args.screen,
                lang,
                args.variant,
                overwrite=args.overwrite,
                settle_s=args.settle,
            )
        except (CaptureError, OSError) as exc:
            print(f"Capture failed ({lang}): {exc}", file=sys.stderr)
            if saved:
                print("Saved before the failure:", *saved, sep="\n  ", file=sys.stderr)
            return 1
        saved.append(target)
        print(target)
    return 0


def make_provider(api_key: str, timeout_s: int):
    from l10n_checker.deepseek import DeepSeekProvider

    return DeepSeekProvider(api_key, timeout_s)


def check_main() -> int:
    from l10n_checker.deepseek import DEFAULT_TIMEOUT_S

    parser = argparse.ArgumentParser(
        description="Check one screenshot for localization defects with DeepSeek."
    )
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--runs-dir", type=Path, default=Path("data/runs"))
    parser.add_argument("--max-requests", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_S)
    args = parser.parse_args()
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        print("DEEPSEEK_API_KEY is not set; no request was sent.", file=sys.stderr)
        return 1
    try:
        result, run_dir = run_check(
            make_provider(api_key, args.timeout),
            args.image,
            output_directory(args.runs_dir),
            RequestBudget(args.max_requests),
            secrets=(api_key,),
        )
    except (CaptureError, OSError) as exc:
        print(f"Check failed: {redact(str(exc), (api_key,))}", file=sys.stderr)
        return 1
    print(run_dir)
    if result.status == "checked":
        print(f"checked: {len(result.findings)} finding(s)")
        return 0
    print(f"not_checked: {result.reason}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
