"""A credit note is the invoice it reverses, in the style the vendor writes them."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from invoice_forge.model import (
    Charge,
    ChargeType,
    CreditNoteStyle,
    Dates,
    Document,
    DocumentType,
    Identifiers,
    LineItem,
    Party,
    Payment,
    RoundingPolicy,
    as_credit_note,
)

RATE = Decimal("19")


def invoice() -> Document:
    party = Party("A Vendor Ltd", ("1 A Street", "AB1 2CD"), "GB123456789")
    return Document(
        type=DocumentType.INVOICE,
        profile_id="en-GB",
        language="en",
        currency="GBP",
        supplier=party,
        bill_to=party,
        identifiers=Identifiers("INV-1", "PO-1", "C-1"),
        dates=Dates(date(2024, 3, 15), date(2024, 4, 14)),
        items=(LineItem(1, "SKU-1", "A thing", Decimal("4"), "ea", Decimal("25.00"), RATE),),
        charges=(Charge(ChargeType.SHIPPING, Decimal("10.00"), RATE, declared=True),),
        payment=Payment("GB00 X", "ABCDGB2L001", "A Bank", "A Vendor Ltd", "Net 30"),
        rounding=RoundingPolicy.PER_LINE,
    )


def test_a_credit_note_references_the_invoice_it_reverses() -> None:
    note = as_credit_note(invoice(), "CN-9", CreditNoteStyle.NEGATIVE_AMOUNTS)
    assert note.type is DocumentType.CREDIT_NOTE
    assert note.identifiers.invoice_number == "CN-9"
    assert note.identifiers.credit_reference == "INV-1"


def test_negative_amounts_invert_every_row_and_charge() -> None:
    note = as_credit_note(invoice(), "CN-9", CreditNoteStyle.NEGATIVE_AMOUNTS)
    assert note.items[0].quantity == Decimal("-4")
    assert note.items[0].net_amount == Decimal("-100.00")
    assert note.charges[0].amount == Decimal("-10.00")
    assert note.totals.total_amount == -invoice().totals.total_amount


def test_credit_wording_leaves_the_amounts_positive() -> None:
    note = as_credit_note(invoice(), "CN-9", CreditNoteStyle.CREDIT_WORDING)
    assert note.items[0].quantity == Decimal("4")
    assert note.totals.total_amount == invoice().totals.total_amount


def test_the_invoice_it_was_made_from_is_untouched() -> None:
    original = invoice()
    as_credit_note(original, "CN-9", CreditNoteStyle.NEGATIVE_AMOUNTS)
    assert original.type is DocumentType.INVOICE
    assert original.items[0].quantity == Decimal("4")


def test_the_rates_a_document_carries_are_the_rates_of_its_vat_lines() -> None:
    assert invoice().vat_rates == (RATE,)
