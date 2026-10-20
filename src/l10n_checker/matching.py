"""Type-free, per-screen detection matching (D-026). No provider calls or I/O."""

import math
import unicodedata
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction
from functools import cache
from typing import Literal

from pydantic import BaseModel, ConfigDict

from l10n_checker.vision import DefectType, Finding, Region

ScreenStatus = Literal["checked", "not_checked"]


class Label(BaseModel):
    """Human-owned label, including D-027 technical-text notes."""

    model_config = ConfigDict(extra="forbid")

    defect_type: DefectType
    text_expected: str
    text_seen: str
    region: Region
    note: str | None = None


@dataclass(frozen=True)
class MatchingConfig:
    """Provisional defaults; final tuning belongs to Anton after the slice."""

    text_threshold: float = 0.90
    prefix_min_coverage: float = 0.50
    prefix_min_words: int = 2

    def __post_init__(self):
        for value in (self.text_threshold, self.prefix_min_coverage):
            if not math.isfinite(value) or not 0 < value <= 1:
                raise ValueError("matching thresholds must be finite and in (0, 1]")
        if not isinstance(self.prefix_min_words, int) or self.prefix_min_words < 2:
            raise ValueError("prefix_min_words must be an integer of at least two")


DEFAULT_CONFIG = MatchingConfig()


def normalize_text(text: str) -> str:
    """Preserve case/accents/punctuation except the equivalent ellipsis glyph."""
    return " ".join(unicodedata.normalize("NFC", text).replace("…", "...").split())


def _levenshtein(first: str, second: str) -> int:
    previous = list(range(len(second) + 1))
    for row, left in enumerate(first, 1):
        current = [row]
        for column, right in enumerate(second, 1):
            current.append(
                min(
                    previous[column] + 1,
                    current[column - 1] + 1,
                    previous[column - 1] + (left != right),
                )
            )
        previous = current
    return previous[-1]


def text_similarity(first: str, second: str) -> float:
    """1 - Levenshtein distance / max length, over normalized Unicode text.

    Empty strings score zero, including against another empty string.
    """
    first, second = normalize_text(first), normalize_text(second)
    if not first or not second:
        return 0.0
    return 1 - _levenshtein(first, second) / max(len(first), len(second))


def _match_score(finding: str, label: str, config: MatchingConfig) -> Fraction | None:
    """Exact score for the assignment; thresholds use the float expressions.

    Comparing the same float values as text_similarity keeps the inclusive
    threshold boundary unchanged; the Fraction makes score ties exact.
    """
    finding, label = normalize_text(finding), normalize_text(label)
    if not finding or not label:
        return None
    distance, longest = _levenshtein(finding, label), max(len(finding), len(label))
    scores = []
    if 1 - distance / longest >= config.text_threshold:
        scores.append(1 - Fraction(distance, longest))
    if finding.endswith("..."):
        prefix = finding[:-3].rstrip()
        visible = label.removesuffix("...").rstrip()
        if visible and len(prefix.split()) >= config.prefix_min_words:
            coverage = len(prefix) / len(visible)
            if visible.startswith(prefix) and coverage >= config.prefix_min_coverage:
                scores.append(Fraction(len(prefix), len(visible)))
    return max(scores) if scores else None


def _label_score(finding: str, label: Label, config: MatchingConfig) -> Fraction | None:
    """Best score against either text of the label (review of PR #27, rule 1).

    Models often report the full intended string of a truncated label, so a
    finding may identify a label by `text_expected` as well as `text_seen`.
    """
    scores = [
        score
        for text in (label.text_seen, label.text_expected)
        if (score := _match_score(finding, text, config)) is not None
    ]
    return max(scores) if scores else None


def _text_is_present(text: str, screen_texts: Sequence[str], config: MatchingConfig):
    text = normalize_text(text)
    if not text:
        return False
    # Presence is deliberately weaker than identification: a literal fragment
    # can be real text without identifying a label (golden case 08c).
    fragment = text.removesuffix("...").rstrip()
    return any(
        (bool(fragment) and fragment in normalize_text(visible))
        or text_similarity(text, visible) >= config.text_threshold
        for visible in screen_texts
    )


def _assign(candidates: Sequence[Sequence[tuple[int, Fraction]]]) -> list[int | None]:
    """Optimal one-to-one assignment of findings to labels (PR #27, rule 2).

    `candidates[f]` lists (label index, score) for finding f in ascending label
    order. The result maximizes the number of matched labels, then the total
    exact score. Among equal assignments it is the lexicographically smallest
    by input order: findings are decided in order, each trying its labels in
    ascending order before staying unassigned, and the first option that still
    reaches the optimum is kept. The search is exact; its state is the set of
    labels already taken, which stays small for one screen's labels.
    """

    @cache
    def best(finding: int, taken: int) -> tuple[tuple[int, Fraction], tuple]:
        if finding == len(candidates):
            return (0, Fraction(0)), ()
        options = [
            (label, score)
            for label, score in candidates[finding]
            if not taken >> label & 1
        ]
        chosen = None
        for label, score in [*options, (None, Fraction(0))]:
            rest_taken = taken if label is None else taken | 1 << label
            (count, total), rest = best(finding + 1, rest_taken)
            value = (count + (label is not None), total + score)
            if chosen is None or value > chosen[0]:
                chosen = (value, (label, *rest))
        return chosen

    return list(best(0, 0)[1])


@dataclass(frozen=True)
class Match:
    finding_index: int
    label_index: int


@dataclass(frozen=True)
class ScreenMatches:
    """Indices always refer to the original input order, before collapsing."""

    status: ScreenStatus
    labels: tuple[Label, ...]
    findings: tuple[Finding, ...]
    matches: tuple[Match, ...]
    unmatched_finding_indices: tuple[int, ...]
    unmatched_label_indices: tuple[int, ...]
    duplicate_finding_indices: tuple[int, ...]
    hallucination_indices: tuple[int, ...]


def match_screen(
    labels: Sequence[Label],
    findings: Sequence[Finding],
    screen_texts: Sequence[str],
    status: ScreenStatus = "checked",
    config: MatchingConfig = DEFAULT_CONFIG,
) -> ScreenMatches:
    """Assign findings to labels one-to-one, maximizing matches, then collapse.

    A finding identifies a label by `text_seen` or `text_expected`. Region
    restricts identical visible texts only. The assignment maximizes the number
    of matched labels, then the total score, with ties resolved by input order
    (see `_assign`). An unassigned finding that identifies some label is a
    collapsed duplicate: by optimality, every label it identifies is taken.
    Neither defect type nor confidence influences the assignment.
    """
    if status not in ("checked", "not_checked"):
        raise ValueError("unknown screen status")
    labels, findings = tuple(labels), tuple(findings)
    if status == "not_checked":
        if findings:
            raise ValueError("not_checked must have no findings")
        return ScreenMatches(status, labels, findings, (), (), (), (), ())

    occurrences = Counter(map(normalize_text, screen_texts))
    label_occurrences = Counter(normalize_text(label.text_seen) for label in labels)
    candidates = []
    for finding in findings:
        row = []
        for label_index, label in enumerate(labels):
            text = normalize_text(label.text_seen)
            repeated = max(occurrences[text], label_occurrences[text]) > 1
            if repeated and finding.region != label.region:
                continue
            score = _label_score(finding.text_seen, label, config)
            if score is not None:
                row.append((label_index, score))
        candidates.append(row)

    assigned = _assign(candidates)
    matches = sorted(
        (Match(f, label) for f, label in enumerate(assigned) if label is not None),
        key=lambda match: match.label_index,
    )
    unassigned = [f for f, label in enumerate(assigned) if label is None]
    duplicates = [f for f in unassigned if candidates[f]]
    unmatched = [f for f in unassigned if not candidates[f]]
    matched_labels = {match.label_index for match in matches}
    hallucinations = tuple(
        index
        for index in unmatched
        if not _text_is_present(findings[index].text_seen, screen_texts, config)
    )
    return ScreenMatches(
        status,
        labels,
        findings,
        tuple(matches),
        tuple(unmatched),
        tuple(index for index in range(len(labels)) if index not in matched_labels),
        tuple(duplicates),
        hallucinations,
    )
