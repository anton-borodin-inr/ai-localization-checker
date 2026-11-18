"""Only the catalog-bound dev pipeline; never run the legacy device smokes."""

from pathlib import Path

import pytest

from l10n_checker.mutation_task import run_task
from l10n_checker.screen_manifest import json_bytes


@pytest.mark.device
def test_real_dev_mutation_generation(request):
    path = request.config.getoption("--mutation-device-config")
    if not path:
        pytest.fail(
            "Mutation device verification requires an approved --mutation-device-config"
        )
    config = json_bytes(Path(path).read_bytes())
    result = run_task(
        config, command=["pytest", "--run-device", "--mutation-device-config", path]
    )
    assert result["status"] == "qualified", (
        f"Mutation run stopped as {result['status']}; retained evidence at {config['output_dir']}"
    )
    assert result["calibration_status"] == "passed"
    assert result["restoration_verified"] and result["labels_created"] is False
