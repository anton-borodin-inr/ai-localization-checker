import os
from pathlib import Path

import pytest

from l10n_checker import capture as capture_module
from l10n_checker.capture import Device, capture, png_size


@pytest.mark.device
def test_real_capture(tmp_path, monkeypatch):
    monkeypatch.setattr(capture_module, "REPO_ROOT", tmp_path)
    sdk = Path(os.environ.get("ANDROID_HOME", str(Path.home() / "Library/Android/sdk")))
    device = Device(sdk / "platform-tools/adb")
    folder = tmp_path / "data" / "capture"
    target = capture(device, folder, "main-menu", "en", "original")
    # Unciv is left stopped, so the device is back in the launcher's orientation;
    # the resolution recorded in the filename must match the image itself.
    resolution = target.name.split("__")[2]
    assert "x".join(map(str, png_size(target.read_bytes()))) == resolution
    assert target.name.endswith(f"__{device.build()}.png")
