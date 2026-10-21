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
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--screen", help="Legacy single-screen capture for ordinary APKs."
    )
    mode.add_argument(
        "--manifest", type=Path, help="D-038 manifest: forward and reverse passes."
    )
    parser.add_argument(
        "--lang",
        action="append",
        help="Repeat for several languages; defaults to the manifest list.",
    )
    parser.add_argument(
        "--variant", help="Legacy mode only; manifest captures use clean."
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--serial")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--settle",
        type=float,
        help="Legacy mode only: launch delay (default 8 seconds).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        help="Manifest hook deadline, greater than 60 s (default 90).",
    )
    parser.add_argument(
        "--repeat",
        type=int,
        choices=[2],
        help="Manifest mode: two passes (default), second in reverse screen order.",
    )
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help="Verify manifest/build and back up data without app-data writes.",
    )
    parser.add_argument(
        "--device-plan",
        type=Path,
        help="Manifest mode: require device/inputs to match this prepared plan before writes.",
    )
    args = parser.parse_args()
    sdk = Path(os.environ.get("ANDROID_HOME", str(Path.home() / "Library/Android/sdk")))
    device = Device(sdk / "platform-tools/adb", args.serial)
    if args.manifest:
        if args.variant is not None or args.settle is not None:
            parser.error("--variant and --settle belong to legacy --screen mode")
        if args.prepare_only and args.overwrite:
            parser.error("--prepare-only requires a fresh backup folder")
        from l10n_checker.screen_capture import capture_manifest, prepare_device
        from l10n_checker.screen_manifest import Inputs

        try:
            inputs = Inputs(args.manifest)
            if args.prepare_only:
                prepare_device(device, inputs, args.output_dir, args.lang)
                print(args.output_dir / "device-plan.json")
                return 0
            summary = capture_manifest(
                device,
                inputs,
                args.output_dir,
                args.lang,
                overwrite=args.overwrite,
                timeout_s=args.timeout if args.timeout is not None else 90,
                device_plan=args.device_plan,
            )
        except (CaptureError, OSError) as exc:
            print(f"Capture failed: {exc}", file=sys.stderr)
            return 1
        print(args.output_dir / "summary.json")
        print(args.output_dir / "gallery.html")
        if summary["status"] == "complete":
            print(f"complete: {len(summary['comparisons'])} pixel-identical pairs")
            return 0
        print(
            "Capture incomplete or non-identical; inspect summary.json", file=sys.stderr
        )
        return 2
    if (
        args.prepare_only
        or args.timeout is not None
        or args.repeat is not None
        or args.device_plan is not None
    ):
        parser.error(
            "--prepare-only, --timeout, --repeat and --device-plan require --manifest"
        )
    if not args.lang or not args.variant:
        parser.error("Legacy --screen mode requires --lang and --variant")
    if not set(args.lang) <= LANGUAGES.keys():
        parser.error("Legacy languages must be en or de")
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
                settle_s=args.settle if args.settle is not None else DEFAULT_SETTLE_S,
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
