"""The supplier as the page prints it, and the country its VAT id says."""

from __future__ import annotations

import re

from conftest import line, make_page
from invoice_extractor.document.model import Document, TextLine
from invoice_extractor.drafting.identity import UNKNOWN_COUNTRY, identity, pattern_of
from invoice_extractor.drafting.seen import observe
from invoice_extractor.drafting.shapes import KnownId
from invoice_extractor.drafting.trace import PLACEHOLDER
from invoice_extractor.drafting.vocabulary import from_lexicons

LEXICONS = {
    "de": {
        "header_labels": {
            "supplier_vat_id": ["USt-IdNr."],
            "customer_vat_id": ["USt-IdNr. des Kunden"],
        }
    }
}
KNOWN = (KnownId("DE", "DE", re.compile(r"\d{9}")), KnownId("AT", "ATU", re.compile(r"\d{8}")))


def document(*lines: TextLine) -> Document:
    return Document(pages=(make_page(1, lines),), source_path="fake.pdf")


def letterhead(*extra: TextLine) -> Document:
    """A name, two address lines and a labelled id at the margin, then a gap, then more."""
    return document(
        line("Nordlicht GmbH", 50.0, 50.0),
        line("Am Hafen 60", 50.0, 62.0),
        line("Leipzig", 50.0, 74.0),
        line("USt-IdNr.: DE879668745", 50.0, 86.0),
        line("Rechnungsanschrift", 50.0, 200.0),
        *extra,
    )


def test_the_letterhead_gives_the_name_and_the_address_without_its_labelled_lines() -> None:
    page = letterhead()
    read_identity = identity(page, observe(page, from_lexicons(LEXICONS), KNOWN), KNOWN)
    assert read_identity.supplier["name"] == "Nordlicht GmbH"
    assert read_identity.supplier["address_lines"] == ["Am Hafen 60", "Leipzig"]
    assert read_identity.supplier["aliases"] == []


def test_the_labelled_supplier_id_names_the_country_and_its_known_pattern() -> None:
    page = letterhead()
    read_identity = identity(page, observe(page, from_lexicons(LEXICONS), KNOWN), KNOWN)
    assert read_identity.supplier["vat_id"] == "DE879668745"
    assert (read_identity.country, read_identity.id_prefix) == ("DE", "DE")
    assert read_identity.id_pattern == r"\d{9}"
    assert any("names as the supplier's VAT id" in trace.reason for trace in read_identity.traces)


def test_an_unlabelled_known_id_is_taken_unless_it_is_labelled_as_the_customer_s() -> None:
    page = document(
        line("UID: ATU67706955", 50.0, 50.0),
        line("USt-IdNr. des Kunden: DE139099603", 360.0, 50.0),
    )
    read_identity = identity(page, observe(page, from_lexicons(LEXICONS), KNOWN), KNOWN)
    assert read_identity.supplier["vat_id"] == "ATU67706955"
    assert read_identity.country == "AT"
    assert "shaped like a AT VAT id" in read_identity.traces[2].reason


def test_a_supplier_id_of_a_country_no_profile_knows_has_its_pattern_read_off_it() -> None:
    page = document(line("USt-IdNr.: CHE-123.456.789", 50.0, 50.0))
    read_identity = identity(page, observe(page, from_lexicons(LEXICONS), KNOWN), KNOWN)
    assert read_identity.supplier["vat_id"] == "CHE-123.456.789"
    assert (read_identity.country, read_identity.id_prefix) == ("CH", "CH")
    assert read_identity.id_pattern == r"[A-Z]\-\d{3}\.\d{3}\.\d{3}"


def test_a_page_with_no_id_at_all_leaves_placeholders_that_name_themselves() -> None:
    page = document(line("Nordlicht GmbH", 50.0, 50.0))
    read_identity = identity(page, observe(page, from_lexicons(LEXICONS), KNOWN), KNOWN)
    assert read_identity.supplier["vat_id"] == PLACEHOLDER
    assert read_identity.country == UNKNOWN_COUNTRY
    assert read_identity.id_pattern == PLACEHOLDER
    assert {trace.key for trace in read_identity.traces if trace.is_placeholder} == {
        "supplier.address_lines",
        "supplier.vat_id",
        "country",
        "vat.id_pattern",
    }


def test_a_page_with_no_gap_under_the_letterhead_reads_its_first_lines() -> None:
    page = document(*(line(f"Line {index}", 50.0, 50.0 + 12.0 * index) for index in range(8)))
    read_identity = identity(page, (), KNOWN)
    assert read_identity.supplier["name"] == "Line 0"
    assert read_identity.supplier["address_lines"] == ["Line 1", "Line 2", "Line 3"]


def test_an_empty_document_leaves_the_supplier_to_fill_in() -> None:
    empty = Document(pages=(make_page(1, ()),), source_path="empty.pdf")
    read_identity = identity(empty, (), KNOWN)
    assert read_identity.supplier["name"] == PLACEHOLDER
    assert (
        identity(Document(pages=(), source_path="none.pdf"), (), KNOWN).supplier["name"]
        == PLACEHOLDER
    )


def test_a_pattern_read_off_an_id_reads_exactly_that_shape() -> None:
    assert pattern_of("12345678") == r"\d{8}"
    assert pattern_of("B12345678") == r"[A-Z]\d{8}"
    assert pattern_of("7P585117668") == r"\d[A-Z]\d{9}"
    assert pattern_of("a1") == "[a-z]\\d"
    assert re.fullmatch(pattern_of("123.456"), "987.654")
