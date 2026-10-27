"""Algorithm boundaries/invariants; hand-computed score examples stay in golden/."""

import json
import math
from pathlib import Path
from time import perf_counter

import pytest
from pydantic import ValidationError

from l10n_checker.matching import (
    Label,
    LabelV1,
    MatchingConfig,
    load_labels,
    match_screen,
    normalize_text,
    text_similarity,
)
from l10n_checker.metrics import score_screen, score_screens
from l10n_checker.vision import Finding, FindingV1


def label(text="Alpha beta gamma...", region="center", **overrides):
    return Label(
        **{
            "defect_type": "truncated_text",
            "text_expected": "Alpha beta gamma delta",
            "text_seen": text,
            "region": region,
        }
        | overrides
    )


def finding(text="Alpha beta gamma...", region="center", **overrides):
    return Finding(
        **{
            "defect_type": "truncated_text",
            "text_seen": text,
            "region": region,
            "confidence": 0.9,
        }
        | overrides
    )


@pytest.mark.parametrize("field", ["text_threshold", "prefix_min_coverage"])
@pytest.mark.parametrize("value", [0, -1, 1.01, math.nan, math.inf])
def test_invalid_thresholds_are_rejected(field, value):
    with pytest.raises(ValueError):
        MatchingConfig(**{field: value})


@pytest.mark.parametrize("words", [0, 1, 2.5])
def test_prefix_cannot_be_configured_as_one_word(words):
    with pytest.raises(ValueError):
        MatchingConfig(prefix_min_words=words)


def test_normalization_preserves_meaningful_characters():
    assert normalize_text(" \tGru\u0308ne\n Straße… ") == "Grüne Straße..."
    assert normalize_text("Straße") != normalize_text("strasse")


@pytest.mark.parametrize("first,second", [("", ""), ("   ", "abc"), ("abc", "")])
def test_empty_text_never_identifies_a_label(first, second):
    assert not match_screen([label(second)], [finding(first)], [second]).matches


def test_threshold_boundary_is_inclusive_and_configurable():
    expected, observed = "abcdefghij", "abcdefghiX"
    score = text_similarity(expected, observed)
    inputs = ([label(expected)], [finding(observed)], [expected])
    assert match_screen(*inputs, config=MatchingConfig(text_threshold=score)).matches
    assert not match_screen(
        *inputs, config=MatchingConfig(text_threshold=math.nextafter(score, 1))
    ).matches
    assert text_similarity(expected, observed) == text_similarity(observed, expected)


def test_prefix_requires_marker_words_and_coverage():
    expected = "Alpha beta gamma..."
    inputs = ([label(expected)], [finding("Alpha beta...")], [expected])
    coverage = len("Alpha beta") / len("Alpha beta gamma")
    assert match_screen(
        *inputs, config=MatchingConfig(text_threshold=1, prefix_min_coverage=coverage)
    ).matches
    assert not match_screen(
        *inputs,
        config=MatchingConfig(
            text_threshold=1, prefix_min_coverage=math.nextafter(coverage, 1)
        ),
    ).matches
    for text in ("Alpha beta", "Alpha..."):
        assert not match_screen(
            [label(expected)],
            [finding(text)],
            [expected],
            config=MatchingConfig(text_threshold=1),
        ).matches


def test_identical_clean_occurrence_also_requires_region():
    text = "Alpha beta gamma..."
    result = match_screen([label(text)], [finding(text, "right")], [text, text])
    assert not result.matches
    assert result.unmatched_finding_indices
    assert not result.hallucination_indices


def test_repeated_labels_are_not_collapsed_across_regions():
    text = "Alpha beta gamma..."
    result = match_screen(
        [label(text, "center"), label(text, "right")],
        [finding(text, "right"), finding(text, "center")],
        [text, text],
    )
    assert {(p.finding_index, p.label_index) for p in result.matches} == {
        (0, 1),
        (1, 0),
    }
    assert not result.duplicate_finding_indices


def test_best_text_representative_wins_without_type_or_confidence_bias():
    result = match_screen(
        [label()],
        [finding("Alpha beta..."), finding(defect_type="other", confidence=0.1)],
        ["Alpha beta gamma..."],
    )
    assert result.matches[0].finding_index == 1
    assert result.duplicate_finding_indices == (0,)
    tied = match_screen(
        [label()],
        [finding(defect_type="other", confidence=0.1), finding()],
        ["Alpha beta gamma..."],
    )
    assert tied.matches[0].finding_index == 0


def test_literal_fragment_is_real_text_even_without_identifying_label():
    result = match_screen([label()], [finding("beta")], ["Alpha beta gamma..."])
    assert result.unmatched_finding_indices
    assert not result.hallucination_indices


def test_d027_other_labels_and_notes_are_supported():
    annotated = label("[amount]", defect_type="other", note="broken placeholder")
    result = match_screen([annotated], [finding("[amount]")], ["[amount]"])
    assert result.matches
    assert result.labels[0].note == annotated.note


@pytest.mark.parametrize(
    "status,findings", [("unknown", []), ("not_checked", [finding()])]
)
def test_inconsistent_status_is_rejected(status, findings):
    with pytest.raises(ValueError):
        match_screen([], findings, [], status=status)


def test_full_expected_text_identifies_a_truncated_label():
    result = match_screen(
        [label("Alpha beta gam...")],
        [finding("Alpha beta gamma delta")],
        ["Alpha beta gam..."],
    )
    assert [(p.finding_index, p.label_index) for p in result.matches] == [(0, 0)]
    assert not result.unmatched_finding_indices
    assert not result.hallucination_indices


def pairs(result):
    return [(p.finding_index, p.label_index) for p in result.matches]


def test_finding_goes_to_free_label_instead_of_becoming_duplicate():
    # "Neue Spiel" scores 1 - 1/11 against both labels; L0 is taken by F0.
    result = match_screen(
        [label("Neues Spiel", "top"), label("Neue Spiele", "center")],
        [finding("Neues Spiel", "top"), finding("Neue Spiel", "center")],
        ["Neues Spiel", "Neue Spiele"],
    )
    assert pairs(result) == [(0, 0), (1, 1)]
    assert not result.duplicate_finding_indices
    assert not result.unmatched_label_indices


def test_matched_label_count_beats_total_score():
    # F0 is exact for L0 (1) and near L1 (15/16); F1 is near L0 only (16/17).
    result = match_screen(
        [label("Spielstand laden"), label("Spielstand ladet")],
        [finding("Spielstand laden"), finding("Spielstand ladenn")],
        ["Spielstand laden", "Spielstand ladet"],
    )
    assert pairs(result) == [(1, 0), (0, 1)]
    assert not result.duplicate_finding_indices


def test_equal_assignments_follow_input_order():
    # Both findings score 14/15 against both labels.
    result = match_screen(
        [label("Spielstand lade"), label("Spielstand ladx")],
        [finding("Spielstand ladz"), finding("Spielstand ladz")],
        ["Spielstand lade", "Spielstand ladx"],
    )
    assert pairs(result) == [(0, 0), (1, 1)]


def test_single_letter_finding_is_a_hallucination():
    result = match_screen([label()], [finding("e")], ["Bergbau und Erzgew..."])
    assert result.unmatched_finding_indices == (0,)
    assert result.hallucination_indices == (0,)


@pytest.mark.parametrize(
    "text",
    ["Bergbau", "Bergbau und", "und Erzgew...", "Erzgew", "Optionen"],
)
def test_whole_words_of_visible_text_are_present(text):
    result = match_screen(
        [label()], [finding(text)], ["Bergbau und Erzgew...", "(Optionen):"]
    )
    assert result.unmatched_finding_indices == (0,)
    assert not result.hallucination_indices


@pytest.mark.parametrize("text", ["erg", "Bergba", "und Erz", "ptionen"])
def test_partial_words_are_not_present(text):
    result = match_screen(
        [label()], [finding(text)], ["Bergbau und Erzgew...", "(Optionen):"]
    )
    assert result.hallucination_indices == (0,)


def test_region_blocked_expected_text_is_not_a_hallucination():
    # Repeated visible text needs the same region, so the finding is unassigned,
    # but it names the label's expected text.
    text = "Alpha beta gam..."
    result = match_screen(
        [label(text, "center")],
        [finding("Alpha beta gamma delta", "right")],
        [text, text],
    )
    assert result.unmatched_finding_indices == (0,)
    assert not result.hallucination_indices


def test_twenty_five_similar_labels_finish_under_one_second():
    texts = [f"Technologie Nummer {number:02d}" for number in range(1, 26)]
    labels = [label(text, text_expected=text) for text in texts]
    findings = [finding(text) for text in texts]
    started = perf_counter()
    result = match_screen(labels, findings, texts)
    elapsed = perf_counter() - started
    assert elapsed < 1, f"match_screen took {elapsed:.6f}s (limit: 1s)"
    assert pairs(result) == [(index, index) for index in range(25)]
    assert not result.duplicate_finding_indices
    assert not result.unmatched_finding_indices
    assert not result.unmatched_label_indices
    assert not result.hallucination_indices
    print(f"25 similar labels / 25 findings: match_screen took {elapsed:.6f}s")


ISSUE_14_LABELS = (
    Path(__file__).resolve().parents[1]
    / "docs/evidence/14/records/inputs"
    / "tech-picker__de__2400x1080__injected__1271002.labels.json"
)


def test_committed_v1_label_file_loads_as_v1():
    version, labels = load_labels(json.loads(ISSUE_14_LABELS.read_text("utf-8")))
    assert version == 1
    assert [type(item) for item in labels] == [LabelV1]
    assert labels[0].defect_type == "truncated_text"


@pytest.mark.parametrize(
    ("version", "defect_type", "accepted"),
    [
        (1, "untranslated", True),
        (1, "overflow", False),
        (2, "wrong_language", True),
        (2, "untranslated", False),
    ],
)
def test_label_file_classes_follow_its_schema_version(version, defect_type, accepted):
    row = {
        "defect_type": defect_type,
        "text_expected": "Neues Spiel",
        "text_seen": "New Game",
        "region": "top",
    }
    label_file = {"schema_version": version, "labels": [row]}
    if accepted:
        assert load_labels(label_file)[0] == version
    else:
        with pytest.raises(ValidationError):
            load_labels(label_file)


@pytest.mark.parametrize("version", [0, 3, "2", True])
def test_unknown_label_schema_version_is_rejected(version):
    with pytest.raises(ValueError):
        load_labels({"schema_version": version, "labels": []})


def test_objects_must_match_the_declared_schema_versions():
    v1_label = LabelV1(**label().model_dump())
    v1_finding = FindingV1(**finding().model_dump())
    texts = ["Alpha beta gamma..."]
    with pytest.raises(ValueError, match="label"):
        match_screen([v1_label], [], texts)
    with pytest.raises(ValueError, match="result"):
        match_screen([], [v1_finding], texts)
    with pytest.raises(ValueError, match="result"):
        match_screen([], [finding()], texts, result_schema_version=1)
    with pytest.raises(ValueError, match="label schema version"):
        match_screen([], [], texts, label_schema_version=True)


@pytest.mark.parametrize(
    ("label_version", "result_version", "reason"),
    [
        (2, 2, None),
        (1, 2, "got labels v1"),
        (2, 1, "got results v1"),
        (1, 1, "got labels v1, results v1"),
    ],
)
def test_confusion_needs_v2_labels_and_results(label_version, result_version, reason):
    labels = [(LabelV1 if label_version == 1 else Label)(**label().model_dump())]
    findings = [
        (FindingV1 if result_version == 1 else Finding)(**finding().model_dump())
    ]
    screen = match_screen(
        labels,
        findings,
        ["Alpha beta gamma..."],
        label_schema_version=label_version,
        result_schema_version=result_version,
    )
    metrics = score_screen(screen)
    assert metrics.tp == 1
    if reason is None:
        assert metrics.confusion is not None
        assert metrics.confusion_unavailable_reason is None
    else:
        assert metrics.confusion is None
        assert metrics.confusion_unavailable_reason.endswith(reason)


def test_one_v1_screen_makes_the_dataset_confusion_unavailable():
    v2 = match_screen([label()], [finding()], ["Alpha beta gamma..."])
    v1 = match_screen(
        [],
        [],
        [],
        status="not_checked",
        result_schema_version=1,
    )
    assert score_screens([v2]).confusion is not None
    assert score_screens([v2, v1]).confusion is None
