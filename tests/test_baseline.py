import json
import subprocess
from pathlib import Path

import pytest

from l10n_checker.baseline import (
    BaselineError,
    Inventory,
    OcrOutput,
    Tesseract,
    Word,
    detect,
    digest,
    normalize,
    parse_tsv,
    region,
    run_baseline,
)
from l10n_checker.unciv_text import TranslationTable

FIXTURES = Path(__file__).parent / "fixtures/ocr"
BASE = "a" * 40
HEADER = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"


def tsv(text, conf=90):
    return HEADER + "".join(
        f"5\t1\t1\t1\t1\t{i + 1}\t{40 + i * 120}\t65\t110\t45\t{conf}\t{word}\n"
        for i, word in enumerate(text.split())
    )


class FakeOcr:
    def __init__(self, text="Bergbau", failure=None, raw=None):
        self.text, self.failure, self.raw = text, failure, raw
        self.calls = 0

    def recognize(self, image, language):
        self.calls += 1
        assert image.read_bytes().startswith(b"\x89PNG")
        if self.failure:
            raise self.failure
        return OcrOutput(
            self.raw if self.raw is not None else tsv(self.text), {"engine": "fake"}
        )


def inventory(request="Mining", box=(0, 0, 1, 1)):
    return Inventory(
        schema_version=1,
        screen="tech-picker",
        base_commit=BASE,
        context="synthetic",
        slots=[
            {"id": "test", "request": request, "box": box, "source": "synthetic source"}
        ],
    )


def tables(german="Bergbau"):
    return {
        "en": TranslationTable.parse(
            "Mining = \nShared = Shared\nResearch complete = \n"
        ),
        "de": TranslationTable.parse(f"Mining = {german}\nShared = Shared\n"),
    }


def detection(
    text, expected="Bergbau", request="Mining", box=(0, 0, 1, 1), language="de", conf=90
):
    return detect(
        inventory(request, box),
        tables(expected),
        language,
        parse_tsv(tsv(text, conf), (960, 200)),
        (960, 200),
    )


def test_clean_exact_and_unicode_normalization():
    findings, diag = detection("ＢＥＲＧＢＡＵ")
    assert findings == []
    assert diag[0]["rule"] == "exact"
    assert normalize(" Straße\n Größe ") == "strasse grösse"


@pytest.mark.parametrize(
    "text", ["Bergbau und Erzgew...", "Bergbau und Erzgew…", "Bergbau und Erzgew"]
)
def test_prefix_with_or_without_marker(text):
    findings, diag = detection(text, "Bergbau und Erzgewinnung")
    assert findings[0].defect_type == "truncated_text"
    assert findings[0].text_seen == text
    assert findings[0].confidence == pytest.approx(0.9)
    assert diag[0]["rule"] == "prefix"


@pytest.mark.parametrize("text", ["Ber", "Berg"])
def test_short_prefix_is_not_invented_as_observed_text(text):
    findings, diag = detection(text, "Bergbau und Erzgewinnung")
    assert diag[0]["rule"] == "missing"
    # The OCR fragment is not used; the candidate names the expected string.
    assert findings[0].text_seen == "Bergbau und Erzgewinnung" != text
    assert findings[0].confidence == 0.5


def test_missing_expected_carries_expected_text_and_slot_region():
    findings, diag = detection("unrelated", box=(0.7, 0.7, 1, 1))
    assert findings[0].text_seen == diag[0]["expected"] == "Bergbau"
    assert findings[0].region == "bottom-right"
    assert findings[0].confidence == 0.5


@pytest.mark.parametrize(("language", "text"), [("de", "Mining"), ("en", "Bergbau")])
def test_known_other_language(language, text):
    findings, _ = detection(text, language=language)
    assert [f.defect_type for f in findings] == ["wrong_language"]


def test_shared_word_is_not_wrong_language():
    assert detection("Shared", request="Shared")[0] == []


def test_missing_translation_source_fallback_is_wrong_language():
    # A natural-language source string; raw identifiers are `other` (D-046),
    # which this rule cannot tell apart (docs/baseline.md).
    findings, diag = detection("Research complete", request="Research complete")
    assert findings[0].defect_type == "wrong_language"
    assert diag[0]["rule"] == "source_fallback"


def test_literal_broken_placeholder_is_other():
    findings, diag = detection("[amount]")
    assert findings[0].defect_type == "other"
    assert diag[0]["rule"] == "literal_placeholder"


def test_unknown_ocr_does_not_establish_another_language():
    assert detection("gibberish")[0][0].defect_type == "truncated_text"


def test_zero_confidence_text_is_not_filtered():
    assert detection("Bergbau", conf=0)[0] == []


def test_scroll_edge_candidate_is_not_suppressed():
    inv = inventory(box=(0, 0, 1, 0.1))
    word = Word("Bergbau...", 0, 0, 110, 10, 0.8, (1, 1, 1, 1))
    findings, _ = detect(
        inv, tables("Bergbau und Erzgewinnung"), "de", [word], (960, 200)
    )
    assert findings[0].defect_type == "truncated_text"


def test_full_text_elsewhere_does_not_suppress_ellipsis():
    inv = inventory(box=(0, 0, 1, 0.5))
    words = [
        Word("Bergbau...", 40, 10, 110, 20, 0.8, (1, 1, 1, 1)),
        Word("Bergbau und Erzgewinnung", 40, 150, 600, 20, 0.9, (1, 2, 1, 1)),
    ]
    findings, _ = detect(
        inv, tables("Bergbau und Erzgewinnung"), "de", words, (960, 200)
    )
    assert len(findings) == 1


def test_region_uses_box_centre_not_start():
    assert region((600, 400, 1000, 500), (2400, 1080)) == "center"
    assert region((0, 0, 100, 100), (2400, 1080)) == "top-left"


@pytest.mark.parametrize(
    "raw",
    [
        "",
        HEADER,
        "wrong\theader\n",
        tsv("Bergbau", "nan"),
        tsv("Bergbau", -1),
        tsv("Bergbau").replace("\t65\t", "\t-65\t"),
        tsv("Bergbau").replace("\t45\t", "\t9000\t"),
        HEADER + "5\t1\n",
    ],
)
def test_invalid_and_empty_ocr_are_errors(raw):
    with pytest.raises((BaselineError, ValueError)):
        parse_tsv(raw, (960, 200))


@pytest.fixture
def inputs(tmp_path):
    fork = tmp_path / "fork"
    fork.mkdir()

    def git(*args):
        return subprocess.run(
            ["git", "-C", str(fork), *args], check=True, capture_output=True, text=True
        ).stdout.strip()

    git("init", "-q")
    directory = fork / "android/assets/jsons/translations"
    directory.mkdir(parents=True)
    config = fork / "buildSrc/src/main/kotlin/BuildConfig.kt"
    config.parent.mkdir(parents=True)
    (directory / "English.properties").write_text("Mining = \n")
    (directory / "German.properties").write_text("Mining = Bergbau\n")
    config.write_text("val appCodeNumber = 101\n")

    def commit():
        git("add", ".")
        git(
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-qm",
            "test fixture",
        )
        return git("rev-parse", "HEAD")

    clean = commit()
    config.write_text("val appCodeNumber = 102\n")
    (directory / "German.properties").write_text("Mining = Bergbau und Erzgewinnung\n")
    injected = commit()
    # Dirty working-tree values must never become expectations.
    (directory / "German.properties").write_text("Mining = WRONG WORKING TREE\n")
    manifest = {
        "base_commit": BASE,
        "builds": {
            "clean": {
                "kind": "clean",
                "version_code": 101,
                "base_commit": BASE,
                "fork_commit": clean,
            },
            "defective": {
                "kind": "defective",
                "version_code": 102,
                "base_commit": BASE,
                "fork_commit": injected,
            },
        },
        "captures": [],
        "human_label_validation": "POISON: never use this",
    }
    images = {}
    for lang, variant, code, fixture in [
        ("de", "clean", 101, "de"),
        ("de", "injected", 102, "de-prefix"),
        ("en", "clean", 101, "en"),
    ]:
        image = tmp_path / f"tech-picker__{lang}__960x200__{variant}__{code}.png"
        content = (FIXTURES / f"{fixture}.png").read_bytes()
        image.write_bytes(content)
        images[(lang, variant)] = image
        manifest["captures"].append(
            {
                "file": image.name,
                "sha256": digest(content),
                "png_size": [960, 200],
                "version_code": code,
                "variant": variant,
                "language": {"en": "English", "de": "German"}[lang],
                "human_label_file": "DO NOT OPEN.labels.json",
                "visual_observation": "POISON",
            }
        )
        image.with_suffix(".labels.json").write_text(
            "INVALID LABEL JSON - must never be opened"
        )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest))
    inventory_path = tmp_path / "inventory.json"
    inventory_path.write_text(inventory().model_dump_json())
    return images, manifest_path, inventory_path, fork, tmp_path / "runs"


def run(inputs, lang="de", variant="clean", engine=None):
    images, manifest, inv, fork, runs = inputs
    return run_baseline(
        images[(lang, variant)], manifest, inv, fork, runs, engine or FakeOcr()
    )


def test_build_specific_expectations_and_unmodified_schema(inputs):
    clean, _ = run(inputs)
    injected, directory = run(
        inputs, variant="injected", engine=FakeOcr("Bergbau und Erzgew...")
    )
    english, _ = run(inputs, lang="en", engine=FakeOcr("Mining"))
    assert clean.status == english.status == injected.status == "checked"
    assert clean.findings == english.findings == []
    assert injected.findings[0].text_seen == "Bergbau und Erzgew..."
    assert set(injected.model_dump()) == {"status", "findings", "reason", "metadata"}
    diag = json.loads((directory / "diagnostics.json").read_text())
    assert diag[0]["expected"] == "Bergbau und Erzgewinnung"
    assert clean.metadata["fork_commit"] != injected.metadata["fork_commit"]
    assert injected.metadata["requests_sent"] == 0
    assert (directory / "source-entries.json").is_file()
    assert (directory / "ocr.tsv").is_file()


def test_run_output_marks_missing_rule_findings(inputs):
    found, found_dir = run(
        inputs, variant="injected", engine=FakeOcr("Bergbau und Erzgew...")
    )
    missing, missing_dir = run(inputs, variant="injected", engine=FakeOcr("unrelated"))
    assert found.findings and found.metadata["missing_rule_findings"] == []
    assert [f.text_seen for f in missing.findings] == ["Bergbau und Erzgewinnung"]
    assert missing.metadata["missing_rule_findings"] == [0]
    for result, directory in ((found, found_dir), (missing, missing_dir)):
        run_json = json.loads((directory / "run.json").read_text())
        result_json = json.loads((directory / "result.json").read_text())
        expected = result.metadata["missing_rule_findings"]
        assert run_json["missing_rule_findings"] == expected
        assert result_json["metadata"]["missing_rule_findings"] == expected
        assert run_json["settings"]["version"] == "baseline-v0.1"
        assert run_json["schema_version"] == 2


def test_labels_and_secrets_are_never_opened(inputs, monkeypatch):
    original = Path.open

    def guard(path, *args, **kwargs):
        assert not path.name.endswith(".labels.json")
        assert path.name != ".env"
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guard)
    monkeypatch.setattr(
        Path, "glob", lambda *args: pytest.fail("no directory discovery")
    )
    result, _ = run(inputs)
    assert result.status == "checked"
    images, manifest, _, fork, runs = inputs
    result, _ = run_baseline(
        images[("de", "clean")],
        manifest,
        Path("forbidden.labels.json"),
        fork,
        runs,
        FakeOcr(),
    )
    assert result.status == "not_checked"


@pytest.mark.parametrize(
    "mutation", ["hash", "version", "duplicate", "language", "source-code", "screen"]
)
def test_bad_provenance_fails_before_ocr(inputs, mutation):
    _, manifest_path, inv_path, _, _ = inputs
    manifest = json.loads(manifest_path.read_text())
    if mutation == "hash":
        manifest["captures"][0]["sha256"] = "bad"
    elif mutation == "version":
        manifest["captures"][0]["version_code"] = 999
    elif mutation == "duplicate":
        manifest["captures"].append(manifest["captures"][0])
    elif mutation == "language":
        manifest["captures"][0]["language"] = "English"
    elif mutation == "source-code":
        manifest["builds"]["clean"]["fork_commit"] = manifest["builds"]["defective"][
            "fork_commit"
        ]
    else:
        inv = json.loads(inv_path.read_text())
        inv["screen"] = "other"
        inv_path.write_text(json.dumps(inv))
    manifest_path.write_text(json.dumps(manifest))
    engine = FakeOcr()
    result, _ = run(inputs, engine=engine)
    assert result.status == "not_checked"
    assert result.reason
    assert result.findings == []
    assert engine.calls == 0


@pytest.mark.parametrize(
    "failure",
    [
        FileNotFoundError("missing OCR"),
        BaselineError("missing deu"),
        subprocess.TimeoutExpired("tesseract", 30),
        subprocess.CalledProcessError(1, "tesseract"),
    ],
)
def test_ocr_failures_are_recorded_not_checked(inputs, failure):
    result, directory = run(inputs, engine=FakeOcr(failure=failure))
    assert result.status == "not_checked"
    assert result.findings == [] and result.reason
    assert (
        json.loads((directory / "result.json").read_text())["status"] == "not_checked"
    )


def test_empty_ocr_is_not_a_clean_result_and_raw_is_kept(inputs):
    result, directory = run(inputs, engine=FakeOcr(raw=HEADER))
    assert result.status == "not_checked"
    assert (directory / "ocr.tsv").read_text() == HEADER


def test_unsupported_required_template_is_not_checked(inputs):
    _, _, inv_path, _, _ = inputs
    inv_path.write_text(inventory("Mining <when [enabled]>").model_dump_json())
    result, _ = run(inputs)
    assert result.status == "not_checked"
    assert "unsupported" in result.reason


def test_tesseract_missing_binary(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _: None)
    with pytest.raises(BaselineError, match="executable is missing"):
        Tesseract().recognize(FIXTURES / "de.png", "de")


def test_tesseract_checks_language_data_and_uses_fixed_settings(tmp_path, monkeypatch):
    (tmp_path / "eng.traineddata").write_bytes(b"eng model")
    (tmp_path / "deu.traineddata").write_bytes(b"deu model")
    calls = []

    def fake(args, **kwargs):
        calls.append(args)
        assert kwargs["timeout"] == 30 and kwargs["check"]
        if args[1] == "--version":
            output = "tesseract fake\n"
        elif args[1] == "--list-langs":
            output = f'List of available languages in "{tmp_path}" (2):\neng\ndeu\n'
        else:
            output = tsv("Bergbau")
        return subprocess.CompletedProcess(args, 0, output, "")

    monkeypatch.setattr("shutil.which", lambda _: "/fake/tesseract")
    monkeypatch.setattr(subprocess, "run", fake)
    output = Tesseract().recognize(FIXTURES / "de.png", "de")
    assert calls[-1][-7:] == ["--oem", "1", "--psm", "11", "-l", "deu+eng", "tsv"]
    assert output.metadata["traineddata_sha256"]["deu"] == digest(b"deu model")
    (tmp_path / "deu.traineddata").unlink()
    with pytest.raises(FileNotFoundError):
        Tesseract().recognize(FIXTURES / "de.png", "de")
