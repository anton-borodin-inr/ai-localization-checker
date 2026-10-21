"""Real D-038 transport smoke; requires the approved installed fixtures/build."""

import os
import uuid
from pathlib import Path

import pytest

from l10n_checker.capture import REPO_ROOT, Device, png_size, unciv_in_foreground
from l10n_checker.hook import request_screen
from l10n_checker.screen_manifest import Inputs


@pytest.mark.device
def test_real_hook_request():
    inputs = Inputs(REPO_ROOT / "fixtures/stage2/screens.json")
    sdk = Path(os.environ.get("ANDROID_HOME", str(Path.home() / "Library/Android/sdk")))
    device = Device(sdk / "platform-tools/adb")
    device.connect()
    assert device.build() == inputs.manifest.build.version_code
    device.check_cutout()
    device.force_stop()
    try:
        result = request_screen(
            device,
            "tech-picker",
            "i41-test-" + uuid.uuid4().hex,
            inputs.states["tech-picker", "de"],
            90,
        )
        assert result["frames"] >= 2
        unciv_in_foreground(device)
        assert png_size(device.screenshot()) == (2400, 1080)
    finally:
        device.force_stop()
