"""Which kind of document this is: an invoice, or the credit note that reverses one."""

from __future__ import annotations

import dataclasses

from conftest import make_document, make_profile
from invoice_extractor.extraction.classify import DocumentType, classify_document
from invoice_extractor.profile.schema import DocumentTypes

TITLES = DocumentTypes(
    invoice_titles=("RECHNUNG",),
    credit_note_titles=("GUTSCHRIFT",),
    credit_reference_labels=("zu Rechnung",),
)


def page(*texts: str) -> object:
    return make_document(
        [
            (1, text, 56.0, 60.0 + index * 14, 300.0, 72.0 + index * 14)
            for index, text in enumerate(texts)
        ]
    )


def naming(titles: DocumentTypes) -> object:
    return dataclasses.replace(make_profile(), document_types=titles)


def test_a_page_that_says_nothing_about_it_is_an_invoice() -> None:
    assert classify_document(page("Nordlicht GmbH"), naming(TITLES)) is DocumentType.INVOICE


def test_a_page_titled_with_the_vendors_word_for_one_is_an_invoice() -> None:
    assert classify_document(page("RECHNUNG"), naming(TITLES)) is DocumentType.INVOICE


def test_a_page_titled_with_the_vendors_word_for_a_credit_note_is_one() -> None:
    assert classify_document(page("GUTSCHRIFT"), naming(TITLES)) is DocumentType.CREDIT_NOTE


def test_a_page_citing_the_invoice_it_reverses_is_a_credit_note() -> None:
    document = page("RECHNUNG", "zu Rechnung RE-2024-0042")
    assert classify_document(document, naming(TITLES)) is DocumentType.CREDIT_NOTE


def test_a_vendor_that_names_no_credit_note_never_prints_one() -> None:
    bare = DocumentTypes(
        invoice_titles=("RECHNUNG",), credit_note_titles=(), credit_reference_labels=()
    )
    assert classify_document(page("GUTSCHRIFT"), naming(bare)) is DocumentType.INVOICE
