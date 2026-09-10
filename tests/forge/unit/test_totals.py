"""Totals are derived from the rows, under whichever rounding policy is asked for."""

from __future__ import annotations

from decimal import Decimal

import pytest

from invoice_forge.model import (
    Charge,
    ChargeType,
    LineItem,
    RoundingPolicy,
    compute_totals,
    to_cents,
)

STANDARD = Decimal("19")
REDUCED = Decimal("7")


def item(
    quantity: str, price: str, rate: Decimal = STANDARD, discount: str | None = None
) -> LineItem:
    return LineItem(
        pos=1,
        sku="SKU-1",
        description="A thing",
        quantity=Decimal(quantity),
        unit="ea",
        unit_price=Decimal(price),
        vat_rate=rate,
        discount_percent=None if discount is None else Decimal(discount),
    )


def shipping(amount: str, declared: bool = True) -> Charge:
    return Charge(ChargeType.SHIPPING, Decimal(amount), STANDARD, declared=declared)


def test_to_cents_rounds_half_away_from_zero() -> None:
    assert to_cents(Decimal("0.125")) == Decimal("0.13")
    assert to_cents(Decimal("0.135")) == Decimal("0.14")


def test_a_line_net_is_quantity_times_price() -> None:
    assert item("25", "349.00").net_amount == Decimal("8725.00")


def test_a_discount_comes_off_the_line() -> None:
    assert item("10", "100.00", discount="10").net_amount == Decimal("900.00")


def test_totals_add_the_rows_the_charges_and_the_tax() -> None:
    totals = compute_totals([item("2", "10.00")], [shipping("5.00")], RoundingPolicy.PER_LINE)
    assert totals.subtotal == Decimal("20.00")
    assert totals.charges_total == Decimal("5.00")
    assert totals.vat_amount == Decimal("4.75")
    assert totals.total_amount == Decimal("29.75")


@pytest.mark.parametrize("policy", list(RoundingPolicy))
def test_both_policies_agree_when_every_line_is_already_exact(policy: RoundingPolicy) -> None:
    items = [item("2", "10.00"), item("3", "1.15")]
    assert compute_totals(items, [], policy).subtotal == Decimal("23.45")


def test_per_line_rounds_every_row_before_adding() -> None:
    # Three rows of 0.005 each: rounded per row they are 0.01 apiece.
    items = [item("1", "0.005") for _ in range(3)]
    totals = compute_totals(items, [], RoundingPolicy.PER_LINE)
    assert totals.subtotal == Decimal("0.03")


def test_total_rounding_adds_first_and_rounds_once() -> None:
    items = [item("1", "0.005") for _ in range(3)]
    totals = compute_totals(items, [], RoundingPolicy.TOTAL)
    assert totals.subtotal == Decimal("0.02")


def test_a_vat_line_per_rate_lowest_first() -> None:
    items = [item("1", "100.00", STANDARD), item("1", "200.00", REDUCED)]
    lines = compute_totals(items, [], RoundingPolicy.PER_LINE).vat_lines
    assert [line.rate for line in lines] == [REDUCED, STANDARD]
    assert [line.base for line in lines] == [Decimal("200.00"), Decimal("100.00")]
    assert [line.vat for line in lines] == [Decimal("14.00"), Decimal("19.00")]


def test_a_declared_charge_joins_the_vat_base_of_its_rate() -> None:
    totals = compute_totals([item("1", "100.00")], [shipping("10.00")], RoundingPolicy.PER_LINE)
    (line,) = totals.vat_lines
    assert line.base == Decimal("110.00")


def test_an_undeclared_charge_is_in_the_total_and_nowhere_else() -> None:
    charge = shipping("10.00", declared=False)
    totals = compute_totals([item("1", "100.00")], [charge], RoundingPolicy.PER_LINE)
    assert totals.charges_total == Decimal("0")
    assert totals.undeclared_total == Decimal("10.00")
    (line,) = totals.vat_lines
    assert line.base == Decimal("100.00")
    assert totals.total_amount == Decimal("129.00")
    # The document deliberately does not add up: that is what the knob is for.
    assert totals.total_amount != totals.subtotal + totals.charges_total + totals.vat_amount


def test_a_document_with_no_rows_totals_to_nothing() -> None:
    totals = compute_totals([], [], RoundingPolicy.PER_LINE)
    assert totals.subtotal == Decimal("0")
    assert totals.vat_lines == ()
    assert totals.total_amount == Decimal("0.00")
