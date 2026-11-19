"""CLI for Stage 3 dev label drafting and confirmed-export writing (D-062)."""

import argparse
import sys
from pathlib import Path

from pydantic import ValidationError

from l10n_checker.capture import CaptureError
from l10n_checker.labeling import draft_run, write_labels


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    draft = commands.add_parser(
        "draft",
        help="Build manifest-backed drafts and write label-review.html next to PNGs",
    )
    draft.add_argument(
        "--run-dir",
        type=Path,
        required=True,
        help="Run directory containing PNGs, mutation-manifest.json and acceptance.json",
    )
    draft.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional output HTML path (default: <run-dir>/label-review.html)",
    )

    write = commands.add_parser(
        "write",
        help="Validate Anton's review export and write schema v2 .labels.json files",
    )
    write.add_argument(
        "--export",
        type=Path,
        required=True,
        help="JSON exported from label-review.html",
    )
    write.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Destination folder for <stem>.labels.json files (e.g. datasets/dev)",
    )
    write.add_argument(
        "--acceptance",
        type=Path,
        default=None,
        help="Optional acceptance.json to verify exact accepted screenshot coverage",
    )
    write.add_argument(
        "--copy-pngs-from",
        type=Path,
        default=None,
        help="Optional folder from which to copy the matching PNGs into output-dir",
    )

    args = parser.parse_args(argv)
    try:
        if args.command == "draft":
            html_path = draft_run(args.run_dir, output_html=args.output)
            print(f"Review page written: {html_path}")
        else:
            written = write_labels(
                args.export,
                args.output_dir,
                acceptance_path=args.acceptance,
                copy_pngs_from=args.copy_pngs_from,
            )
            print(f"Wrote {len(written)} label files to {args.output_dir}")
    except (
        CaptureError,
        OSError,
        ValueError,
        TypeError,
        KeyError,
        ValidationError,
    ) as exc:
        print(f"Labeling error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
