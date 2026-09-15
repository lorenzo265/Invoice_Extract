"""The arithmetic of a fit: what a signal tells, what a score has been worth, how far off.

Three small pieces, none of which knows what a document is. A signal is worth what it
tells apart — how much higher it runs on the values that turned out right than on the
ones that turned out wrong. A score is worth what it has been worth: the observed rate in
its own band, pooled where the bands contradict each other, which is the nearest
non-decreasing curve to what was measured. And how far off the whole thing is is the
weighted distance between what it predicted and what happened.

Everything here is deterministic and dependency-free: the same samples in the same order
produce the same numbers, which is what makes a committed fit reviewable (ENGINE_SPEC §9).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

# Ten bands, which is what a reliability report is read in.
BANDS = 10
# The fewest observations worth fitting a curve to. Below it the bands are noise.
ENOUGH = 20
PRECISION = 6


@dataclass(frozen=True, slots=True)
class Sample:
    """One field on one document: what its signals said, and whether it was right."""

    signals: Mapping[str, float]
    correct: bool


@dataclass(frozen=True, slots=True)
class Pooled:
    """One block of a fitted curve: what it pooled to, out of how much, over how many bands."""

    rate: float
    count: int
    bands: int


@dataclass(frozen=True, slots=True)
class Band:
    """One band of predicted confidence: what it predicted, what happened, how often."""

    low: float
    high: float
    predicted: float
    observed: float
    count: int

    def to_dict(self) -> dict[str, object]:
        return {
            "low": round(self.low, PRECISION),
            "high": round(self.high, PRECISION),
            "predicted": round(self.predicted, PRECISION),
            "observed": round(self.observed, PRECISION),
            "count": self.count,
        }


def weights_for(samples: Sequence[Sample]) -> Mapping[str, float] | None:
    """What each signal is worth: how much higher it runs where the answer was right.

    A corpus that never got this field wrong has nothing to tell the two apart on, and no
    weights are fitted from it — the field is scored with the uniform mean and says so.
    """
    right = [sample for sample in samples if sample.correct]
    wrong = [sample for sample in samples if not sample.correct]
    if not right or not wrong:
        return None
    fitted = {name: max(_mean(right, name) - _mean(wrong, name), 0.0) for name in _named(samples)}
    kept = {name: round(value, PRECISION) for name, value in fitted.items() if value > 0.0}
    return kept or None


def curve_for(scored: Sequence[tuple[float, bool]]) -> tuple[tuple[float, float], ...] | None:
    """What a score of each size proved to be worth, as a curve that never goes down."""
    if len(scored) < ENOUGH:
        return None
    grouped = _deciles(sorted(scored))
    blocks = isotonic([(observed, count) for _, observed, count in grouped])
    worth = [smoothed(block) for block in blocks for _ in range(block.bands)]
    points = {
        round(predicted, PRECISION): round(value, PRECISION)
        for (predicted, _, _), value in zip(grouped, worth, strict=True)
    }
    return tuple(sorted(points.items()))


def smoothed(block: Pooled) -> float:
    """What a block of the fit is worth, as evidence rather than as a promise.

    A curve is fitted from what was measured, and what was measured is a sample: two
    values right out of two is not a promise, and two hundred out of two hundred is not
    quite one either. Crediting every block with one of each outcome is what keeps a fit
    from claiming more than the corpus behind it can support.
    """
    return (block.rate * block.count + 1) / (block.count + _BOTH_OUTCOMES)


def bands(scored: Sequence[tuple[float, bool]], count: int = BANDS) -> tuple[Band, ...]:
    """The reliability curve: equal-width bands of what was predicted against what happened."""
    found: list[Band] = []
    for index in range(count):
        low, high = index / count, (index + 1) / count
        inside = [pair for pair in scored if _within(pair[0], low, high, index == count - 1)]
        if inside:
            found.append(_band(low, high, inside))
    return tuple(found)


def expected_calibration_error(found: Sequence[Band]) -> float:
    """How far the confidences were off, weighted by how many values they spoke for."""
    total = sum(band.count for band in found)
    if not total:
        return 0.0
    apart = sum(band.count * abs(band.predicted - band.observed) for band in found)
    return round(apart / total, PRECISION)


def isotonic(observations: Sequence[tuple[float, int]]) -> list[Pooled]:
    """Pool adjacent violators: the nearest non-decreasing sequence to what was observed.

    Bands that agree are pooled with the ones that contradict each other, because two
    bands that came to the same rate are one piece of evidence about that rate and are
    worth believing twice as much as either of them alone.
    """
    blocks: list[Pooled] = []
    for value, weight in observations:
        blocks.append(Pooled(value, max(weight, 1), 1))
        while len(blocks) > 1 and blocks[-2].rate >= blocks[-1].rate:
            blocks[-2:] = [_pooled(blocks[-2], blocks[-1])]
    return blocks


def _pooled(left: Pooled, right: Pooled) -> Pooled:
    count = left.count + right.count
    rate = (left.rate * left.count + right.rate * right.count) / count
    return Pooled(rate, count, left.bands + right.bands)


def _deciles(scored: Sequence[tuple[float, bool]]) -> list[tuple[float, float, int]]:
    """Ten groups of as near as makes no difference the same size, in score order."""
    size = max(len(scored) // BANDS, 1)
    groups = [scored[start : start + size] for start in range(0, len(scored), size)]
    if len(groups) > BANDS:
        groups[BANDS - 1 :] = [[pair for group in groups[BANDS - 1 :] for pair in group]]
    return [(_scores(group), _rate(group), len(group)) for group in groups]


def _band(low: float, high: float, inside: Sequence[tuple[float, bool]]) -> Band:
    return Band(low, high, _scores(inside), _rate(inside), len(inside))


def _within(score: float, low: float, high: float, last: bool) -> bool:
    return low <= score < high or (last and score == high)


def _scores(group: Sequence[tuple[float, bool]]) -> float:
    return sum(score for score, _ in group) / len(group)


def _rate(group: Sequence[tuple[float, bool]]) -> float:
    return sum(1 for _, correct in group if correct) / len(group)


# The one hit and the one miss every band is credited with before it is believed.
_BOTH_OUTCOMES = 2


def _named(samples: Sequence[Sample]) -> list[str]:
    return sorted({name for sample in samples for name in sample.signals})


def _mean(samples: Sequence[Sample], name: str) -> float:
    """The mean of one signal over the samples that emitted it; an absent one says nothing."""
    values = [sample.signals[name] for sample in samples if name in sample.signals]
    return sum(values) / len(values) if values else 0.0
