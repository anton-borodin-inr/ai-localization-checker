import json
import shutil
from pathlib import Path

import pytest

from l10n_checker import ocr, ocr_experiment
from l10n_checker.baseline import BaselineError

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def copied_inputs(tmp_path):
    protocol = json.loads((ROOT / ocr_experiment.PROTOCOL).read_text())
    files = [ocr_experiment.PROTOCOL, *protocol["protected_sha256"]]
    files += [row["path"] for row in protocol["images"]]
    for name in files:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    return tmp_path


def test_exactly_seven_named_dev_images_are_validated(copied_inputs):
    protocol = ocr_experiment.validated_protocol(copied_inputs)
    assert len(protocol["images"]) == 7
    assert sum(r["scope"] == "labelled" for r in protocol["images"]) == 3
    assert {r["screen"] for r in protocol["images"]} == {
        "tech-picker",
        "city-production",
    }
    assert len(protocol["grid"]) * len(protocol["images"]) * 2 == 84


def test_additional_image_or_configuration_requires_new_protocol(copied_inputs):
    path = copied_inputs / ocr_experiment.PROTOCOL
    protocol = json.loads(path.read_text())
    protocol["grid"].append({"id": "extra"})
    path.write_text(json.dumps(protocol))
    with pytest.raises(ValueError, match="pre-registered protocol"):
        ocr_experiment.validated_protocol(copied_inputs)


def test_modified_image_stops_before_engine_creation(copied_inputs, monkeypatch):
    protocol = json.loads((copied_inputs / ocr_experiment.PROTOCOL).read_text())
    image = copied_inputs / protocol["images"][0]["path"]
    image.write_bytes(b"changed")
    monkeypatch.setattr(
        ocr_experiment, "ConfiguredOcr", lambda *_: pytest.fail("OCR must not start")
    )
    with pytest.raises(ValueError, match="Image SHA-256"):
        ocr_experiment.run_experiment(copied_inputs, Path("unused"), Path("unused"))


def test_changed_reference_is_rejected(copied_inputs):
    path = copied_inputs / ocr_experiment.REFERENCE_SOURCE
    path.write_text("{}")
    with pytest.raises(ValueError, match="Protected input/code"):
        ocr_experiment.validated_protocol(copied_inputs)


def test_model_hash_mismatch_stops_before_process_creation(tmp_path, monkeypatch):
    for name in (ocr.MODEL_FILES[0], ocr.MODEL_FILES[1]):
        (tmp_path / name).write_bytes(b"not the frozen weights")
    (tmp_path / "models.json").write_text(json.dumps({"sha256": {}}))
    monkeypatch.setattr(ocr, "version", lambda _: "1.7.2")
    monkeypatch.setattr(
        ocr.multiprocessing,
        "get_context",
        lambda *_: pytest.fail("worker must not start"),
    )
    with pytest.raises(BaselineError, match="SHA-256 mismatch"):
        ocr.EasyOCR(tmp_path).recognize(Path("unused.png"), "en")


def test_timing_survives_an_engine_failure():
    class Broken:
        def recognize(self, *_):
            raise BaselineError("failed")

    engine = ocr_experiment.TimedEngine(Broken())
    with pytest.raises(BaselineError, match="failed"):
        engine.recognize(Path("unused.png"), "de")
    assert engine.output is None
    assert engine.seconds >= 0
