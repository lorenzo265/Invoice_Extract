"""Confidence is a weighted sum of five named signals, and it says which ones lit."""

from __future__ import annotations

from decimal import Decimal

from conftest import make_field_profile
from invoice_extractor.document.model import BBox, Zone
from invoice_extractor.domain.findings import Finding, Severity
from invoice_extractor.domain.models import Evidence, FieldResult, Strategy
from invoice_extractor.extraction.engine import Extraction
from invoice_extractor.validation.confidence import SIGNAL_WEIGHTS, score

BOTTOM_RIGHT = Zone(3, 3)
EXPECTED_ZONE = make_field_profile(zones=(BOTTOM_RIGHT,))
BOX = BBox(400.0, 609.25, 472.83, 622.99)


def extraction(
    label: str | None = "Subtotal",
    zone: Zone | None = BOTTOM_RIGHT,
    candidate_count: int = 1,
    valid: bool = True,
    value: object = Decimal("490.00"),
) -> Extraction:
    evidence = Evidence(1, BOX, label, Strategy.LABEL_RIGHT, "Subtotal: 490.00")
    field = FieldResult(
        name="subtotal",
        value=value,  # type: ignore[arg-type]  # a test may pass None to model a missing field
        raw_text="Subtotal: 490.00",
        evidence=evidence,
        valid=valid,
    )
    return Extraction(field=field, candidate_count=candidate_count, zone=zone)


def test_weights_sum_to_one() -> None:
    assert round(sum(SIGNAL_WEIGHTS.values()), 10) == 1.0


def test_all_signals_lit_scores_one() -> None:
    assert score(extraction(), EXPECTED_ZONE, ()).confidence == 1.0


def test_missing_field_scores_zero() -> None:
    scored = score(extraction(value=None), EXPECTED_ZONE, ())
    assert scored.confidence == 0.0
    assert set(scored.confidence_breakdown.values()) == {0.0}


def test_breakdown_lists_every_signal() -> None:
    scored = score(extraction(), EXPECTED_ZONE, ())
    assert tuple(scored.confidence_breakdown) == tuple(SIGNAL_WEIGHTS)


def test_breakdown_entries_sum_to_the_confidence() -> None:
    scored = score(extraction(label=None, candidate_count=3), EXPECTED_ZONE, ())
    assert round(sum(scored.confidence_breakdown.values()), 2) == scored.confidence


def test_error_finding_on_field_clears_invariants_signal() -> None:
    error = Finding(Severity.ERROR, "totals_reconcile", "disagrees", field="subtotal")
    scored = score(extraction(), EXPECTED_ZONE, (error,))
    assert scored.confidence_breakdown["invariants_agree"] == 0.0
    assert scored.confidence == round(1.0 - SIGNAL_WEIGHTS["invariants_agree"], 2)


def test_an_error_about_another_field_leaves_this_one_alone() -> None:
    error = Finding(Severity.ERROR, "totals_reconcile", "disagrees", field="total_amount")
    assert score(extraction(), EXPECTED_ZONE, (error,)).confidence == 1.0


def test_a_warning_does_not_clear_the_invariants_signal() -> None:
    warning = Finding(Severity.WARNING, "line_items_sum", "skipped", field="subtotal")
    assert score(extraction(), EXPECTED_ZONE, (warning,)).confidence == 1.0


def test_a_zone_outside_the_layouts_list_clears_that_signal() -> None:
    scored = score(extraction(zone=Zone(1, 1)), EXPECTED_ZONE, ())
    assert scored.confidence_breakdown["in_expected_zone"] == 0.0


def test_more_than_one_candidate_clears_that_signal() -> None:
    scored = score(extraction(candidate_count=2), EXPECTED_ZONE, ())
    assert scored.confidence_breakdown["single_candidate"] == 0.0


def test_a_failed_validator_clears_that_signal() -> None:
    scored = score(extraction(valid=False), EXPECTED_ZONE, ())
    assert scored.confidence_breakdown["validator_passed"] == 0.0


def test_a_regex_match_with_no_label_clears_that_signal() -> None:
    scored = score(extraction(label=None), EXPECTED_ZONE, ())
    assert scored.confidence_breakdown["label_exact_match"] == 0.0
