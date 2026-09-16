"""Signals to one number: weighted, renormalised, mapped and capped."""

from __future__ import annotations

import pytest

from invoice_extractor.domain.models import FITTED, UNIFORM
from invoice_extractor.scoring.compute import compute, interpolate


def test_a_field_with_no_signals_is_trusted_not_at_all() -> None:
    scored = compute({})
    assert scored.confidence == 0.0
    assert scored.breakdown == {}
    assert scored.source == UNIFORM


def test_without_weights_every_signal_counts_the_same() -> None:
    scored = compute({"label_found": 1.0, "zone_match": 0.0})
    assert scored.confidence == 0.5
    assert scored.source == UNIFORM


def test_the_breakdown_is_what_the_signals_said() -> None:
    signals = {"label_found": 1.0, "zone_match": 0.25}
    assert compute(signals).breakdown == signals


def test_weights_are_renormalised_over_the_signals_a_field_emitted() -> None:
    """A field that could not be asked half the questions is not scored down for them."""
    weights = {"label_found": 1.0, "zone_match": 1.0, "runner_up_gap": 8.0}
    scored = compute({"label_found": 1.0, "zone_match": 0.0}, weights)
    assert scored.confidence == 0.5
    assert scored.source == FITTED


def test_a_weight_says_how_much_a_signal_is_worth() -> None:
    weights = {"label_found": 3.0, "zone_match": 1.0}
    assert compute({"label_found": 1.0, "zone_match": 0.0}, weights).confidence == 0.75


def test_weights_that_name_none_of_the_emitted_signals_fall_back_to_the_mean() -> None:
    scored = compute({"label_found": 1.0, "zone_match": 0.0}, {"runner_up_gap": 1.0})
    assert scored.confidence == 0.5


def test_a_negative_weight_is_worth_nothing_rather_than_less_than_nothing() -> None:
    weights = {"label_found": 1.0, "zone_match": -5.0}
    assert compute({"label_found": 1.0, "zone_match": 0.0}, weights).confidence == 1.0


def test_a_cap_from_stage_five_is_the_most_a_field_can_be_worth() -> None:
    assert compute({"label_found": 1.0}, cap=0.5).confidence == 0.5
    assert compute({"label_found": 1.0}, cap=None).confidence == 1.0


def test_a_curve_says_what_a_score_of_that_size_has_been_worth() -> None:
    curve = ((0.0, 0.0), (1.0, 0.5))
    assert compute({"label_found": 1.0}, curve=curve).confidence == 0.5


def test_a_confidence_never_leaves_nought_to_one() -> None:
    assert compute({"label_found": 4.0}).confidence == 1.0
    assert compute({"label_found": -4.0}).confidence == 0.0


@pytest.mark.parametrize(
    ("value", "expected"),
    [(0.0, 0.2), (0.5, 0.6), (0.75, 0.8), (1.0, 1.0), (2.0, 1.0), (-1.0, 0.2)],
)
def test_a_curve_is_a_line_between_the_points_it_was_fitted_at(
    value: float, expected: float
) -> None:
    assert interpolate(((0.0, 0.2), (0.5, 0.6), (1.0, 1.0)), value) == pytest.approx(expected)


def test_a_curve_with_no_points_changes_nothing() -> None:
    assert interpolate((), 0.4) == 0.4


def test_two_points_at_one_score_read_as_the_later_of_them() -> None:
    """A fit may measure the same score twice; a curve is still a function of it."""
    assert interpolate(((0.5, 0.2), (0.5, 0.9)), 0.5) == 0.2
    assert interpolate(((0.4, 0.1), (0.5, 0.2), (0.5, 0.9)), 0.45) == pytest.approx(0.15)
