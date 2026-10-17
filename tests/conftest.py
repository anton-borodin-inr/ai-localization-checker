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


def make_png(width=4, height=2):
    """A minimal valid PNG with the given size."""
    import struct
    import zlib

    def chunk(kind, data):
        crc = struct.pack(">I", zlib.crc32(kind + data))
        return struct.pack(">I", len(data)) + kind + data + crc

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress((b"\x00" + b"\xff\x00\x00" * width) * height))
        + chunk(b"IEND", b"")
    )


@pytest.fixture
def screenshot(tmp_path):
    path = tmp_path / "main-menu__en__4x2__original__1.png"
    path.write_bytes(make_png())
    return path
