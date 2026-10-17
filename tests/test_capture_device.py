import os
import uuid
from pathlib import Path

import pytest

from l10n_checker.capture import REPO_ROOT, Device, capture, png_size


@pytest.mark.device
def test_real_capture():
    sdk = Path(os.environ.get("ANDROID_HOME", str(Path.home() / "Library/Android/sdk")))
    device = Device(sdk / "platform-tools/adb")
    folder = REPO_ROOT / "data" / "device-tests" / uuid.uuid4().hex
    target = capture(device, folder, "current", "unspecified", "original")
    assert png_size(target.read_bytes()) == device.size()
    assert target.name.endswith(f"__{device.build()}.png")
