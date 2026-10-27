"""Type-free, per-screen detection matching (D-026). No provider calls or I/O."""

import math
import re
import unicodedata
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction
from typing import Literal

from pydantic import BaseModel, ConfigDict

from l10n_checker.vision import DefectType, DefectTypeV1, Finding, FindingV1, Region

ScreenStatus = Literal["checked", "not_checked"]


class Label(BaseModel):
    """Human-owned label (label schema 2), including technical-text notes."""

    model_config = ConfigDict(extra="forbid")

    defect_type: DefectType
    text_expected: str
    text_seen: str
    region: Region
    note: str | None = None


class LabelV1(Label):
    """A label from a schema 1 label file, read for detection scoring only."""

    defect_type: DefectTypeV1


def load_labels(label_file: dict) -> tuple[int, list[Label]]:
    """Labels of a `.labels.json` file, validated by its integer schema_version."""
    version = label_file["schema_version"]
    if type(version) is not int or version not in (1, 2):
        raise ValueError(f"unknown label schema version: {version!r}")
    model = LabelV1 if version == 1 else Label
    return version, [model.model_validate(row) for row in label_file["labels"]]


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


def _text_is_present(
    text: str,
    screen_texts: Sequence[str],
    labels: Sequence[Label],
    config: MatchingConfig,
) -> bool:
    """Whether an unassigned finding names real text (PR #27, rule 3).

    Presence is deliberately weaker than identification (golden case 08c), but
    a fragment must be whole words: the finding's body, without a terminal
    ellipsis, must sit at word boundaries inside a visible text. Near-exact
    similarity to a visible text also counts, and so does identifying any
    label's expected text, so such a finding is never a hallucination.
    """
    text = normalize_text(text)
    if not text:
        return False
    body = text.removesuffix("...").rstrip()
    words = re.compile(rf"(?<!\w){re.escape(body)}(?!\w)") if body else None
    return any(
        (words is not None and words.search(normalize_text(visible)) is not None)
        or text_similarity(text, visible) >= config.text_threshold
        for visible in screen_texts
    ) or any(
        _match_score(text, label.text_expected, config) is not None for label in labels
    )


def _minimum_cost_columns(costs: Sequence[Sequence[int]]) -> list[int]:
    """Rectangular Hungarian algorithm; nonempty rows <= columns.

    Return one distinct column per row in O(rows**2 * columns) integer
    operations. Potentials and shortest augmenting paths use exact integers.
    Column zero is the temporary root of each augmenting path.
    """
    rows, columns = len(costs), len(costs[0])
    row_potential = [0] * (rows + 1)
    column_potential = [0] * (columns + 1)
    row_for_column = [0] * (columns + 1)
    predecessor = [0] * (columns + 1)
    for row in range(1, rows + 1):
        row_for_column[0] = row
        column = 0
        minimum: list[int | None] = [None] * (columns + 1)
        visited = [False] * (columns + 1)
        while True:
            visited[column] = True
            current_row = row_for_column[column]
            delta = None
            next_column = 0
            for target in range(1, columns + 1):
                if visited[target]:
                    continue
                reduced = (
                    costs[current_row - 1][target - 1]
                    - row_potential[current_row]
                    - column_potential[target]
                )
                if minimum[target] is None or reduced < minimum[target]:
                    minimum[target] = reduced
                    predecessor[target] = column
                if delta is None or minimum[target] < delta:
                    delta, next_column = minimum[target], target
            # There is always a free column because rows <= columns.
            assert delta is not None
            for target in range(columns + 1):
                if visited[target]:
                    row_potential[row_for_column[target]] += delta
                    column_potential[target] -= delta
                elif minimum[target] is not None:
                    minimum[target] -= delta
            column = next_column
            if row_for_column[column] == 0:
                break
        while column:
            previous = predecessor[column]
            row_for_column[column] = row_for_column[previous]
            column = previous

    assigned = [0] * rows
    for column in range(1, columns + 1):
        if row_for_column[column]:
            assigned[row_for_column[column] - 1] = column - 1
    return assigned


def _assign(candidates: Sequence[Sequence[tuple[int, Fraction]]]) -> list[int | None]:
    """Optimal one-to-one assignment with the exact search's tie-breaking.

    `candidates[f]` lists distinct (label index, score) pairs in ascending label
    order. Maximize matched labels, then the exact Fraction score sum. For ties,
    choose the lexicographically smallest assignment in finding input order,
    with ascending label indices preferred before None at every position.

    Scale scores by their denominators' LCM and encode the three priorities
    as one integer weight; no float rounding or epsilon is used. The Hungarian
    algorithm assigns F findings to L real plus F dummy columns in
    O(F**2 * (L + F)) integer operations and O(F * (L + F)) space. Integer bit
    lengths are polynomial in the input size; see docs/matching-metrics.md
    for the weight bounds. Neither candidate generation nor scoring changes.
    """
    findings = len(candidates)
    labels = sorted({label for row in candidates for label, _ in row})
    if not labels:
        return [None] * findings
    label_columns = {label: column for column, label in enumerate(labels)}
    denominator = math.lcm(
        *(score.denominator for row in candidates for _, score in row)
    )
    scaled = [
        [
            (label_columns[label], score.numerator * (denominator // score.denominator))
            for label, score in row
        ]
        for row in candidates
    ]
    max_score = max(abs(score) for row in scaled for _, score in row)
    base = len(labels) + 1
    score_weight = base**findings
    # Total scaled scores lie in [-F*M, F*M]; tie digits total < score_weight.
    count_weight = (2 * findings * max_score + 1) * score_weight
    place = score_weight // base
    costs = []
    for row in scaled:
        # Nonedges cost 1, dummy columns 0, real edges < 0. With F dummies,
        # any nonedge could be replaced by a free dummy, so none is optimal.
        costs.append([1] * len(labels) + [0] * findings)
        for column, score in row:
            preference = (len(labels) - column) * place
            costs[-1][column] = -(count_weight + score * score_weight + preference)
        place //= base
    return [
        labels[column] if column < len(labels) else None
        for column in _minimum_cost_columns(costs)
    ]


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
    label_schema_version: int = 2
    result_schema_version: int = 2


def match_screen(
    labels: Sequence[Label],
    findings: Sequence[Finding],
    screen_texts: Sequence[str],
    status: ScreenStatus = "checked",
    config: MatchingConfig = DEFAULT_CONFIG,
    *,
    label_schema_version: int = 2,
    result_schema_version: int = 2,
) -> ScreenMatches:
    """Assign findings to labels one-to-one, maximizing matches, then collapse.

    A finding identifies a label by `text_seen` or `text_expected`. Region
    restricts identical visible texts only. The assignment maximizes the number
    of matched labels, then the total score, with ties resolved by input order
    (see `_assign`). An unassigned finding that identifies some label is a
    collapsed duplicate: by optimality, every label it identifies is taken.
    Neither defect type nor confidence influences the assignment. The schema
    versions only decide whether metrics may compare the classes (D-046).
    """
    if status not in ("checked", "not_checked"):
        raise ValueError("unknown screen status")
    labels, findings = tuple(labels), tuple(findings)
    for items, version, models, side in (
        (labels, label_schema_version, (LabelV1, Label), "label"),
        (findings, result_schema_version, (FindingV1, Finding), "result"),
    ):
        if type(version) is not int or version not in (1, 2):
            raise ValueError(f"unknown {side} schema version: {version!r}")
        if any(type(item) is not models[version - 1] for item in items):
            raise ValueError(f"{side} objects do not match {side} schema v{version}")
    versions = {
        "label_schema_version": label_schema_version,
        "result_schema_version": result_schema_version,
    }
    if status == "not_checked":
        if findings:
            raise ValueError("not_checked must have no findings")
        return ScreenMatches(status, labels, findings, (), (), (), (), (), **versions)

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
        if not _text_is_present(findings[index].text_seen, screen_texts, labels, config)
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
        **versions,
    )
