"""The normalised value the truth records for each printed thing."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from invoice_forge.fields import LABELLED_FIELDS
from invoice_forge.lexicon.loader import load_lexicon
from invoice_forge.model import (
    Dates,
    Document,
    DocumentType,
    Identifiers,
    LineItem,
    Party,
    Payment,
    RoundingPolicy,
)
from invoice_forge.profiles.loader import load_profile
from invoice_forge.render.totals import headline_rate
from invoice_forge.sample.catalogue import load_catalogue
from invoice_forge.sample.sampler import SampleRequest, sample_document
from invoice_forge.truth.values import field_values

RATE = Decimal("19")


def sampled() -> Document:
    profile = load_profile("de-DE")
    lexicon = load_lexicon(profile.lexicon)
    catalogue = load_catalogue(profile.lexicon)
    return sample_document(SampleRequest(profile, lexicon, catalogue, 3))


def bare(**changes: object) -> Document:
    party = Party("A Vendor Ltd", ("1 A Street",), None)
    return Document(
        type=DocumentType.INVOICE,
        profile_id="en-GB",
        language="en",
        currency="GBP",
        supplier=party,
        bill_to=party,
        identifiers=Identifiers("INV-1", "PO-1", "C-1"),
        dates=Dates(date(2024, 3, 15), date(2024, 4, 14)),
        items=(),
        charges=(),
        payment=Payment("GB00 X", "ABCDGB2L001", "A Bank", "A Vendor Ltd", "Net 30"),
        rounding=RoundingPolicy.PER_LINE,
    )


def test_every_value_is_a_string_and_every_name_is_canonical() -> None:
    document = sampled()
    values = field_values(document, headline_rate(document.totals))
    assert set(values) <= set(LABELLED_FIELDS)
    assert all(isinstance(value, str) for value in values.values())


def test_dates_are_recorded_in_iso_8601() -> None:
    document = sampled()
    values = field_values(document, None)
    assert values["invoice_date"] == document.dates.invoice_date.isoformat()
    assert values["due_date"] == document.dates.due_date.isoformat()


def test_a_vat_id_is_recorded_as_letters_and_digits_only() -> None:
    spaced = Party("A Vendor Ltd", ("1 A Street",), "de 018 159/083")
    document = bare()
    values = field_values(
        Document(**{**{f: getattr(document, f) for f in Document.__slots__}, "supplier": spaced}),
        None,
    )
    assert values["supplier_vat_id"] == "DE018159083"


def test_a_party_without_a_vat_id_records_none_at_all() -> None:
    assert "supplier_vat_id" not in field_values(bare(), None)
    assert "customer_vat_id" not in field_values(bare(), None)


def test_a_date_the_document_does_not_carry_is_absent() -> None:
    assert "supply_date" not in field_values(bare(), None)


def test_a_document_with_no_rate_records_no_rate() -> None:
    assert "vat_rate" not in field_values(bare(), None)


def test_a_document_with_a_rate_records_it_plainly() -> None:
    assert field_values(bare(), Decimal("19"))["vat_rate"] == "19"


def test_the_amounts_are_recorded_without_separators_or_currency() -> None:
    document = sampled()
    values = field_values(document, None)
    assert values["total_amount"] == str(document.totals.total_amount)
    assert "," not in values["subtotal"]


def test_the_payment_terms_are_recorded_as_the_sentence_alone() -> None:
    assert field_values(bare(), None)["payment_terms"] == "Net 30"


def test_a_row_records_every_column_the_extractor_reads() -> None:
    from invoice_forge.truth.values import item_row

    item = LineItem(1, "SKU-1", "A thing", Decimal("2"), "ea", Decimal("10.00"), RATE)
    row = item_row(item, {})
    assert row["sku"] == "SKU-1"
    assert row["quantity"] == "2"
    assert row["unit_price"] == "10.00"
    assert row["net_amount"] == "20.00"
    assert row["cells"] == {}
