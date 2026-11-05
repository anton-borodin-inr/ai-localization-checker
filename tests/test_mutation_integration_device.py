"""Only the catalog-bound dev pipeline; never run the legacy device smokes."""

from pathlib import Path

import pytest

from l10n_checker.mutation_run import run_config
from l10n_checker.screen_manifest import json_bytes


@pytest.mark.device
def test_real_dev_mutation_generation(request):
    path = request.config.getoption("--mutation-device-config")
    if not path:
        pytest.fail(
            "Mutation device verification requires an approved --mutation-device-config"
        )
    config = json_bytes(Path(path).read_bytes())
    result = run_config(config)
    assert result["status"] == "qualified", (
        f"Mutation run stopped as {result['status']}; retained evidence at {config['output_dir']}"
    )
    assert result["calibration_status"] == "passed"
    assert result["downgrade_verified"] and result["restoration_verified"]
    assert result["capture_set_qualified"] and result["labels_created"] is False
