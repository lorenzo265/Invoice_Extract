"""The overlay a draft writes: zones where labels sat, and labels of another language."""

from __future__ import annotations

from invoice_extractor.document.model import BBox, Zone
from invoice_extractor.drafting.assemble import (
    Settings,
    assemble,
    default_field_names,
    fields,
    parties,
)
from invoice_extractor.drafting.conventions import Convention
from invoice_extractor.drafting.identity import Identity
from invoice_extractor.drafting.pairs import How, Mark, Pair
from invoice_extractor.drafting.seen import Seen
from invoice_extractor.drafting.shapes import Reading, Shape
from invoice_extractor.drafting.vocabulary import Term

BOX = BBox(0.0, 0.0, 10.0, 10.0)
DEFAULT_FIELDS = ("invoice_number", "invoice_date", "subtotal")


def seen(label: str, zone: Zone, label_zone: Zone, *terms: Term) -> Seen:
    pair = Pair(label, "x", 1, zone, label_zone, BOX, BOX, How.BESIDE, Mark.COLON)
    return Seen(pair=pair, reading=Reading(Shape.TEXT), terms=terms)


def test_a_field_gets_every_zone_its_label_was_found_in_once() -> None:
    number = Term("de", "header_labels", "invoice_number", "Rechnungs-Nr.")
    drafted = fields(
        [
            seen("Rechnungs-Nr.", Zone(1, 3), Zone(1, 2), number),
            seen("Rechnungs-Nr.", Zone(1, 3), Zone(1, 2), number),
            seen("Rechnungs-Nr.", Zone(2, 3), Zone(2, 2), number),
        ],
        "de",
        DEFAULT_FIELDS,
    )
    assert drafted == {"invoice_number": {"zones": ["r1c3", "r2c3"]}}


def test_a_label_only_another_language_spells_is_added_to_the_field() -> None:
    english = Term("en", "header_labels", "invoice_number", "Invoice No.")
    drafted = fields([seen("Invoice No.", Zone(1, 3), Zone(1, 3), english)], "de", DEFAULT_FIELDS)
    assert drafted == {"invoice_number": {"zones": ["r1c3"], "labels": ["Invoice No."]}}


def test_a_totals_label_places_the_field_of_the_same_name() -> None:
    subtotal = Term("de", "totals_labels", "subtotal", "Nettosumme")
    drafted = fields([seen("Nettosumme", Zone(3, 3), Zone(3, 3), subtotal)], "de", DEFAULT_FIELDS)
    assert drafted == {"subtotal": {"zones": ["r3c3"]}}


def test_an_entry_the_defaults_declare_no_field_for_is_left_to_the_evidence() -> None:
    column = Term("de", "column_headers", "quantity", "Menge")
    reference = Term("de", "header_labels", "our_reference", "Unser Zeichen")
    drafted = fields(
        [
            seen("Menge", Zone(2, 2), Zone(2, 2), column),
            seen("Unser Zeichen", Zone(1, 3), Zone(1, 3), reference),
        ],
        "de",
        DEFAULT_FIELDS,
    )
    assert drafted == {}


def test_a_party_block_gets_the_zone_its_heading_sat_in() -> None:
    heading = Term("de", "party_headings", "bill_to", "Rechnungsanschrift")
    drafted = parties([seen("Rechnungsanschrift", Zone(2, 1), Zone(1, 1), heading)], "de")
    assert drafted == {"bill_to": {"zones": ["r1c1"]}}


def test_the_overlay_carries_the_settings_in_the_documented_order() -> None:
    settings = Settings(
        identity=Identity({"name": "X"}, "DE", "DE", r"\d{9}", ()),
        number_format=Convention({"decimal_separator": ","}, ()),
        date_formats=Convention(["dd.mm.yyyy"], ()),
        currencies=Convention(["EUR"], ()),
        rates=Convention({"standard": "19"}, ()),
    )
    overlay = assemble("de-DE", "de", settings, [], DEFAULT_FIELDS)
    assert list(overlay) == [
        "id",
        "language",
        "country",
        "lexicon",
        "number_format",
        "date_formats",
        "currencies",
        "vat",
        "supplier",
        "fields",
        "parties",
    ]
    assert overlay["vat"] == {
        "rates": {"standard": "19"},
        "id_prefix": "DE",
        "id_pattern": r"\d{9}",
    }
    assert overlay["lexicon"] == "de"


def test_the_default_field_names_are_read_off_the_defaults_file() -> None:
    assert default_field_names({"fields": {"iban": {}, "currency": {}}}) == ("iban", "currency")
    assert default_field_names({}) == ()
