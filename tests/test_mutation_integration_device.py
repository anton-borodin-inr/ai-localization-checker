"""Only the catalog-bound dev pipeline; never run the legacy device smokes."""

from pathlib import Path

import pytest

from l10n_checker.mutation_run import run_config
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


@pytest.mark.device
def test_real_dev_calibration_measurement(request):
    """Passing means diagnostic completion only, never calibration qualification."""
    path = request.config.getoption("--mutation-device-config")
    if not path:
        pytest.fail("Measurement requires an approved --mutation-device-config")
    config = json_bytes(Path(path).read_bytes())
    assert (
        config["sha256"]
        == "790b21921ca3d4988b6257a6da235817c8b8407b2f029871c74a05598efaf354"
    )
    # run_config authenticates both actual versionCodes before Device construction.
    result = run_config(config, measurement_only=True)
    assert (
        result["measurement_only"] is True and result["measurement_complete"] is True
    ), f"Measurement incomplete; retained evidence at {config['output_dir']}"
    assert result["status"] == result["calibration_status"] == "failed"
    assert (
        result["capture_set_qualified"] is False and result["labels_created"] is False
    )
    assert (
        result["downgrade_verified"] is True and result["restoration_verified"] is True
    )
    assert result["dynamic_tests"] == [] and "handoff" not in result
    assert not (Path(config["output_dir"]) / "builder-handoff").exists()
    screens = {
        "options-gameplay",
        "tech-picker",
        "city-production",
        "empire-stats",
        "civilopedia",
    }
    assert set(result["screen_ids"]) == screens
    assert len(result["screenshots"]) == 40
    assert {s["role"] for s in result["screenshots"]} == {"clean", "calibration"}
    for role, code in (("clean", "1888080431"), ("calibration", "1808820362")):
        shots = [s for s in result["screenshots"] if s["role"] == role]
        assert len(shots) == 20
        assert {(s["screen"], s["language"], s["pass"]) for s in shots} == {
            (screen, language, n)
            for screen in screens
            for language in ("en", "de")
            for n in (1, 2)
        }
        assert all(s["build"]["version_code"] == code for s in shots)
