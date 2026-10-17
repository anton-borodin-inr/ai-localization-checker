import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--run-device",
        action="store_true",
        help="Run tests requiring the emulator and Appium",
    )


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--run-device"):
        for item in items:
            if "device" in item.keywords:
                item.add_marker(
                    pytest.mark.skip(
                        reason="Use --run-device with a prepared emulator and Appium"
                    )
                )
