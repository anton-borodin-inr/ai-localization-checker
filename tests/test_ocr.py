import json
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image
from test_baseline import tsv

from l10n_checker import baseline_cli, ocr
from l10n_checker.baseline import BaselineError, OcrOutput, parse_tsv
from l10n_checker.vision import CheckResult

ROOT = Path(__file__).resolve().parents[1]


def test_parameters_equal_pre_registered_grid():
    protocol = json.loads((ROOT / "docs/evidence/48/protocol.json").read_text())
    assert len(protocol["grid"]) == 6
    assert {(r["engine"], r["preprocess"]) for r in protocol["grid"]} == {
        (engine, variant) for engine in ocr.ENGINES for variant in ocr.PREPROCESSING
    }
    assert protocol["easyocr"]["readtext"] == ocr.EASY_PARAMS
    assert protocol["languages"]["easyocr"] == ocr.LANGUAGES


@pytest.mark.parametrize("engine", ocr.ENGINES)
@pytest.mark.parametrize("variant", ocr.PREPROCESSING)
def test_selection_is_explicit_and_lazy(engine, variant):
    selected = ocr.ConfiguredOcr(engine, variant)
    assert selected.preprocessing == variant
    assert isinstance(
        selected.backend, ocr.Tesseract if engine == "tesseract" else ocr.EasyOCR
    )
    selected.close()


def test_unknown_configuration_is_rejected():
    with pytest.raises(BaselineError):
        ocr.ConfiguredOcr("unknown", "none")
    with pytest.raises(BaselineError):
        ocr.ConfiguredOcr("tesseract", "extra-variant")


@pytest.mark.parametrize("variant", ocr.PREPROCESSING[1:])
def test_preprocessing_has_repeatable_bytes_and_keeps_input(tmp_path, variant):
    source = tmp_path / "input.png"
    image = Image.new("RGB", (5, 3))
    image.putdata([(i * 17, i * 10, i * 7) for i in range(15)])
    image.save(source)
    before = source.read_bytes()
    first, second = tmp_path / "a.png", tmp_path / "b.png"
    a = ocr.preprocess(source, variant, first)
    b = ocr.preprocess(source, variant, second)
    assert a == b
    assert first.read_bytes() == second.read_bytes()
    assert source.read_bytes() == before
    with Image.open(first) as actual:
        assert actual.size == (10, 6)
        if variant.endswith("otsu"):
            assert set(actual.tobytes()) <= {0, 255}


def test_otsu_uses_smallest_maximizer():
    histogram = [0] * 256
    histogram[0] = histogram[255] = 10
    assert ocr.otsu_threshold(histogram) == 0


def test_upscale_maps_boxes_with_outward_rounding(tmp_path):
    image = tmp_path / "input.png"
    Image.new("RGB", (960, 200)).save(image)
    native = tsv("Mining").replace("40\t65\t110\t45", "81\t131\t219\t89")

    class Fake:
        def recognize(self, path, language):
            with Image.open(path) as prepared:
                assert prepared.size == (1920, 400)
            return OcrOutput(native, {"engine": "fake"})

    selected = ocr.ConfiguredOcr("tesseract", "upscale2x")
    selected.backend = Fake()
    output = selected.recognize(image, "en")
    word = parse_tsv(output.tsv, (960, 200))[0]
    assert word.box == (40, 65, 150, 110)
    assert word.text == "Mining"
    assert output.metadata["native_tsv"] == native


def test_easyocr_keeps_native_segment_and_zero_confidence():
    words = ocr.segment_words(
        [([[10.2, 4], [80.1, 4], [80.1, 20], [10.2, 20]], "two words", 0)], (100, 50)
    )
    assert len(words) == 1
    assert words[0].text == "two words"
    assert words[0].box == (10, 4, 81, 20)
    assert parse_tsv(ocr.word_tsv(words), (100, 50)) == words


@pytest.mark.parametrize("confidence", [float("nan"), -0.1, 1.1])
def test_invalid_easyocr_confidence_fails(confidence):
    with pytest.raises(BaselineError):
        ocr.segment_words(
            [([[0, 0], [10, 0], [10, 10], [0, 10]], "x", confidence)], (20, 20)
        )


def test_readings_use_full_image_frame_for_global_regions():
    result = ocr.readings(tsv("two words"), (960, 200))
    assert result == [
        {
            "text_seen": "two words",
            "region": "left",
            "box": [0, 0, 960, 200],
            "text_box": [40, 65, 270, 110],
        }
    ]


def test_worker_timeout_is_a_baseline_failure():
    class Connection:
        def poll(self, timeout):
            assert timeout == 0.01
            return False

    with pytest.raises(BaselineError, match="timeout"):
        ocr.EasyOCR(timeout_s=0.01)._receive(None, Connection())


def test_default_import_does_not_load_torch_or_easyocr():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; sys.path.insert(0, 'src'); import l10n_checker.baseline_cli; "
                "assert 'torch' not in sys.modules; assert 'easyocr' not in sys.modules"
            ),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_cli_forwards_explicit_configuration_and_closes(monkeypatch):
    selected = []

    class Fake:
        def __init__(self, *args):
            selected.append(args)

        def close(self):
            selected.append("closed")

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "l10n-baseline",
            "--image",
            "a.png",
            "--manifest",
            "m.json",
            "--inventory",
            "i.json",
            "--unciv-fork",
            "fork",
            "--ocr-engine",
            "easyocr",
            "--ocr-preprocess",
            "upscale2x",
        ],
    )
    monkeypatch.setattr(baseline_cli, "ConfiguredOcr", Fake)
    monkeypatch.setattr(baseline_cli, "output_directory", lambda path: path)

    def run(*args):
        assert isinstance(args[-1], Fake)
        return CheckResult(
            status="checked", findings=[], reason=None, metadata={}
        ), Path("run")

    monkeypatch.setattr(baseline_cli, "run_baseline", run)
    assert baseline_cli.main() == 0
    assert selected == [("easyocr", "upscale2x", Path("data/ocr-models")), "closed"]
