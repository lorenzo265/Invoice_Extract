"""Stage 5 as one pass: fill in, then resolve, then report."""

from __future__ import annotations

from decimal import Decimal

from conftest import make_profile
from invoice_extractor.domain.models import FieldResult
from invoice_extractor.domain.rows import LineItem, VatSummaryRow
from invoice_extractor.domain.totals import Charge
from invoice_extractor.reconcile.amounts import FROM_SUMMARY, UNDECLARED
from invoice_extractor.reconcile.stage import reconcile


def amounts(**values: str) -> dict[str, FieldResult]:
    return {
        name: FieldResult(name, Decimal(value), value, None, valid=True)
        for name, value in values.items()
    }


def test_a_document_that_says_everything_is_left_as_it_says_it() -> None:
    fields = {
        **amounts(subtotal="100.00", vat_amount="20.00", vat_rate="20", total_amount="120.00"),
        "currency": FieldResult("currency", "GBP", "GBP", None, valid=True),
    }
    summary = [VatSummaryRow(rate=Decimal("20"), base=Decimal("100.00"), vat=Decimal("20.00"))]
    found = reconcile(fields, (), [LineItem(vat_rate=Decimal("20"))], summary, make_profile())
    assert found.fields == fields
    assert found.charges == ()
    assert found.currency == "GBP"
    assert tuple(item.vat_line for item in found.items) == (0,)
    assert found.findings == ()
    assert found.caps == {}


def test_what_a_document_leaves_out_is_filled_in_before_the_rest_is_judged() -> None:
    """The tax comes from the summary, and the charge from what is left over after it."""
    fields = amounts(subtotal="100.00", total_amount="125.00")
    summary = [VatSummaryRow(rate=Decimal("20"), base=Decimal("100.00"), vat=Decimal("20.00"))]
    found = reconcile(fields, (), (), summary, make_profile())
    assert found.fields["vat_amount"].value == Decimal("20.00")
    assert [(charge.type, charge.amount) for charge in found.charges] == [
        ("OTHER", Decimal("5.00"))
    ]
    assert [finding.code for finding in found.findings] == [FROM_SUMMARY, FROM_SUMMARY, UNDECLARED]


def test_a_declared_charge_is_carried_through_to_the_result() -> None:
    fields = amounts(subtotal="100.00", vat_amount="20.00", total_amount="125.00")
    declared = [Charge(type="SHIPPING", amount=Decimal("5.00"))]
    found = reconcile(fields, declared, (), (), make_profile())
    assert found.charges == tuple(declared)
    assert found.findings == ()
