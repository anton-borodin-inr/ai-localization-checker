"""CLI for the offline baseline; never initializes a provider or reads a key."""

import argparse
import sys
from pathlib import Path

from l10n_checker.baseline import run_baseline
from l10n_checker.capture import CaptureError
from l10n_checker.ocr import ENGINES, PREPROCESSING, ConfiguredOcr


def output_directory(path: Path) -> Path:
    """Anchor this CLI to the checkout cwd, including non-editable installs."""
    directory = path.resolve()
    if not directory.is_relative_to(Path.cwd().resolve() / "data"):
        raise CaptureError(
            "The output folder must be inside the current checkout's data/."
        )
    return directory


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Offline OCR + Unciv translation baseline"
    )
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--unciv-fork", type=Path, required=True)
    parser.add_argument("--runs-dir", type=Path, default=Path("data/baseline-runs"))
    parser.add_argument("--ocr-engine", choices=ENGINES, default="tesseract")
    parser.add_argument("--ocr-preprocess", choices=PREPROCESSING, default="none")
    parser.add_argument("--ocr-model-dir", type=Path, default=Path("data/ocr-models"))
    args = parser.parse_args()
    engine = None
    try:
        if (args.ocr_engine, args.ocr_preprocess) != ("tesseract", "none"):
            engine = ConfiguredOcr(
                args.ocr_engine, args.ocr_preprocess, args.ocr_model_dir
            )
        result, directory = run_baseline(
            args.image,
            args.manifest,
            args.inventory,
            args.unciv_fork,
            output_directory(args.runs_dir),
            *([engine] if engine is not None else []),
        )
    except (CaptureError, OSError) as exc:
        print(f"Cannot record baseline run: {exc}", file=sys.stderr)
        return 1
    finally:
        if engine is not None:
            engine.close()
    print(directory)
    if result.status == "not_checked":
        print(f"not_checked: {result.reason}")
        return 2
    print(f"checked: {len(result.findings)} finding(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
