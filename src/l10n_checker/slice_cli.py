"""Live slice orchestration and offline replay entry point."""

import argparse
import os
import sys
from pathlib import Path

from l10n_checker.baseline_cli import output_directory
from l10n_checker.capture import CaptureError
from l10n_checker.slice import prepare, read, replay, run_slice


def main() -> int:
    parser = argparse.ArgumentParser(description="Run or replay the vertical slice")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    for name in (
        "images",
        "labels",
        "reference",
        "approval",
        "manifest",
        "inventory",
        "unciv-fork",
    ):
        run.add_argument(f"--{name}", type=Path, required=True)
    run.add_argument("--workspace", type=Path, default=Path("data/runs/issue-14"))
    run.add_argument("--max-requests", type=int, choices=[1], required=True)
    offline = commands.add_parser("replay")
    offline.add_argument("--bundle", type=Path, required=True)
    offline.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    api_key = ""
    try:
        if args.command == "replay":
            replay(args.bundle, args.output)
            print(args.output)
            return 0
        prepared = prepare(
            args.images,
            args.labels,
            args.reference,
            args.approval,
            args.manifest,
            args.inventory,
            args.unciv_fork,
        )
        api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY is not set; no request sent")
        from l10n_checker.deepseek import DeepSeekProvider

        path = run_slice(
            prepared,
            args.reference,
            args.approval,
            args.manifest,
            args.inventory,
            args.unciv_fork,
            output_directory(args.workspace),
            lambda: DeepSeekProvider(api_key),
            secrets=(api_key,),
        )
        print(path)
        totals = read(path / "comparison.json")["totals"]
        return 2 if any(t["not_checked_screens"] for t in totals.values()) else 0
    except (OSError, ValueError, KeyError, StopIteration, CaptureError) as exc:
        from l10n_checker.vision import redact

        print(
            redact(f"Slice failed: {exc}", (api_key,) if api_key else ()),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
