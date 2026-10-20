"""Detection counts and classification confusion for D-026 screen matches."""

from collections import Counter
from collections.abc import Iterable
from dataclasses import asdict, dataclass

from l10n_checker.matching import ScreenMatches
from l10n_checker.vision import DefectType


@dataclass(frozen=True)
class ConfusionCount:
    label_type: DefectType
    finding_type: DefectType
    count: int


@dataclass(frozen=True)
class Metrics:
    tp: int
    fp: int
    fn: int
    precision: float | None
    recall_checked: float | None
    recall_all: float | None
    hallucinations: int
    duplicates_collapsed: int
    not_checked_screens: int
    confusion: tuple[ConfusionCount, ...]
    fn_on_not_checked: int

    def to_dict(self) -> dict:
        """JSON-ready values: undefined remains None (JSON null), never NaN."""
        result = asdict(self)
        result["confusion"] = [asdict(row) for row in self.confusion]
        return result


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def score_screens(screens: Iterable[ScreenMatches]) -> Metrics:
    """Sum counts before dividing; fn excludes labels on not_checked screens.

    No true-negative screen count is inferred. A caller retains the association
    between each ScreenMatches and its screenshot to list unchecked screens.
    """
    tp = fp = fn = hallucinations = duplicates = not_checked = fn_unchecked = 0
    confusion: Counter[tuple[DefectType, DefectType]] = Counter()
    for screen in screens:
        if screen.status == "not_checked":
            not_checked += 1
            fn_unchecked += len(screen.labels)
            continue
        tp += len(screen.matches)
        fp += len(screen.unmatched_finding_indices)
        fn += len(screen.unmatched_label_indices)
        hallucinations += len(screen.hallucination_indices)
        duplicates += len(screen.duplicate_finding_indices)
        for pair in screen.matches:
            confusion[
                (
                    screen.labels[pair.label_index].defect_type,
                    screen.findings[pair.finding_index].defect_type,
                )
            ] += 1
    return Metrics(
        tp=tp,
        fp=fp,
        fn=fn,
        precision=_ratio(tp, tp + fp),
        recall_checked=_ratio(tp, tp + fn),
        recall_all=_ratio(tp, tp + fn + fn_unchecked),
        hallucinations=hallucinations,
        duplicates_collapsed=duplicates,
        not_checked_screens=not_checked,
        confusion=tuple(
            ConfusionCount(label_type, finding_type, count)
            for (label_type, finding_type), count in sorted(confusion.items())
        ),
        fn_on_not_checked=fn_unchecked,
    )


def score_screen(screen: ScreenMatches) -> Metrics:
    return score_screens((screen,))
