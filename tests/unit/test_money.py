"""Exact rounding and the tolerance every invariant is measured against."""

from __future__ import annotations

from decimal import Decimal

import pytest

from invoice_extractor.domain.money import CENT, quantize_cents, within_tolerance


@pytest.mark.parametrize(
    ("value", "expected"),
    [("0.125", "0.12"), ("0.135", "0.14"), ("2.345", "2.34"), ("2.355", "2.36")],
)
def test_quantize_cents_rounds_half_even(value: str, expected: str) -> None:
    assert quantize_cents(Decimal(value)) == Decimal(expected)


def test_quantize_cents_keeps_two_places_on_a_whole_amount() -> None:
    assert str(quantize_cents(Decimal("490"))) == "490.00"


def test_within_tolerance_at_boundary() -> None:
    assert within_tolerance(Decimal("588.00"), Decimal("588.01"))
    assert not within_tolerance(Decimal("588.00"), Decimal("588.02"))


def test_within_tolerance_accepts_a_wider_tolerance() -> None:
    assert within_tolerance(Decimal("100.00"), Decimal("100.05"), tolerance=Decimal("0.05"))
    assert Decimal("0.01") == CENT
