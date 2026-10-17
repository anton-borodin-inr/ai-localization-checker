"""Measure PNG retrieval plus disk writing; no detector or paid API calls."""

import argparse
import json
import os
from pathlib import Path
from statistics import mean
from time import perf_counter

from l10n_checker.capture import (
    PACKAGE,
    CaptureError,
    Device,
    appium_session,
    output_directory,
    png_size,
)


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
    size = device.size()
    result = {
        "samples_per_method": 10,
        "size": size,
        "versionCode": device.build(),
        "scope": "PNG retrieval plus write_bytes; validation excluded; no fsync; no warmup",
        "order": "Appium then adb, sequential groups",
        "seconds": {},
    }
    start = perf_counter()
    with appium_session(device) as driver:
        result["session_setup_seconds"] = perf_counter() - start
        if driver.current_package != PACKAGE:
            raise CaptureError("Open Unciv before benchmarking.")
        methods = {
            "appium": driver.get_screenshot_as_png,
            "adb": lambda: device.run("exec-out", "screencap", "-p"),
        }
        for method, retrieve in methods.items():
            samples = []
            for i in range(10):
                device.check_cutout()
                if driver.current_package != PACKAGE:
                    raise CaptureError("Unciv left the foreground during benchmarking.")
                path = folder / f"{method}-{i + 1:02d}.png"
                start = perf_counter()
                payload = retrieve()
                retrieve_elapsed = perf_counter() - start
                device.check_cutout()
                if png_size(payload) != size or device.size() != size:
                    raise CaptureError("Benchmark screenshot size mismatch.")
                start = perf_counter()
                path.write_bytes(payload)
                elapsed = retrieve_elapsed + perf_counter() - start
                samples.append(elapsed)
            result["seconds"][method] = {"samples": samples, "mean": mean(samples)}
    report = folder / "timings.json"
    report.write_text(json.dumps(result, indent=2) + "\n")
    print(report.read_text())


if __name__ == "__main__":
    try:
        main()
    except (CaptureError, OSError) as exc:
        raise SystemExit(f"Benchmark failed: {exc}") from None
