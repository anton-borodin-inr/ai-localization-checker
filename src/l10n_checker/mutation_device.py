"""Approved install/capture transactions; never uninstall, provision saves or build."""

import subprocess

from l10n_checker import app_data

# Shared app-data readers are also used by standalone capture.
from l10n_checker.mutation_catalog import require

# Preserve the public compatibility constant without a cyclic dependency.
ANDROIDX_BOOKKEEPING = app_data.ANDROIDX_BOOKKEEPING


def assert_idle(device):
    result = subprocess.run(
        ["pgrep", "-fl", "l10n-capture"], capture_output=True, timeout=10, check=False
    )
    require(
        result.returncode == 1 and not result.stdout.strip(),
        "Another l10n-capture process is active or process check failed",
    )
    device.connect()
    online = [
        line.split()[0]
        for line in device.run("devices").decode().splitlines()
        if len(line.split()) == 2
        and line.split()[0].startswith("emulator-")
        and line.split()[1] == "device"
    ]
    require(
        online == [device.serial],
        "Exactly one emulator is required by the environment checker",
    )
    require(
        not device.pid(), "Unciv is already running; emulator has not been released"
    )
