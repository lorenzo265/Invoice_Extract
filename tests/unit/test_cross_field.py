"""Do the document's values agree with each other, and what is not asked of which document."""

from __future__ import annotations

import dataclasses
from datetime import date
from decimal import Decimal

from conftest import make_profile
from invoice_extractor.domain.findings import Severity
from invoice_extractor.domain.models import FieldResult
from invoice_extractor.domain.parties import Party
from invoice_extractor.validation.cross_field import (
    CHECK_NAMES,
    bill_to_country_matches_customer_vat,
    credit_note_references_invoice,
    currency_agrees_across_families,
    customer_vat_differs_from_supplier,
    dates_in_order,
    invoice_number_in_filename,
    vat_prefix_matches_country,
)
from invoice_extractor.validation.facts import Facts

VALUES: dict[str, object] = {
    "invoice_number": "INV-2024-0042",
    "supply_date": date(2024, 3, 10),
    "invoice_date": date(2024, 3, 15),
    "due_date": date(2024, 4, 14),
    "supplier_vat_id": "GB312141377",
    "customer_vat_id": "GB987654321",
    "currency": "GBP",
}
BILLED = Party(name="Ashgrove Ltd", lines=("12 High Street", "Leeds LS1 4AB", "1 Test Street"))


def fields(**overrides: object) -> dict[str, FieldResult]:
    found = {**VALUES, **overrides}
    return {
        name: FieldResult(name, value, str(value), None, valid=True)  # type: ignore[arg-type]
        for name, value in found.items()
        if value is not None
    }


def facts(**changes: object) -> Facts:
    made: dict[str, object] = {
        "profile": make_profile(),
        "fields": fields(),
        "parties": {"bill_to": BILLED},
        "document_type": "invoice",
        "source_path": "corpus/0001_en-GB_classic_s7.pdf",
        "currency_basis": "GBP",
    }
    return Facts(**{**made, **changes})  # type: ignore[arg-type]  # a test names its own


def test_the_seven_checks_are_the_seven_the_specification_names() -> None:
    assert CHECK_NAMES == (
        "invoice_number_in_filename",
        "vat_prefix_matches_country",
        "dates_in_order",
        "currency_agrees_across_families",
        "customer_vat_differs_from_supplier",
        "bill_to_country_matches_customer_vat",
        "credit_note_references_invoice",
    )


def test_a_file_named_after_nothing_in_particular_claims_nothing() -> None:
    verdict = invoice_number_in_filename(facts())
    assert verdict.passed is None
    assert verdict.detail == "the file name claims no document"


def test_a_file_named_after_this_document_agrees_with_it() -> None:
    named = facts(source_path="inbox/INV-2024-0042.pdf")
    assert invoice_number_in_filename(named).passed


def test_a_file_named_after_another_document_is_worth_saying() -> None:
    named = facts(source_path="inbox/INV-2024-9999.pdf")
    verdict = invoice_number_in_filename(named)
    assert verdict.passed is False
    assert verdict.severity is Severity.WARNING


def test_a_document_with_no_number_is_not_asked_what_the_file_is_called() -> None:
    assert invoice_number_in_filename(facts(fields=fields(invoice_number=None))).passed is None


def test_the_supplier_registration_carries_its_countrys_prefix() -> None:
    assert vat_prefix_matches_country(facts()).passed
    wrong = facts(fields=fields(supplier_vat_id="FR312141377"))
    assert vat_prefix_matches_country(wrong).detail == "FR312141377 does not begin with GB"
    assert vat_prefix_matches_country(facts(fields=fields(supplier_vat_id=None))).passed is None


def test_the_dates_run_in_the_order_dates_run_in() -> None:
    assert dates_in_order(facts()).passed
    backwards = facts(fields=fields(due_date=date(2024, 1, 1)))
    verdict = dates_in_order(backwards)
    assert verdict.passed is False
    assert verdict.detail == "invoice_date 2024-03-15 is after due_date 2024-01-01"


def test_one_date_alone_cannot_be_out_of_order() -> None:
    alone = facts(fields=fields(supply_date=None, due_date=None))
    assert dates_in_order(alone).passed is None


def test_the_currency_is_the_one_the_amounts_add_up_in() -> None:
    assert currency_agrees_across_families(facts()).passed
    assert currency_agrees_across_families(facts(currency_basis="USD")).passed is False
    assert currency_agrees_across_families(facts(currency_basis=None)).passed is None
    assert currency_agrees_across_families(facts(fields=fields(currency=None))).passed is None


def test_one_registration_cannot_be_both_parties() -> None:
    assert customer_vat_differs_from_supplier(facts()).passed
    same = facts(fields=fields(customer_vat_id="GB 312141377"))
    assert customer_vat_differs_from_supplier(same).passed is False
    alone = facts(fields=fields(customer_vat_id=None))
    assert customer_vat_differs_from_supplier(alone).passed is None


def test_a_customer_registered_where_the_vendor_is_is_billed_there() -> None:
    assert bill_to_country_matches_customer_vat(facts()).passed
    elsewhere = facts(parties={"bill_to": dataclasses.replace(BILLED, lines=("12 High Street",))})
    assert bill_to_country_matches_customer_vat(elsewhere).passed is False


def test_a_customer_registered_elsewhere_is_not_asked_where_it_is_billed() -> None:
    abroad = facts(fields=fields(customer_vat_id="FR987654321"))
    assert bill_to_country_matches_customer_vat(abroad).passed is None
    assert bill_to_country_matches_customer_vat(facts(parties={})).passed is None


def test_a_vendor_whose_own_address_names_no_country_asks_nothing_of_the_customers() -> None:
    profile = dataclasses.replace(
        make_profile(),
        supplier=dataclasses.replace(make_profile().supplier, address_lines=()),
    )
    assert bill_to_country_matches_customer_vat(facts(profile=profile)).passed is None


def test_a_credit_note_says_what_it_credits() -> None:
    credit = facts(document_type="credit_note", fields={**fields(), **_reference("INV-2024-0001")})
    assert credit_note_references_invoice(credit).passed
    assert credit_note_references_invoice(facts()).passed is None
    silent = facts(document_type="credit_note")
    verdict = credit_note_references_invoice(silent)
    assert verdict.passed is False
    assert verdict.severity is Severity.WARNING


def _reference(number: str) -> dict[str, FieldResult]:
    return {"credit_reference": FieldResult("credit_reference", number, number, None, valid=True)}


def test_an_amount_is_never_mistaken_for_a_date() -> None:
    """`dates_in_order` reads dates, and a field holding something else is not one."""
    amounts = {**fields(), "invoice_date": FieldResult("invoice_date", Decimal(1), "1", None, True)}
    assert dates_in_order(facts(fields=amounts)).passed
