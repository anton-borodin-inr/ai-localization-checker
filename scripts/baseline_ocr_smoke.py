"""Explicit offline integration check: real Tesseract on synthetic known text."""

import json
from pathlib import Path

from l10n_checker.baseline import Tesseract, normalize, parse_tsv
from l10n_checker.capture import png_size


def main():
    fixtures = Path(__file__).resolve().parents[1] / "tests/fixtures/ocr"
    expected = json.loads((fixtures / "texts.json").read_text())
    engine = Tesseract()
    for name, language in (("en", "en"), ("de", "de"), ("de-umlauts", "de")):
        image = fixtures / f"{name}.png"
        output = engine.recognize(image, language)
        words = parse_tsv(output.tsv, png_size(image.read_bytes()))
        actual = " ".join(word.text for word in words)
        if normalize(actual) != normalize(expected[name]):
            raise AssertionError(f"{name}: expected {expected[name]!r}, got {actual!r}")
        print(f"{name}: {actual!r}; {output.metadata}")


if __name__ == "__main__":
    main()
