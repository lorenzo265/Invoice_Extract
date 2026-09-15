"""Each invariant: when it holds, when it does not, and when it does not apply."""

from __future__ import annotations

from decimal import Decimal

from conftest import make_profile
from invoice_extractor.domain.findings import Severity
from invoice_extractor.domain.models import FieldResult, LineItem, VatSummaryRow
from invoice_extractor.domain.totals import Charge
from invoice_extractor.validation.facts import Facts
from invoice_extractor.validation.invariants import (
    INVARIANT_NAMES,
    document_type_matches_total_sign,
    line_items_sum_equals_subtotal,
    line_items_sum_equals_total_when_no_vat,
    line_items_vat_sum_equals_vat_total,
    line_totals_plus_charges_equal_grand_total,
    per_rate_vat_consistency,
    subtotal_plus_vat_equals_total,
    summary_base_sums_equal_subtotal,
    summary_vat_sums_equal_vat_total,
    vat_equals_subtotal_times_rate,
)

# One consistent document, in the vendor's own numbers: four rows at 20%, no charges.
CLEAN = {
    "subtotal": "490.00",
    "vat_rate": "20.00",
    "vat_amount": "98.00",
    "total_amount": "588.00",
}
ITEMS = (
    LineItem(description="Hex bolt", net_amount=Decimal("60.00"), vat_rate=Decimal("20")),
    LineItem(description="Bearing", net_amount=Decimal("154.00"), vat_rate=Decimal("20")),
    LineItem(description="Bracket", net_amount=Decimal("276.00"), vat_rate=Decimal("20")),
)
SUMMARY = (VatSummaryRow(rate=Decimal("20"), base=Decimal("490.00"), vat=Decimal("98.00")),)


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


def facts(**changes: object) -> Facts:
    """One document the arithmetic of which adds up, with whatever a test changes."""
    made: dict[str, object] = {
        "profile": make_profile(),
        "fields": fields(),
        "items": ITEMS,
        "summary": SUMMARY,
        "document_type": "invoice",
    }
    return Facts(**{**made, **changes})  # type: ignore[arg-type]  # a test names its own


def test_the_ten_invariants_are_the_ten_the_specification_names() -> None:
    assert INVARIANT_NAMES == (
        "subtotal_plus_vat_equals_total",
        "line_items_sum_equals_subtotal",
        "line_items_sum_equals_total_when_no_vat",
        "vat_equals_subtotal_times_rate",
        "per_rate_vat_consistency",
        "summary_base_sums_equal_subtotal",
        "summary_vat_sums_equal_vat_total",
        "line_totals_plus_charges_equal_grand_total",
        "line_items_vat_sum_equals_vat_total",
        "document_type_matches_total_sign",
    )


def test_a_document_that_adds_up_passes_every_one_of_them() -> None:
    every = (
        subtotal_plus_vat_equals_total,
        line_items_sum_equals_subtotal,
        vat_equals_subtotal_times_rate,
        per_rate_vat_consistency,
        summary_base_sums_equal_subtotal,
        summary_vat_sums_equal_vat_total,
        line_totals_plus_charges_equal_grand_total,
        line_items_vat_sum_equals_vat_total,
        document_type_matches_total_sign,
    )
    assert all(rule(facts()).passed for rule in every)


def test_the_total_is_the_net_and_the_tax_and_what_was_added() -> None:
    charged = facts(fields=fields(total_amount="600.50"), charges=(_shipping(),))
    assert subtotal_plus_vat_equals_total(charged).passed
    assert subtotal_plus_vat_equals_total(facts(charges=(_shipping(),))).passed is False


def test_a_sum_that_disagrees_names_both_sides_of_itself() -> None:
    verdict = subtotal_plus_vat_equals_total(facts(fields=fields(total_amount="600.00")))
    assert verdict.detail == "490.00 + 98.00 = 588.00 but total_amount is 600.00"
    assert verdict.severity is Severity.ERROR


def test_an_amount_the_document_does_not_carry_is_not_a_failure() -> None:
    verdict = subtotal_plus_vat_equals_total(facts(fields=fields(vat_amount=None)))
    assert verdict.passed is None
    assert verdict.detail == "vat_amount was not read"


def test_a_row_nobody_could_read_an_amount_off_is_a_sum_that_cannot_be_made() -> None:
    unreadable = (*ITEMS[:2], LineItem(description="Bracket"))
    assert line_items_sum_equals_subtotal(facts(items=unreadable)).passed is None


def test_the_rows_add_up_to_the_net_under_them() -> None:
    assert line_items_sum_equals_subtotal(facts()).passed
    assert line_items_sum_equals_subtotal(facts(fields=fields(subtotal=None))).passed is None
    assert line_items_sum_equals_subtotal(facts(fields=fields(subtotal="1.00"))).passed is False


def test_where_nothing_is_taxed_the_rows_are_what_is_owed() -> None:
    untaxed = facts(fields=fields(vat_amount="0.00", total_amount="490.00"))
    assert line_items_sum_equals_total_when_no_vat(untaxed).passed
    assert line_items_sum_equals_total_when_no_vat(facts()).passed is None
    nothing = facts(fields=fields(vat_amount=None))
    assert line_items_sum_equals_total_when_no_vat(nothing).detail == "vat_amount was not read"


def test_an_untaxed_document_missing_its_rows_is_not_asked() -> None:
    untaxed = facts(fields=fields(vat_amount="0.00", total_amount=None))
    assert line_items_sum_equals_total_when_no_vat(untaxed).passed is None


def test_what_is_taxed_is_the_net_and_the_charges_the_block_declared() -> None:
    charged = facts(fields=fields(vat_amount="100.00"), charges=(_shipping(Decimal("10.00")),))
    assert vat_equals_subtotal_times_rate(charged).passed


def test_a_document_at_more_than_one_rate_has_no_one_rate_to_multiply_by() -> None:
    several = (
        VatSummaryRow(rate=Decimal("7"), base=Decimal("100.00"), vat=Decimal("7.00")),
        VatSummaryRow(rate=Decimal("20"), base=Decimal("390.00"), vat=Decimal("78.00")),
    )
    verdict = vat_equals_subtotal_times_rate(facts(summary=several))
    assert verdict.passed is None
    assert "more than one rate" in verdict.detail


def test_a_rate_the_document_does_not_state_is_not_multiplied_by() -> None:
    assert vat_equals_subtotal_times_rate(facts(fields=fields(vat_rate=None))).passed is None


def test_every_line_of_the_summary_taxes_its_own_base() -> None:
    wrong = (VatSummaryRow(rate=Decimal("20"), base=Decimal("490.00"), vat=Decimal("1.00")),)
    assert per_rate_vat_consistency(facts()).passed
    assert per_rate_vat_consistency(facts(summary=wrong)).detail == "20% x 490.00 is not 1.00"


def test_a_summary_that_states_no_full_line_is_not_asked() -> None:
    partial = (VatSummaryRow(rate=Decimal("20")),)
    assert per_rate_vat_consistency(facts(summary=partial)).passed is None
    assert per_rate_vat_consistency(facts(summary=())).passed is None


def test_the_summary_is_charged_on_the_net_and_the_declared_charges() -> None:
    charged = facts(
        summary=(VatSummaryRow(rate=Decimal("20"), base=Decimal("500.00"), vat=Decimal("100.00")),),
        charges=(_shipping(Decimal("10.00")),),
    )
    assert summary_base_sums_equal_subtotal(charged).passed
    assert summary_base_sums_equal_subtotal(facts(summary=charged.summary)).passed is False


def test_a_document_with_no_summary_is_not_asked_what_it_adds_up_to() -> None:
    assert summary_base_sums_equal_subtotal(facts(summary=())).passed is None
    assert summary_vat_sums_equal_vat_total(facts(summary=())).passed is None
    assert summary_vat_sums_equal_vat_total(facts(fields=fields(vat_amount=None))).passed is None


def test_the_summary_comes_to_the_tax_the_block_states() -> None:
    assert summary_vat_sums_equal_vat_total(facts()).passed
    wrong = (VatSummaryRow(rate=Decimal("20"), base=Decimal("490.00"), vat=Decimal("1.00")),)
    assert summary_vat_sums_equal_vat_total(facts(summary=wrong)).passed is False


def test_the_rows_the_charges_and_the_tax_are_what_is_owed() -> None:
    charged = facts(fields=fields(total_amount="600.50"), charges=(_shipping(),))
    assert line_totals_plus_charges_equal_grand_total(charged).passed
    assert line_totals_plus_charges_equal_grand_total(facts(items=())).passed is None
    nothing = facts(fields=fields(total_amount=None))
    assert line_totals_plus_charges_equal_grand_total(nothing).passed is None


def test_each_row_taxed_at_its_own_rate_comes_to_the_tax() -> None:
    assert line_items_vat_sum_equals_vat_total(facts()).passed
    untaxed = (*ITEMS[:2], LineItem(description="Bracket", net_amount=Decimal("276.00")))
    assert line_items_vat_sum_equals_vat_total(facts(items=untaxed)).passed is None
    nothing = facts(fields=fields(vat_amount=None))
    assert line_items_vat_sum_equals_vat_total(nothing).passed is None


def test_the_tax_on_a_declared_charge_is_counted_with_the_rows() -> None:
    charged = facts(fields=fields(vat_amount="100.00"), charges=(_shipping(Decimal("10.00")),))
    assert line_items_vat_sum_equals_vat_total(charged).passed


def test_a_credit_note_gives_money_back_and_an_invoice_asks_for_it() -> None:
    credit = facts(fields=fields(total_amount="-588.00"), document_type="credit_note")
    assert document_type_matches_total_sign(credit).passed
    wrong = document_type_matches_total_sign(facts(document_type="credit_note"))
    assert wrong.passed is False
    assert wrong.severity is Severity.WARNING, "advisory: the sign is not what makes it one"


def test_a_document_that_asks_for_nothing_says_nothing_about_its_kind() -> None:
    nothing = facts(fields=fields(total_amount="0.00"))
    assert document_type_matches_total_sign(nothing).passed is None


def _shipping(amount: Decimal = Decimal("12.50")) -> Charge:
    return Charge(type="SHIPPING", amount=amount)
