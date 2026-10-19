"""Measure adb PNG retrieval plus disk writing; no detector or paid API calls."""

import argparse
import json
import os
from pathlib import Path
from statistics import mean
from time import perf_counter

from l10n_checker.capture import (
    CaptureError,
    Device,
    output_directory,
    png_size,
    unciv_in_foreground,
)

SAMPLES = 10


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    folder = output_directory(args.output_dir)
    folder.mkdir(parents=True, exist_ok=True)
    sdk = Path(os.environ.get("ANDROID_HOME", str(Path.home() / "Library/Android/sdk")))
    device = Device(sdk / "platform-tools/adb")
    device.connect()
    device.check_cutout()
    unciv_in_foreground(device)
    size = device.size()
    result = {
        "samples": SAMPLES,
        "size": size,
        "versionCode": device.build(),
        "method": "adb exec-out screencap -p",
        "scope": "PNG retrieval plus write_bytes; validation excluded; no fsync; no warmup",
        "seconds": {},
    }
    samples = []
    for i in range(SAMPLES):
        device.check_cutout()
        unciv_in_foreground(device)
        path = folder / f"adb-{i + 1:02d}.png"
        start = perf_counter()
        payload = device.screenshot()
        retrieve_elapsed = perf_counter() - start
        if png_size(payload) != size or device.size() != size:
            raise CaptureError("Benchmark screenshot size mismatch.")
        start = perf_counter()
        path.write_bytes(payload)
        samples.append(retrieve_elapsed + perf_counter() - start)
    result["seconds"] = {"samples": samples, "mean": mean(samples)}
    report = folder / "timings.json"
    report.write_text(json.dumps(result, indent=2) + "\n")
    print(report.read_text())


if __name__ == "__main__":
    try:
        main()
    except (CaptureError, OSError) as exc:
        raise SystemExit(f"Benchmark failed: {exc}") from None
