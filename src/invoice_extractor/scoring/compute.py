"""Signals to one number (ENGINE_SPEC §8): weighted, renormalised, mapped, capped.

The rule is small and stated once. Every signal a field emitted is worth its weight; the
weights are renormalised over exactly those signals, so a field that could not be asked
half the questions is not scored down for the half it was never asked. What comes out is
put through the field's calibration map — a monotone curve fitted offline, which says
what a score of this size has been worth on documents whose answers were known — and
then capped by whatever stage 5 found the document disagreeing with itself about.

A field with no fitted weights is scored with the uniform mean and says so, because a
number that came from a guess about what matters should not look like one that did not.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from itertools import pairwise

from invoice_extractor.domain.models import FITTED, UNIFORM

PRECISION = 4
NO_CAP = 1.0
# A calibration map is a curve through points a fit measured; between them it is a line.
Curve = Sequence[tuple[float, float]]


@dataclass(frozen=True, slots=True)
class Scored:
    """One field's confidence, what it was made of, and where its weights came from."""

    confidence: float
    breakdown: Mapping[str, float] = field(default_factory=dict)
    source: str = UNIFORM


def compute(
    signals: Mapping[str, float],
    weights: Mapping[str, float] | None = None,
    cap: float | None = None,
    curve: Curve | None = None,
) -> Scored:
    """The weighted mean of the signals a field emitted, calibrated and then capped."""
    if not signals:
        return Scored(0.0)
    shares = _shares(signals, weights)
    total = sum(signals[name] * share for name, share in shares.items())
    mapped = total if curve is None else interpolate(curve, total)
    capped = min(mapped, NO_CAP if cap is None else cap)
    return Scored(
        confidence=round(_clamped(capped), PRECISION),
        breakdown=dict(signals),
        source=UNIFORM if weights is None else FITTED,
    )


def _shares(
    signals: Mapping[str, float], weights: Mapping[str, float] | None
) -> Mapping[str, float]:
    """What each emitted signal is worth once the weights are renormalised over them."""
    if weights is None:
        return dict.fromkeys(signals, 1.0 / len(signals))
    wanted = {name: max(weights.get(name, 0.0), 0.0) for name in signals}
    total = sum(wanted.values())
    if total <= 0.0:
        return dict.fromkeys(signals, 1.0 / len(signals))
    return {name: value / total for name, value in wanted.items()}


def interpolate(curve: Curve, value: float) -> float:
    """What the fit observed at a score of this size, read off the curve between points."""
    points = sorted(curve)
    if not points:
        return value
    if value <= points[0][0]:
        return points[0][1]
    for (left, low), (right, high) in pairwise(points):
        if value <= right:
            span = right - left
            return high if span <= 0 else low + (high - low) * (value - left) / span
    return points[-1][1]


def _clamped(value: float) -> float:
    return min(max(value, 0.0), 1.0)
