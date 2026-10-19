"""CLI for the offline baseline; never initializes a provider or reads a key."""

import argparse
import sys
from pathlib import Path

from l10n_checker.baseline import run_baseline
from l10n_checker.capture import CaptureError, output_directory


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Offline OCR + Unciv translation baseline"
    )
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--unciv-fork", type=Path, required=True)
    parser.add_argument("--runs-dir", type=Path, default=Path("data/baseline-runs"))
    args = parser.parse_args()
    try:
        result, directory = run_baseline(
            args.image,
            args.manifest,
            args.inventory,
            args.unciv_fork,
            output_directory(args.runs_dir),
        )
    except (CaptureError, OSError) as exc:
        print(f"Cannot record baseline run: {exc}", file=sys.stderr)
        return 1
    print(directory)
    if result.status == "not_checked":
        print(f"not_checked: {result.reason}")
        return 2
    print(f"checked: {len(result.findings)} finding(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
