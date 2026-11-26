"""CLI for dataset evaluation (`l10n-eval`)."""

import argparse
import os
import subprocess
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

from l10n_checker.baseline import DEFAULT_PREPROCESSING, PREPROCESSING, BaselineError
from l10n_checker.baseline_cli import output_directory
from l10n_checker.capture import CaptureError
from l10n_checker.deepseek import DEFAULT_TIMEOUT_S, THINKING_EFFORTS
from l10n_checker.evaluation import (
    DEFAULT_BUILD_REQUESTS,
    DEFAULT_INVENTORIES_DIR,
    DEFAULT_REFERENCES_DIR,
    DEFAULT_UNCIV_FORK,
    evaluate_dataset,
)
from l10n_checker.vision import VisionProvider, redact


def _decimal_arg(raw: str) -> Decimal:
    try:
        value = Decimal(raw)
    except InvalidOperation as exc:
        raise argparse.ArgumentTypeError(f"Invalid decimal value: {raw!r}") from exc
    if not value.is_finite() or value <= 0:
        raise argparse.ArgumentTypeError("USD cap must be a finite positive number")
    return value


def make_provider(
    api_key: str, timeout_s: int, thinking: str = "disabled"
) -> VisionProvider:
    from l10n_checker.deepseek import DeepSeekProvider

    return DeepSeekProvider(api_key, timeout_s=timeout_s, thinking=thinking)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate baseline or vision detector on a labeled dataset folder."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        required=True,
        help="Folder of *.png screenshots and matching *.labels.json files.",
    )
    parser.add_argument(
        "--detector",
        choices=("baseline", "vision"),
        required=True,
        help="Detector to run across the dataset.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Run output folder inside data/ (e.g. data/runs/<run_id>).",
    )
    parser.add_argument(
        "--build-requests",
        type=Path,
        default=DEFAULT_BUILD_REQUESTS,
        help="JSON mapping batch IDs to translation patches.",
    )
    parser.add_argument(
        "--unciv-fork",
        type=Path,
        default=DEFAULT_UNCIV_FORK,
        help="Path to the Unciv git repository with the base commit translations.",
    )
    parser.add_argument(
        "--inventories-dir",
        type=Path,
        default=DEFAULT_INVENTORIES_DIR,
        help="Folder of <screen>.json baseline inventories.",
    )
    parser.add_argument(
        "--references-dir",
        type=Path,
        default=DEFAULT_REFERENCES_DIR,
        help="Folder of confirmed <screen>__<lang>/reference.json files.",
    )
    parser.add_argument(
        "--preprocess",
        choices=PREPROCESSING,
        default=DEFAULT_PREPROCESSING,
        help="OCR preprocessing variant for baseline (default: %(default)s).",
    )
    parser.add_argument(
        "--max-requests",
        type=int,
        default=None,
        help="Vision only: required dataset-wide request cap.",
    )
    parser.add_argument(
        "--max-usd",
        "--usd-cap",
        dest="max_usd",
        type=_decimal_arg,
        default=None,
        help="Vision only: required dataset-wide USD cap.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_S,
        help="Vision only: request timeout in seconds (default: %(default)s).",
    )
    parser.add_argument(
        "--thinking",
        choices=THINKING_EFFORTS,
        default="disabled",
        help="Vision only: thinking mode / reasoning effort (default: %(default)s).",
    )
    parser.add_argument(
        "--keep-records",
        action="store_true",
        help="Keep per-image OCR/diagnostic or vision folders under records/.",
    )

    raw_argv = list(argv) if argv is not None else sys.argv[1:]
    args = parser.parse_args(raw_argv)

    if args.detector == "vision":
        if args.max_requests is None or args.max_requests < 1:
            parser.error("--detector vision requires --max-requests >= 1")
        if args.max_usd is None:
            parser.error("--detector vision requires --max-usd")
    else:
        if args.max_requests is not None or args.max_usd is not None:
            parser.error("--max-requests and --max-usd apply only to --detector vision")
        if args.thinking != "disabled":
            parser.error("--thinking applies only to --detector vision")

    api_key = ""
    secrets: tuple[str, ...] = ()
    try:
        target_dir = output_directory(args.output_dir)
        provider_factory = None
        if args.detector == "vision":
            api_key = os.environ.get("DEEPSEEK_API_KEY", "")
            if not api_key:
                raise ValueError("DEEPSEEK_API_KEY is not set; no request was sent")
            secrets = (api_key,)
            provider_factory = lambda: make_provider(
                api_key, args.timeout, args.thinking
            )

        run_record, _ = evaluate_dataset(
            dataset_dir=args.dataset,
            detector=args.detector,
            output_dir=target_dir,
            command=["l10n-eval", *raw_argv],
            build_requests_path=args.build_requests,
            unciv_fork=args.unciv_fork,
            inventories_dir=args.inventories_dir,
            references_dir=args.references_dir,
            preprocess=args.preprocess,
            provider_factory=provider_factory,
            max_requests=args.max_requests,
            max_usd=args.max_usd,
            keep_records=args.keep_records,
            secrets=secrets,
        )
    except (
        BaselineError,
        CaptureError,
        OSError,
        ValueError,
        KeyError,
        TypeError,
        subprocess.SubprocessError,
    ) as exc:
        print(
            redact(f"Evaluation failed: {exc}", secrets),
            file=sys.stderr,
        )
        return 1

    metrics = run_record["metrics"]
    print(target_dir)
    print(
        f"tp={metrics['tp']} (obs={metrics['tp_observed']}, miss={metrics['tp_missing']}) "
        f"fp={metrics['fp']} fn={metrics['fn']} "
        f"not_checked={metrics['not_checked_screens']} "
        f"fn_on_not_checked={metrics['fn_on_not_checked']} "
        f"empty_label_fp={metrics['empty_label_fp']}"
    )
    return 2 if metrics["not_checked_screens"] else 0


if __name__ == "__main__":
    sys.exit(main())
