"""What the block did not say, taken from what the rest of the document did."""

from __future__ import annotations

from decimal import Decimal

from conftest import line, make_profile
from invoice_extractor.domain.evidence import Evidence, Strategy
from invoice_extractor.domain.findings import Severity
from invoice_extractor.domain.models import FieldResult
from invoice_extractor.domain.rows import LineItem, VatSummaryRow
from invoice_extractor.domain.totals import Charge
from invoice_extractor.reconcile.amounts import (
    FROM_ITEMS,
    FROM_SUMMARY,
    FROM_TOTAL,
    UNDECLARED,
    backfill_vat,
    choose_currency_basis,
    implied_vat,
    resolve_charges,
)


def evidence(text: str = "20.00") -> Evidence:
    return Evidence(1, line(text, 500, 600).bbox, None, Strategy.TABLE_CELL, text)


def field(name: str, value: object) -> FieldResult:
    return FieldResult(name, value, str(value), evidence(str(value)), valid=True)  # type: ignore[arg-type]


def amounts(**values: str) -> dict[str, FieldResult]:
    return {name: field(name, Decimal(value)) for name, value in values.items()}


def summary_row(rate: str, base: str, vat: str) -> VatSummaryRow:
    return VatSummaryRow(
        rate=Decimal(rate),
        base=Decimal(base),
        vat=Decimal(vat),
        cells={"rate": evidence(rate), "vat": evidence(vat)},
    )


def item(rate: str, net: str) -> LineItem:
    return LineItem(
        vat_rate=Decimal(rate), net_amount=Decimal(net), cells={"vat_rate": evidence(rate)}
    )


def test_a_block_with_no_tax_takes_it_from_the_summary() -> None:
    fields = amounts(subtotal="100.00", total_amount="120.00")
    summary = [summary_row("20", "100.00", "20.00")]
    found = backfill_vat(fields, (), (), summary, make_profile())
    assert found.fields["vat_amount"].value == Decimal("20.00")
    assert [(f.severity, f.code) for f in found.findings] == [
        (Severity.INFO, FROM_SUMMARY),
        (Severity.INFO, FROM_SUMMARY),
    ]


def test_a_backfilled_value_points_at_what_it_was_worked_out_from() -> None:
    summary = [summary_row("20", "100.00", "20.00")]
    found = backfill_vat(amounts(subtotal="100.00"), (), (), summary, make_profile())
    filled = found.fields["vat_amount"].evidence
    assert filled is not None
    assert filled.strategy is Strategy.DERIVED


def test_a_summary_with_no_tax_column_fills_in_nothing() -> None:
    """Nothing here computes a tax the document does not carry the numbers for."""
    summary = [VatSummaryRow(rate=Decimal("20"), base=Decimal("100.00"))]
    found = backfill_vat(amounts(subtotal="100.00"), (), (), summary, make_profile())
    assert "vat_amount" not in found.fields
    assert found.fields["vat_rate"].value == Decimal("20"), "the rate it does print is read"


def test_the_rate_a_document_is_at_is_the_rate_its_summary_is_mostly_at() -> None:
    summary = [summary_row("7", "10.00", "0.70"), summary_row("20", "100.00", "20.00")]
    found = backfill_vat(amounts(subtotal="110.00"), (), (), summary, make_profile())
    assert found.fields["vat_rate"].value == Decimal("20")


def test_the_higher_rate_settles_two_lines_charged_on_as_much() -> None:
    summary = [summary_row("7", "100.00", "7.00"), summary_row("20", "100.00", "20.00")]
    found = backfill_vat(amounts(subtotal="200.00"), (), (), summary, make_profile())
    assert found.fields["vat_rate"].value == Decimal("20")


def test_a_rate_the_block_states_is_not_taken_from_the_summary() -> None:
    fields = {**amounts(subtotal="110.00"), "vat_rate": field("vat_rate", Decimal("7"))}
    summary = [summary_row("20", "100.00", "20.00")]
    found = backfill_vat(fields, (), (), summary, make_profile())
    assert found.fields["vat_rate"].value == Decimal("7")


def test_a_document_with_no_summary_is_at_the_rate_most_of_its_rows_are() -> None:
    """A minimal document states no rate anywhere but the rate column of its own table."""
    items = [item("0", "50.00"), item("20", "100.00"), item("20", "10.00")]
    found = backfill_vat(amounts(subtotal="160.00"), (), items, (), make_profile())
    assert found.fields["vat_rate"].value == Decimal("20")
    assert [finding.code for finding in found.findings] == [FROM_ITEMS]


def test_a_table_with_no_rate_column_says_nothing_about_the_rate() -> None:
    items = [LineItem(net_amount=Decimal("100.00"))]
    found = backfill_vat(amounts(subtotal="100.00"), (), items, (), make_profile())
    assert "vat_rate" not in found.fields


def test_a_document_that_states_no_tax_anywhere_implies_it_from_its_total() -> None:
    fields = amounts(subtotal="100.00", total_amount="120.00")
    found = backfill_vat(fields, (), (), (), make_profile())
    assert found.fields["vat_amount"].value == Decimal("20.00")
    assert [finding.code for finding in found.findings] == [FROM_TOTAL]


def test_a_difference_too_wide_to_be_a_rate_is_not_read_as_tax() -> None:
    fields = amounts(subtotal="100.00", total_amount="200.00")
    assert implied_vat(fields, (), make_profile()) is None


def test_a_charge_the_block_declares_is_not_read_as_tax() -> None:
    fields = amounts(subtotal="100.00", total_amount="105.00")
    charges = [Charge(type="SHIPPING", amount=Decimal("5.00"))]
    found = implied_vat(fields, charges, make_profile())
    assert found is not None
    assert found.value == Decimal("0.00")


def test_tax_is_only_negative_where_the_total_is() -> None:
    """A credit note reverses what it credits; an invoice does not owe tax backwards."""
    fields = amounts(subtotal="100.00", total_amount="95.00")
    assert implied_vat(fields, (), make_profile()) is None


def test_a_credit_note_implies_its_tax_the_same_way() -> None:
    fields = amounts(subtotal="-100.00", total_amount="-120.00")
    found = implied_vat(fields, (), make_profile())
    assert found is not None
    assert found.value == Decimal("-20.00")


def test_a_document_with_no_net_implies_nothing() -> None:
    assert implied_vat(amounts(total_amount="120.00"), (), make_profile()) is None
    assert implied_vat(amounts(subtotal="0.00", total_amount="0.00"), (), make_profile()) is None


def test_a_zero_tax_a_zero_summary_agrees_with_is_left_as_it_is() -> None:
    fields = {**amounts(subtotal="100.00"), "vat_amount": field("vat_amount", Decimal("0.00"))}
    summary = [summary_row("0", "100.00", "0.00")]
    found = backfill_vat(fields, (), (), summary, make_profile())
    assert found.fields["vat_amount"] is fields["vat_amount"]
    assert [finding.field for finding in found.findings] == ["vat_rate"]


def test_a_zero_tax_with_no_summary_at_all_is_left_as_it_is() -> None:
    fields = {
        **amounts(subtotal="100.00", total_amount="120.00"),
        "vat_amount": field("vat_amount", Decimal("0.00")),
    }
    found = backfill_vat(fields, (), (), (), make_profile())
    assert found.fields["vat_amount"].value == Decimal("0.00")


def test_what_the_total_carries_and_no_line_declares_is_a_charge() -> None:
    fields = amounts(subtotal="100.00", vat_amount="20.00", total_amount="125.00")
    found = resolve_charges(fields, (), make_profile())
    assert [(charge.type, charge.amount, charge.declared) for charge in found.charges] == [
        ("OTHER", Decimal("5.00"), False)
    ]
    finding = found.findings[0]
    assert (finding.severity, finding.code) == (Severity.WARNING, UNDECLARED)


def test_a_block_that_adds_up_carries_only_what_it_declared() -> None:
    fields = amounts(subtotal="100.00", vat_amount="20.00", total_amount="125.00")
    declared = [Charge(type="SHIPPING", amount=Decimal("5.00"))]
    found = resolve_charges(fields, declared, make_profile())
    assert found.charges == tuple(declared)
    assert not found.findings


def test_a_document_missing_an_amount_infers_no_charge() -> None:
    found = resolve_charges(amounts(subtotal="100.00"), (), make_profile())
    assert found.charges == ()


def test_the_currency_a_document_is_in_is_the_one_its_amounts_add_up_in() -> None:
    fields = {
        **amounts(subtotal="100.00", vat_amount="20.00", total_amount="120.00"),
        "currency": field("currency", "GBP"),
    }
    assert choose_currency_basis(fields, (), make_profile()) == "GBP"


def test_no_currency_is_chosen_where_the_amounts_do_not_close() -> None:
    fields = {
        **amounts(subtotal="100.00", vat_amount="20.00", total_amount="500.00"),
        "currency": field("currency", "GBP"),
    }
    assert choose_currency_basis(fields, (), make_profile()) is None


def test_no_currency_is_chosen_where_none_was_read() -> None:
    fields = amounts(subtotal="100.00", vat_amount="20.00", total_amount="120.00")
    assert choose_currency_basis(fields, (), make_profile()) is None
