"""Compare production assignment with the frozen exact search from 335f6a4.

The oracle is copied from matching.py before issue #31's optimization. Keep its
search independent of production helpers and preserve its original logic.
"""

from collections.abc import Sequence
from fractions import Fraction
from functools import cache
from random import Random

import pytest

from l10n_checker.matching import _assign


def _exact_assign(
    candidates: Sequence[Sequence[tuple[int, Fraction]]],
) -> list[int | None]:
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


@pytest.mark.parametrize("seed", range(1000))
def test_assignment_matches_exact_search(seed):
    rng = Random(seed)
    label_count = seed % 9
    finding_count = (seed // 9) % 11
    # Include missing label indices as well as rectangular, empty and dense inputs.
    labels = sorted(rng.sample(range(16), label_count))
    density = (0.25, 0.6, 1.0)[(seed // 99) % 3]
    score_pools = (
        (Fraction(1),),  # Deliberate ties throughout the graph.
        (Fraction(1, 2), Fraction(2, 3), Fraction(3, 4), Fraction(1)),
        (Fraction(1), Fraction(1) - Fraction(1, 10**20)),
        (Fraction(9, 10), Fraction(19, 20), Fraction(20, 21), Fraction(1)),
    )
    pool = score_pools[seed % len(score_pools)]
    candidates = [
        [(label, rng.choice(pool)) for label in labels if rng.random() < density]
        for _ in range(finding_count)
    ]
    assert _assign(candidates) == _exact_assign(candidates), (seed, candidates)


@pytest.mark.parametrize(
    "candidates",
    [
        [],
        [[], [], []],
        [[(0, Fraction(1)), (1, Fraction(1, 2))], [(0, Fraction(1))]],
        [[(0, Fraction(1))], [(0, Fraction(1))], [(0, Fraction(1))]],
        [
            [(0, Fraction(1, 2)), (1, Fraction(2, 3))],
            [(0, Fraction(1, 3)), (1, Fraction(1, 2))],
        ],  # Different denominators, identical total scores.
        [
            [(0, Fraction(1) - Fraction(1, 10**20)), (1, Fraction(1))],
            [(0, Fraction(1)), (1, Fraction(1))],
        ],  # A score difference smaller than float precision beats input order.
        [[(2, Fraction(0)), (7, Fraction(-10))], [(2, Fraction(100))]],
    ],
)
def test_assignment_boundaries_match_exact_search(candidates):
    assert _assign(candidates) == _exact_assign(candidates)
