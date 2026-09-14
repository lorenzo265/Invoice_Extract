"""Each invariant: when it holds, when it is skipped, and what it says when it fails."""

from __future__ import annotations

import dataclasses
from decimal import Decimal

import pytest

from invoice_extractor.domain.findings import Severity
from invoice_extractor.domain.models import Charge, FieldResult, LineItem, VatSummaryRow
from invoice_extractor.validation.invariants import (
    INVARIANT_NAMES,
    check_all,
    line_items_sum,
    totals_reconcile,
    vat_rate_consistent,
)

CLEAN = {
    "subtotal": "490.00",
    "vat_rate": "20.00",
    "vat_amount": "98.00",
    "total_amount": "588.00",
}
ITEMS = (
    LineItem(part_number="ACM-1001", description="Hex bolt", net_amount=Decimal("60.00")),
    LineItem(part_number="ACM-2210", description="Bearing", net_amount=Decimal("154.00")),
    LineItem(part_number="ACM-3300", description="Bracket", net_amount=Decimal("276.00")),
)


def fields(**overrides: str | None) -> dict[str, FieldResult]:
    amounts = {**CLEAN, **overrides}
    return {
        name: FieldResult(
            name=name,
            value=None if text is None else Decimal(text),
            raw_text=text,
            evidence=None,
            valid=text is not None,
        )
        for name, text in amounts.items()
    }


def test_totals_reconcile_holds_within_a_cent() -> None:
    assert totals_reconcile(fields()) is None
    assert totals_reconcile(fields(total_amount="588.01")) is None


def test_totals_reconcile_reports_error_with_both_sides() -> None:
    finding = totals_reconcile(fields(total_amount="589.00"))
    assert finding is not None
    assert finding.severity is Severity.ERROR
    assert finding.code == "totals_reconcile"
    assert finding.field == "total_amount"
    assert finding.message == "490.00 + 98.00 = 588.00 but total_amount is 589.00"


def test_line_items_sum_holds_for_rows_that_add_up() -> None:
    assert line_items_sum(fields(), ITEMS) is None


def test_line_items_sum_reports_error_with_every_row() -> None:
    finding = line_items_sum(fields(subtotal="500.00"), ITEMS)
    assert finding is not None
    assert finding.severity is Severity.ERROR
    assert finding.field == "subtotal"
    assert finding.message == "60.00 + 154.00 + 276.00 = 490.00 but subtotal is 500.00"


def test_line_items_sum_warns_when_no_items() -> None:
    finding = line_items_sum(fields(), ())
    assert finding is not None
    assert finding.severity is Severity.WARNING
    assert finding.message == "line_items_sum skipped: line_items not found"
    assert finding.field is None


def test_vat_rate_consistent_quantizes_before_compare() -> None:
    # 333.33 x 19% is 63.3327 exactly; the invoice prints the rounded cent, 63.33.
    rounded = fields(subtotal="333.33", vat_rate="19.00", vat_amount="63.33")
    assert vat_rate_consistent(rounded) is None
    # The reported expectation is the quantized product, not its full precision.
    finding = vat_rate_consistent(fields(subtotal="333.33", vat_rate="19.00", vat_amount="99.00"))
    assert finding is not None
    assert finding.message == "19.00% x 333.33 = 63.33 but vat_amount is 99.00"


def test_vat_rate_consistent_reports_error_with_the_rate_applied() -> None:
    finding = vat_rate_consistent(fields(vat_amount="99.00", total_amount="589.00"))
    assert finding is not None
    assert finding.field == "vat_amount"
    assert finding.message == "20.00% x 490.00 = 98.00 but vat_amount is 99.00"


def test_missing_operand_yields_warning_not_error() -> None:
    finding = totals_reconcile(fields(total_amount=None))
    assert finding is not None
    assert finding.severity is Severity.WARNING
    assert finding.message == "totals_reconcile skipped: total_amount not found"
    assert finding.field == "total_amount"


@pytest.mark.parametrize("missing", ["subtotal", "vat_amount", "total_amount"])
def test_totals_reconcile_names_whichever_operand_is_missing(missing: str) -> None:
    finding = totals_reconcile(fields(**{missing: None}))
    assert finding is not None
    assert finding.message == f"totals_reconcile skipped: {missing} not found"


def test_line_items_sum_warns_when_the_subtotal_is_missing() -> None:
    finding = line_items_sum(fields(subtotal=None), ITEMS)
    assert finding is not None
    assert finding.message == "line_items_sum skipped: subtotal not found"


@pytest.mark.parametrize("missing", ["subtotal", "vat_rate", "vat_amount"])
def test_vat_rate_consistent_names_whichever_operand_is_missing(missing: str) -> None:
    finding = vat_rate_consistent(fields(**{missing: None}))
    assert finding is not None
    assert finding.message == f"vat_rate_consistent skipped: {missing} not found"


def test_a_field_that_is_not_a_decimal_counts_as_missing() -> None:
    not_a_number = fields()
    not_a_number["subtotal"] = FieldResult("subtotal", "many", "many", None, valid=False)
    finding = totals_reconcile(not_a_number)
    assert finding is not None
    assert finding.message == "totals_reconcile skipped: subtotal not found"


def test_check_all_preserves_name_order() -> None:
    broken = fields(subtotal="1.00", vat_rate="20.00", vat_amount="2.00", total_amount="99.00")
    assert tuple(finding.code for finding in check_all(broken, ITEMS)) == INVARIANT_NAMES


def test_check_all_drops_the_invariants_that_held() -> None:
    assert check_all(fields(), ITEMS) == ()


def test_line_items_sum_is_skipped_when_a_rows_amount_could_not_be_read() -> None:
    """A row nobody could read an amount off is a row this sum cannot be made of."""
    unreadable = (*ITEMS[:2], dataclasses.replace(ITEMS[2], net_amount=None))
    finding = line_items_sum(fields(), unreadable)
    assert finding is not None
    assert finding.severity is Severity.WARNING
    assert "skipped" in finding.message


def test_a_charge_the_document_carries_is_part_of_what_the_total_comes_to() -> None:
    carried = fields(total_amount="600.50")
    charges = (Charge(type="SHIPPING", amount=Decimal("12.50")),)
    assert totals_reconcile(carried, charges) is None
    assert totals_reconcile(carried) is not None, "and the same sum without it does not hold"


def test_a_charge_names_itself_in_the_sum_the_finding_prints() -> None:
    charges = (Charge(type="SHIPPING", amount=Decimal("12.50")),)
    finding = totals_reconcile(fields(), charges)
    assert finding is not None
    assert finding.message.startswith("490.00 + 12.50 + 98.00 = 600.50")


def test_what_is_taxed_is_the_net_and_the_charges_the_block_declared() -> None:
    charges = (
        Charge(type="SHIPPING", amount=Decimal("10.00")),
        Charge(type="OTHER", amount=Decimal("100.00"), declared=False),
    )
    taxed = fields(vat_amount="100.00")
    assert vat_rate_consistent(taxed, charges) is None


def test_a_document_at_more_than_one_rate_has_no_one_rate_to_check() -> None:
    """The check is `vat_equals_subtotal_times_rate`, and that is a single-rate document."""
    summary = (
        VatSummaryRow(rate=Decimal("7"), base=Decimal("100.00"), vat=Decimal("7.00")),
        VatSummaryRow(rate=Decimal("20"), base=Decimal("390.00"), vat=Decimal("78.00")),
    )
    finding = vat_rate_consistent(fields(vat_amount="85.00"), (), summary)
    assert finding is not None
    assert finding.severity is Severity.INFO
    assert finding.message.endswith("not applicable: the document is at more than one rate")


def test_a_document_at_one_rate_is_checked_against_it() -> None:
    summary = (VatSummaryRow(rate=Decimal("20"), base=Decimal("490.00"), vat=Decimal("98.00")),)
    assert vat_rate_consistent(fields(), (), summary) is None
