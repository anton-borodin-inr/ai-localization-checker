"""Command-line entry points for one screenshot: capture and vision check."""

import argparse
import os
import sys
from pathlib import Path

from l10n_checker.capture import (
    DEFAULT_SERVER,
    CaptureError,
    Device,
    capture,
    output_directory,
)
from l10n_checker.vision import RequestBudget, redact, run_check


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Capture the current Unciv screen through Appium."
    )
    parser.add_argument("--screen", required=True)
    parser.add_argument("--lang", required=True)
    parser.add_argument("--variant", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--serial")
    parser.add_argument("--server", default=DEFAULT_SERVER)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    sdk = Path(os.environ.get("ANDROID_HOME", str(Path.home() / "Library/Android/sdk")))
    try:
        target = capture(
            Device(sdk / "platform-tools/adb", args.serial),
            args.output_dir,
            args.screen,
            args.lang,
            args.variant,
            args.server,
            args.overwrite,
        )
    except (CaptureError, OSError) as exc:
        print(f"Capture failed: {exc}", file=sys.stderr)
        return 1
    print(target)
    return 0


def make_provider(api_key: str, model: str):
    from l10n_checker.gemini import GeminiProvider

    return GeminiProvider(api_key, model)


def check_main() -> int:
    from l10n_checker.gemini import DEFAULT_MODEL

    parser = argparse.ArgumentParser(
        description="Check one screenshot for localization defects with Gemini."
    )
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--runs-dir", type=Path, default=Path("data/runs"))
    parser.add_argument("--max-requests", type=int, default=1)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        print("GEMINI_API_KEY is not set; no request was sent.", file=sys.stderr)
        return 1
    try:
        result, run_dir = run_check(
            make_provider(api_key, args.model),
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
