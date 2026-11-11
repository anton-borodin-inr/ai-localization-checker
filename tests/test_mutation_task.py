"""Fresh capture qualification through the bounded RGB gate."""

from types import SimpleNamespace

import pytest
from test_mutation_verify import png
from test_text_dump import dump_for, element

from l10n_checker import mutation_task
from l10n_checker.capture import CaptureError
from l10n_checker.text_dump import canonical_bytes, load_dump


@pytest.mark.parametrize("case", ["bounded", "unmutated", "repeat"])
def test_capture_keeps_dump_and_repeat_gates_with_d060(tmp_path, monkeypatch, case):
    screen = SimpleNamespace(id="tech-picker")
    languages = {"en": "English", "de": "German"}
    settings = {"en": b"en", "de": b"de"}
    inputs = SimpleNamespace(
        manifest=SimpleNamespace(
            build=SimpleNamespace(version_code="1271045"),
            resolution=[100, 60],
            languages=[
                SimpleNamespace(code=code, game_language=name)
                for code, name in languages.items()
            ],
        ),
        settings=settings,
        states={(screen.id, code): {} for code in languages},
        screens=lambda language, reverse: [screen],
    )
    raw = {
        code: dump_for(language=name, size=[100, 60])
        for code, name in languages.items()
    }
    clean = {
        (screen.id, code): (png(), load_dump(canonical_bytes(dump)))
        for code, dump in raw.items()
    }
    if case == "unmutated":
        raw["en"]["elements"] = [element(bounds=[11, 20, 30, 40])]
    monkeypatch.setattr(mutation_task, "unciv_in_foreground", lambda device: None)
    monkeypatch.setattr(
        mutation_task,
        "request_screen",
        lambda *args, **kwargs: {"dump": {"file": "dump"}},
    )
    monkeypatch.setattr(
        mutation_task,
        "read_dump",
        lambda device, event, expected: canonical_bytes(raw[device.settings.decode()]),
    )

    class Device:
        frame = 0

        def force_stop(self):
            pass

        def pid(self):
            return ""

        def write_file(self, _path, payload):
            self.settings = payload

        def read_file(self, _path):
            return self.settings

        def check_cutout(self):
            pass

        def size(self):
            return (100, 60)

        def build(self):
            return "1271045"

        def screenshot(self):
            self.frame += 1
            red = 11 if case == "repeat" and self.frame == 3 else 12
            return png([((99, 59), (red, 20, 30, 255))])

        def shell(self, *_args):
            pass

    records = []
    args = (Device(), inputs, [], tmp_path, "batch", "calibration", clean, records)
    if case == "repeat":
        with pytest.raises(CaptureError, match="Repeat differs"):
            mutation_task.capture_build(*args)
    else:
        failure = mutation_task.capture_build(*args)
        if case == "unmutated":
            assert failure["verification"]["pixels"]["passed"]
            assert failure["verification"]["changed_unmutated_elements"]
        else:
            assert failure is None
            assert len(records) == 4
        assert records[0]["verification"]["pixels"]["outside"]["tolerated_pixels"] == 1
    assert not list(tmp_path.iterdir())
