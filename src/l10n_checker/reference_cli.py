"""Offline candidate/review commands; no device or provider entry points."""

import argparse
import sys
from pathlib import Path

from pydantic import ValidationError

from l10n_checker.capture import CaptureError
from l10n_checker.text_dump import canonical_bytes
from l10n_checker.text_reference import (
    compare_capture_runs,
    confirm_bundle,
    review_one,
    review_run,
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    generate = commands.add_parser(
        "generate", help="Create unconfirmed engine-backed review pages"
    )
    source = generate.add_mutually_exclusive_group(required=True)
    source.add_argument("--capture-run", type=Path)
    source.add_argument("--pair", type=Path)
    generate.add_argument("--output-dir", type=Path, required=True)
    confirm = commands.add_parser(
        "confirm", help="Validate and import Anton's explicit browser export"
    )
    confirm.add_argument("--review-dir", type=Path, required=True)
    confirm.add_argument("--bundle", type=Path, required=True)
    confirm.add_argument("--output-dir", type=Path, required=True)
    compare = commands.add_parser(
        "compare-captures", help="Compare decoded PNGs against a previous capture run"
    )
    compare.add_argument("--capture-run", type=Path, required=True)
    compare.add_argument("--reference-run", type=Path, required=True)
    compare.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "generate":
            if args.pair:
                review_one(args.pair, args.output_dir)
            else:
                review_run(args.capture_run, args.output_dir)
            print(f"Unconfirmed candidates: {args.output_dir}")
        elif args.command == "confirm":
            confirm_bundle(args.review_dir, args.bundle, args.output_dir)
            print(f"Verified human-confirmed reference: {args.output_dir}")
        else:
            report = compare_capture_runs(args.capture_run, args.reference_run)
            with args.output.open("xb") as stream:
                stream.write(canonical_bytes(report))
            print(f"Capture comparison: {report['status']}")
            return 0 if report["status"] == "identical" else 2
    except (
        CaptureError,
        OSError,
        ValueError,
        TypeError,
        KeyError,
        ValidationError,
    ) as exc:
        print(f"Reference error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
