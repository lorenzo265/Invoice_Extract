"""The arithmetic of a fit: what a signal tells, what a band is worth, how far off it was."""

from __future__ import annotations

import pytest

from invoice_extractor.scoring.fit import (
    ENOUGH,
    Band,
    Pooled,
    Sample,
    bands,
    curve_for,
    expected_calibration_error,
    isotonic,
    smoothed,
    weights_for,
)


def sample(label: float, zone: float, correct: bool) -> Sample:
    return Sample({"label_found": label, "zone_match": zone}, correct)


def test_a_signal_is_worth_how_much_it_tells_the_right_answers_from_the_wrong() -> None:
    samples = [sample(1.0, 0.5, True), sample(0.0, 0.5, False)]
    weights = weights_for(samples)
    assert weights == {"label_found": 1.0}, "a signal that says the same either way tells nothing"


def test_a_corpus_that_was_never_wrong_fits_no_weights_at_all() -> None:
    assert weights_for([sample(1.0, 1.0, True), sample(0.5, 1.0, True)]) is None
    assert weights_for([sample(1.0, 1.0, False)]) is None


def test_a_signal_that_runs_higher_where_the_answer_was_wrong_is_worth_nothing() -> None:
    samples = [sample(0.0, 1.0, True), sample(1.0, 1.0, False)]
    assert weights_for(samples) is None


def test_a_signal_no_sample_emitted_is_not_weighed() -> None:
    samples = [Sample({"label_found": 1.0}, True), Sample({"zone_match": 0.0}, False)]
    assert weights_for(samples) == {"label_found": 1.0}


def test_too_few_observations_to_fit_a_curve_to_fit_none() -> None:
    assert curve_for([(0.5, True)] * (ENOUGH - 1)) is None


def test_a_curve_says_what_a_score_of_each_size_proved_to_be_worth() -> None:
    scored = [(0.2, False)] * 20 + [(0.9, True)] * 20
    curve = curve_for(scored)
    assert curve is not None
    low, high = curve[0], curve[-1]
    assert low[0] == pytest.approx(0.2)
    assert low[1] < high[1]


def test_more_bands_than_there_are_deciles_are_gathered_into_the_last_one() -> None:
    """Ten bands, whatever the corpus divides into: the remainder joins the top one."""
    curve = curve_for([(index / 100, True) for index in range(25)])
    assert curve is not None
    assert len(curve) <= 10


def test_a_curve_never_goes_down_however_the_bands_came_out() -> None:
    scored = [(0.1, True)] * 10 + [(0.2, False)] * 10 + [(0.3, True)] * 10
    curve = curve_for(scored)
    assert curve is not None
    assert [value for _, value in curve] == sorted(value for _, value in curve)


def test_a_band_that_never_failed_is_very_good_rather_than_certain() -> None:
    assert smoothed(Pooled(rate=1.0, count=8, bands=1)) == pytest.approx(9 / 10)
    assert smoothed(Pooled(rate=1.0, count=250, bands=10)) == pytest.approx(251 / 252)


def test_bands_that_agree_are_pooled_into_the_evidence_they_are() -> None:
    assert isotonic([(1.0, 5), (1.0, 5)]) == [Pooled(1.0, 10, 2)]


def test_bands_that_contradict_each_other_are_pooled_into_what_they_came_to() -> None:
    assert isotonic([(1.0, 1), (0.0, 1)]) == [Pooled(0.5, 2, 2)]
    assert isotonic([(0.0, 1), (1.0, 1)]) == [Pooled(0.0, 1, 1), Pooled(1.0, 1, 1)]


def test_the_reliability_curve_is_what_was_predicted_against_what_happened() -> None:
    found = bands([(0.05, False), (0.95, True), (0.99, True)])
    assert [band.count for band in found] == [1, 2]
    assert found[0].observed == 0.0
    assert found[-1].observed == 1.0
    assert found[-1].predicted == pytest.approx(0.97)


def test_a_score_of_one_lands_in_the_last_band_rather_than_outside_them() -> None:
    assert [band.count for band in bands([(1.0, True)])] == [1]


def test_how_far_off_the_confidences_were_is_weighted_by_what_they_spoke_for() -> None:
    found = (
        Band(0.0, 0.5, predicted=0.2, observed=0.2, count=90),
        Band(0.5, 1.0, predicted=0.9, observed=0.4, count=10),
    )
    assert expected_calibration_error(found) == pytest.approx(0.05)
    assert expected_calibration_error(()) == 0.0


def test_a_band_of_the_report_reads_back_as_the_numbers_it_holds() -> None:
    entry = Band(0.0, 0.1, 0.05, 1.0, 3).to_dict()
    assert entry == {"low": 0.0, "high": 0.1, "predicted": 0.05, "observed": 1.0, "count": 3}
