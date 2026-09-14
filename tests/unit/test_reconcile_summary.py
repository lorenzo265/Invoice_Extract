"""Does the block agree with the summary, and which line of it taxes which row."""

from __future__ import annotations

from decimal import Decimal

from conftest import make_profile
from invoice_extractor.domain.findings import Severity
from invoice_extractor.domain.models import FieldResult
from invoice_extractor.domain.rows import LineItem, VatSummaryRow
from invoice_extractor.domain.totals import Charge
from invoice_extractor.reconcile.summary import (
    AMBIGUOUS,
    DISAGREE,
    DISAGREEMENT_CAP,
    cross_check_totals_vs_summary,
    link_items_to_vat_lines,
)


def amounts(**values: str) -> dict[str, FieldResult]:
    return {
        name: FieldResult(name, Decimal(value), value, None, valid=True)
        for name, value in values.items()
    }


def row(rate: str | None, base: str | None, vat: str | None) -> VatSummaryRow:
    return VatSummaryRow(
        rate=None if rate is None else Decimal(rate),
        base=None if base is None else Decimal(base),
        vat=None if vat is None else Decimal(vat),
    )


def test_a_summary_that_says_what_the_block_says_agrees_with_it() -> None:
    fields = amounts(subtotal="100.00", vat_amount="20.00")
    summary = [row("20", "100.00", "20.00")]
    found = cross_check_totals_vs_summary(fields, (), summary, make_profile())
    assert found.agrees
    assert found.caps == {}
    assert found.findings == ()


def test_a_document_that_prints_no_summary_disagrees_with_nothing() -> None:
    fields = amounts(subtotal="100.00", vat_amount="20.00")
    assert cross_check_totals_vs_summary(fields, (), (), make_profile()).agrees


def test_a_summary_adding_up_to_another_tax_caps_the_tax_it_disagrees_with() -> None:
    fields = amounts(subtotal="100.00", vat_amount="7.00")
    summary = [row("20", "100.00", "20.00")]
    found = cross_check_totals_vs_summary(fields, (), summary, make_profile())
    assert not found.vat_agrees
    assert found.caps == {"vat_amount": DISAGREEMENT_CAP}
    finding = found.findings[0]
    assert (finding.severity, finding.code, finding.field) == (
        Severity.WARNING,
        DISAGREE,
        "vat_amount",
    )


def test_what_the_summary_is_charged_on_is_the_net_and_the_charges_the_block_named() -> None:
    """A vendor that bills for delivery taxes the delivery, and its base says so."""
    fields = amounts(subtotal="100.00", vat_amount="21.00")
    charges = [Charge(type="SHIPPING", amount=Decimal("5.00"))]
    summary = [row("20", "105.00", "21.00")]
    assert cross_check_totals_vs_summary(fields, charges, summary, make_profile()).agrees


def test_a_base_the_block_does_not_come_to_caps_the_net() -> None:
    fields = amounts(subtotal="100.00", vat_amount="100.00")
    summary = [row("20", "500.00", "100.00")]
    found = cross_check_totals_vs_summary(fields, (), summary, make_profile())
    assert not found.base_agrees
    assert found.caps == {"subtotal": DISAGREEMENT_CAP}


def test_a_line_that_does_not_tax_its_base_at_its_rate_caps_the_rate() -> None:
    fields = amounts(subtotal="100.00", vat_amount="7.00")
    found = cross_check_totals_vs_summary(fields, (), [row("20", "100.00", "7.00")], make_profile())
    assert found.vat_agrees and found.base_agrees
    assert not found.closes
    assert found.caps == {"vat_rate": DISAGREEMENT_CAP}


def test_a_line_missing_a_column_is_not_a_line_that_disagrees() -> None:
    fields = amounts(subtotal="100.00", vat_amount="20.00")
    summary = [row("20", None, "20.00")]
    assert cross_check_totals_vs_summary(fields, (), summary, make_profile()).agrees


def test_a_block_that_states_nothing_disagrees_with_nothing() -> None:
    summary = [row("20", "100.00", "20.00")]
    assert cross_check_totals_vs_summary({}, (), summary, make_profile()).agrees


def test_every_row_is_taxed_by_the_line_at_its_own_rate() -> None:
    summary = [row("7", "10.00", "0.70"), row("20", "100.00", "20.00")]
    items = [LineItem(vat_rate=Decimal("20")), LineItem(vat_rate=Decimal("7"))]
    charges = [Charge(type="SHIPPING", amount=Decimal("5.00"), vat_rate=Decimal("20"))]
    found = link_items_to_vat_lines(items, charges, summary)
    assert found.items == (1, 0)
    assert found.charges == (1,)
    assert found.findings == ()


def test_a_row_at_no_stated_rate_is_taxed_by_the_one_line_there_is() -> None:
    found = link_items_to_vat_lines([LineItem()], (), [row("20", "100.00", "20.00")])
    assert found.items == (0,)


def test_a_row_at_no_stated_rate_is_linked_to_nothing_where_there_are_several() -> None:
    summary = [row("7", "10.00", "0.70"), row("20", "100.00", "20.00")]
    assert link_items_to_vat_lines([LineItem()], (), summary).items == (None,)


def test_a_row_at_a_rate_no_line_charges_is_linked_to_nothing() -> None:
    found = link_items_to_vat_lines([LineItem(vat_rate=Decimal("5"))], (), [row("20", "1", "0.20")])
    assert found.items == (None,)
    assert found.findings == ()


def test_a_row_that_matches_two_lines_is_linked_to_neither_and_said_so() -> None:
    summary = [row("20", "10.00", "2.00"), row("20", "100.00", "20.00")]
    found = link_items_to_vat_lines([LineItem(vat_rate=Decimal("20"))], (), summary)
    assert found.items == (None,)
    finding = found.findings[0]
    assert (finding.severity, finding.code) == (Severity.WARNING, AMBIGUOUS)


def test_a_document_with_no_summary_links_nothing() -> None:
    assert link_items_to_vat_lines([LineItem(vat_rate=Decimal("20"))], (), ()).items == (None,)
