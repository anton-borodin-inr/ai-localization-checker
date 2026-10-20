"""Algorithm boundaries/invariants; hand-computed score examples stay in golden/."""

import math

import pytest

from l10n_checker.matching import (
    Label,
    MatchingConfig,
    match_screen,
    normalize_text,
    text_similarity,
)
from l10n_checker.vision import Finding


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
