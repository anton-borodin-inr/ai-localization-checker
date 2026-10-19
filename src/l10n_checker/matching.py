"""Type-free, per-screen detection matching (D-026). No provider calls or I/O."""

import math
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
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


def text_similarity(first: str, second: str) -> float:
    """1 - Levenshtein distance / max length, over normalized Unicode text.

    Empty strings score zero, including against another empty string.
    """
    first, second = normalize_text(first), normalize_text(second)
    if not first or not second:
        return 0.0
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
    return 1 - previous[-1] / max(len(first), len(second))


def _match_score(finding: str, label: str, config: MatchingConfig) -> float | None:
    finding, label = normalize_text(finding), normalize_text(label)
    if not finding or not label:
        return None
    similarity = text_similarity(finding, label)
    scores = [similarity] if similarity >= config.text_threshold else []
    if finding.endswith("..."):
        prefix = finding[:-3].rstrip()
        visible = label.removesuffix("...").rstrip()
        if visible and len(prefix.split()) >= config.prefix_min_words:
            coverage = len(prefix) / len(visible)
            if visible.startswith(prefix) and coverage >= config.prefix_min_coverage:
                scores.append(coverage)
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
    """Assign each finding to its strongest eligible label, then collapse.

    Region restricts identical visible texts only. Candidate ties use label
    input order; representative ties use finding input order. Neither defect
    type nor confidence influences assignment or representative selection.
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
    groups: dict[int, list[tuple[float, int]]] = defaultdict(list)
    unmatched = []
    for finding_index, finding in enumerate(findings):
        candidates = []
        for label_index, label in enumerate(labels):
            text = normalize_text(label.text_seen)
            repeated = max(occurrences[text], label_occurrences[text]) > 1
            if repeated and finding.region != label.region:
                continue
            score = _match_score(finding.text_seen, label.text_seen, config)
            if score is not None:
                candidates.append((score, -label_index))
        if candidates:
            score, negative_index = max(candidates)
            groups[-negative_index].append((score, finding_index))
        else:
            unmatched.append(finding_index)

    matches, duplicates = [], []
    for label_index, group in sorted(groups.items()):
        ordered = sorted(group, key=lambda item: (-item[0], item[1]))
        matches.append(Match(ordered[0][1], label_index))
        duplicates.extend(index for _, index in ordered[1:])
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
        tuple(index for index in range(len(labels)) if index not in groups),
        tuple(sorted(duplicates)),
        hallucinations,
    )
