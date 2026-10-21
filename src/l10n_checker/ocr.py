"""Selectable offline OCR stage; no translation, matching or metric rules."""

import csv
import hashlib
import io
import json
import math
import multiprocessing
import tempfile
import time
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from PIL import Image

from l10n_checker.baseline import (
    BaselineError,
    OcrOutput,
    Tesseract,
    Word,
    parse_tsv,
)

ENGINES = ("tesseract", "easyocr")
PREPROCESSING = ("none", "upscale2x", "upscale2x-otsu")
LANGUAGES = {"en": ["en"], "de": ["de", "en"]}
MODEL_FILES = ("craft_mlt_25k.pth", "english_g2.pth", "latin_g2.pth")
EASY_PARAMS = {
    "decoder": "greedy",
    "beamWidth": 5,
    "batch_size": 1,
    "workers": 0,
    "allowlist": None,
    "blocklist": None,
    "detail": 1,
    "rotation_info": None,
    "paragraph": False,
    "min_size": 20,
    "contrast_ths": 0.1,
    "adjust_contrast": 0.5,
    "filter_ths": 0.003,
    "text_threshold": 0.7,
    "low_text": 0.4,
    "link_threshold": 0.4,
    "canvas_size": 4800,
    "mag_ratio": 1.0,
    "slope_ths": 0.1,
    "ycenter_ths": 0.5,
    "height_ths": 0.5,
    "width_ths": 0.5,
    "y_ths": 0.5,
    "x_ths": 1.0,
    "add_margin": 0.1,
    "threshold": 0.2,
    "bbox_min_score": 0.2,
    "bbox_min_size": 3,
    "max_candidates": 0,
    "output_format": "standard",
}
HEADER = (
    "level",
    "page_num",
    "block_num",
    "par_num",
    "line_num",
    "word_num",
    "left",
    "top",
    "width",
    "height",
    "conf",
    "text",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def otsu_threshold(histogram: list[int]) -> int:
    """Smallest maximizer; integer cross-products avoid floating tie drift."""
    total = sum(histogram)
    weighted = sum(i * count for i, count in enumerate(histogram))
    count_left = sum_left = 0
    best_num, best_den, best = -1, 1, 0
    for threshold, count in enumerate(histogram):
        count_left += count
        sum_left += threshold * count
        count_right = total - count_left
        if not count_left or not count_right:
            continue
        numerator = (sum_left * total - weighted * count_left) ** 2
        denominator = count_left * count_right
        if numerator * best_den > best_num * denominator:
            best_num, best_den, best = numerator, denominator, threshold
    return best


def preprocess(image: Path, variant: str, target: Path) -> dict:
    if variant not in PREPROCESSING or variant == "none":
        raise BaselineError("A transformed preprocessing variant is required")
    with Image.open(image) as source:
        source_size = source.size
        prepared = source.convert("RGB").resize(
            (source.width * 2, source.height * 2), Image.Resampling.LANCZOS
        )
    threshold = None
    if variant == "upscale2x-otsu":
        prepared = prepared.convert("L")
        threshold = otsu_threshold(prepared.histogram())
        prepared = prepared.point([255 if i > threshold else 0 for i in range(256)])
    prepared.save(target, format="PNG")
    return {
        "variant": variant,
        "scale": 2,
        "source_size": list(source_size),
        "source_sha256": sha256(image),
        "prepared_sha256": sha256(target),
        "otsu_threshold": threshold,
    }


def word_tsv(words: list[Word]) -> str:
    output = io.StringIO()
    writer = csv.writer(output, delimiter="\t", lineterminator="\n")
    writer.writerow(HEADER)
    for index, word in enumerate(words, 1):
        if any(c in word.text for c in "\t\r\n"):
            raise BaselineError("OCR segment contains a TSV control character")
        writer.writerow(
            [
                5,
                *word.line,
                index,
                word.left,
                word.top,
                word.width,
                word.height,
                word.confidence * 100,
                word.text,
            ]
        )
    return output.getvalue()


def mapped_box(box, scale, size):
    if len(box) != 4 or not all(math.isfinite(float(v)) for v in box):
        raise BaselineError("Invalid OCR box")
    left, top = math.floor(box[0] / scale), math.floor(box[1] / scale)
    right, bottom = math.ceil(box[2] / scale), math.ceil(box[3] / scale)
    left, top = max(0, left), max(0, top)
    right, bottom = min(size[0], right), min(size[1], bottom)
    if right <= left or bottom <= top:
        raise BaselineError("Empty OCR box after coordinate conversion")
    return left, top, right - left, bottom - top


def segment_words(segments, size):
    words = []
    for index, (points, text, confidence) in enumerate(segments, 1):
        if not isinstance(text, str) or not text.strip():
            raise BaselineError("Empty EasyOCR segment")
        if len(points) != 4 or any(len(point) != 2 for point in points):
            raise BaselineError("Invalid EasyOCR polygon")
        if not all(math.isfinite(float(v)) for point in points for v in point):
            raise BaselineError("Non-finite EasyOCR polygon")
        confidence = float(confidence)
        if not math.isfinite(confidence) or not 0 <= confidence <= 1:
            raise BaselineError("Invalid EasyOCR confidence")
        xs, ys = zip(*points, strict=True)
        box = (min(xs), min(ys), max(xs), max(ys))
        words.append(
            Word(text, *mapped_box(box, 1, size), confidence, (1, index, 1, 1))
        )
    return words


def _easy_worker(connection, model_dir, language):
    """Isolate model crashes and enforce a parent-controlled timeout."""
    try:
        started = time.monotonic()
        import easyocr
        import torch

        torch.set_num_threads(1)
        reader = easyocr.Reader(
            LANGUAGES[language],
            gpu=False,
            detect_network="craft",
            recog_network="standard",
            quantize=True,
            cudnn_benchmark=False,
            model_storage_directory=model_dir,
            user_network_directory=str(Path(model_dir) / "user-network"),
            download_enabled=False,
            verbose=False,
        )
        connection.send(("ready", time.monotonic() - started))
        while (path := connection.recv()) is not None:
            result = reader.readtext(path, **EASY_PARAMS)
            native = [
                ([[float(x), float(y)] for x, y in points], text, float(confidence))
                for points, text, confidence in result
            ]
            connection.send(("result", native))
    except Exception as exc:  # noqa: BLE001 -- serialize failures at the process boundary
        connection.send(("error", f"{type(exc).__name__}: {exc}"))
    finally:
        connection.close()


class EasyOCR:
    def __init__(self, model_dir=Path("data/ocr-models"), timeout_s=300):
        self.model_dir = Path(model_dir).resolve()
        self.timeout_s = timeout_s
        self.sessions = {}

    def _receive(self, process, connection):
        try:
            if not connection.poll(self.timeout_s):
                raise BaselineError(f"EasyOCR timeout after {self.timeout_s} seconds")
            kind, value = connection.recv()
            if kind == "error":
                raise BaselineError(f"EasyOCR failed: {value}")
            return kind, value
        except (EOFError, OSError) as exc:
            raise BaselineError(f"EasyOCR worker exited ({process.exitcode})") from exc

    def recognize(self, image: Path, language: str) -> OcrOutput:
        if language not in LANGUAGES:
            raise BaselineError("Unsupported OCR language")
        try:
            installed = version("easyocr")
        except PackageNotFoundError as exc:
            raise BaselineError("EasyOCR is not installed") from exc
        if installed != "1.7.2":
            raise BaselineError("This OCR configuration requires EasyOCR 1.7.2")
        manifest = json.loads((self.model_dir / "models.json").read_text())
        files = (MODEL_FILES[0], MODEL_FILES[1 if language == "en" else 2])
        hashes = {name: sha256(self.model_dir / name) for name in files}
        if any(manifest["sha256"].get(name) != value for name, value in hashes.items()):
            raise BaselineError("EasyOCR model SHA-256 mismatch")
        initialization_s = 0.0
        try:
            if language not in self.sessions:
                context = multiprocessing.get_context("spawn")
                connection, child = context.Pipe()
                process = context.Process(
                    target=_easy_worker,
                    args=(child, str(self.model_dir), language),
                    daemon=True,
                )
                process.start()
                child.close()
                self.sessions[language] = process, connection
                kind, initialization_s = self._receive(process, connection)
                if kind != "ready":
                    raise BaselineError("Invalid EasyOCR worker initialization")
            process, connection = self.sessions[language]
            connection.send(str(image.resolve()))
            kind, segments = self._receive(process, connection)
            if kind != "result":
                raise BaselineError("Invalid EasyOCR worker response")
            with Image.open(image) as source:
                words = segment_words(segments, source.size)
            return OcrOutput(
                word_tsv(words),
                {
                    "engine": "easyocr 1.7.2",
                    "languages": LANGUAGES[language],
                    "models_sha256": hashes,
                    "parameters": EASY_PARAMS,
                    "device": "cpu",
                    "torch_threads": 1,
                    "initialization_s": initialization_s,
                    "native_segments": segments,
                },
            )
        except (BaselineError, BrokenPipeError):
            self.close()
            raise

    def close(self):
        for process, connection in self.sessions.values():
            if process.is_alive():
                try:
                    connection.send(None)
                except (BrokenPipeError, OSError):
                    pass
                process.join(timeout=2)
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=2)
            connection.close()
        self.sessions.clear()


class ConfiguredOcr:
    def __init__(self, engine, preprocessing="none", model_dir=Path("data/ocr-models")):
        if engine not in ENGINES or preprocessing not in PREPROCESSING:
            raise BaselineError("Unknown OCR configuration")
        self.backend = Tesseract() if engine == "tesseract" else EasyOCR(model_dir)
        self.preprocessing = preprocessing

    def recognize(self, image: Path, language: str) -> OcrOutput:
        if self.preprocessing == "none":
            return self.backend.recognize(image, language)
        with tempfile.TemporaryDirectory(prefix="l10n-ocr-") as directory:
            target = Path(directory) / image.name
            metadata = preprocess(image, self.preprocessing, target)
            output = self.backend.recognize(target, language)
        size = tuple(metadata["source_size"])
        native_words = parse_tsv(output.tsv, (size[0] * 2, size[1] * 2))
        words = [
            Word(w.text, *mapped_box(w.box, 2, size), w.confidence, w.line)
            for w in native_words
        ]
        return OcrOutput(
            word_tsv(words),
            {
                **output.metadata,
                "preprocessing": metadata,
                "native_tsv": output.tsv,
            },
        )

    def close(self):
        if isinstance(self.backend, EasyOCR):
            self.backend.close()


def readings(tsv: str, size: tuple[int, int]) -> list[dict]:
    """D-033 adapter: native lines/segments only, never screen-wide joining."""
    lines = {}
    for word in parse_tsv(tsv, size):
        lines.setdefault(word.line, []).append(word)
    result = []
    from l10n_checker.baseline import region, union

    for words in lines.values():
        box = union(words)
        result.append(
            {
                "text_seen": " ".join(w.text for w in words),
                "region": region(box, size),
                "box": [0, 0, *size],
                "text_box": list(box),
            }
        )
    return result
