"""Command-line entry point for one screenshot."""

import argparse
import os
import sys
from pathlib import Path

from l10n_checker.capture import DEFAULT_SERVER, CaptureError, Device, capture


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


if __name__ == "__main__":
    sys.exit(main())
