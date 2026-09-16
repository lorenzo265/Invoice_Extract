"""The evidence file: every guess with its reason, and the worksheet of what was not one."""

from __future__ import annotations

from invoice_extractor.document.model import BBox, Zone
from invoice_extractor.drafting.assemble import Settings
from invoice_extractor.drafting.conventions import Convention
from invoice_extractor.drafting.evidence import evidence
from invoice_extractor.drafting.identity import Identity
from invoice_extractor.drafting.pairs import How, Mark, Pair
from invoice_extractor.drafting.seen import Seen
from invoice_extractor.drafting.shapes import Reading, Shape
from invoice_extractor.drafting.trace import Trace, missing
from invoice_extractor.drafting.vocabulary import Term

BOX = BBox(1.0, 2.0, 3.0, 4.0)
DEFAULT_FIELDS = ("invoice_number", "iban")


def seen(label: str, reading: Reading, mark: Mark = Mark.COLON, *terms: Term) -> Seen:
    pair = Pair(label, "v", 1, Zone(1, 3), Zone(1, 2), BOX, BOX, How.RIGHT, mark)
    return Seen(pair=pair, reading=reading, terms=terms)


def settings(*traces: Trace) -> Settings:
    return Settings(
        identity=Identity({}, "DE", "DE", r"\d{9}", traces),
        number_format=Convention({}, ()),
        date_formats=Convention([], ()),
        currencies=Convention([], ()),
        rates=Convention({}, ()),
    )


def test_placed_fields_and_missing_ones_are_told_apart_by_the_defaults() -> None:
    number = Term("de", "header_labels", "invoice_number", "Rechnungs-Nr.")
    read = evidence(
        "a.pdf",
        "de-DE",
        "de",
        (),
        settings(),
        [seen("Rechnungs-Nr.", Reading(Shape.IDENTIFIER), Mark.COLON, number)],
        DEFAULT_FIELDS,
    )
    assert [one.field for one in read.placed] == ["invoice_number"]
    assert read.missing == ("iban",)


def test_placeholders_are_the_traces_whose_value_is_one() -> None:
    read = evidence("a.pdf", "draft", "und", (), settings(missing("country", "a code")), [], ())
    assert read.placeholders == ("country",)


def test_the_worksheet_lists_unnamed_pairs_with_a_colon_or_a_strong_shape() -> None:
    read = evidence(
        "a.pdf",
        "draft",
        "und",
        (),
        settings(),
        [
            seen("UID-Nummer", Reading(Shape.VAT_ID, ("AT",))),
            seen("Hardware", Reading(Shape.TEXT), Mark.NONE),
            seen("Deutschland", Reading(Shape.DATE, ("dd.mm.yyyy",)), Mark.NONE),
            seen(
                "Rechnungs-Nr.",
                Reading(Shape.IDENTIFIER),
                Mark.COLON,
                Term("de", "header_labels", "invoice_number", "x"),
            ),
        ],
        DEFAULT_FIELDS,
    )
    assert [one.pair.label for one in read.unmapped] == ["UID-Nummer", "Deutschland"]


def test_the_file_written_carries_every_section_a_person_reads() -> None:
    heading = Term("de", "party_headings", "bill_to", "Rechnungsanschrift")
    read = evidence(
        "a.pdf",
        "de-DE",
        "de",
        (("de", 5),),
        settings(Trace("country", "DE", "why")),
        [seen("Rechnungsanschrift", Reading(Shape.TEXT), Mark.NONE, heading)],
        DEFAULT_FIELDS,
    )
    written = read.to_dict()
    assert written["language"] == {"chosen": "de", "votes": [["de", 5]]}
    assert written["settings"] == [
        {"key": "country", "value": "DE", "reason": "why", "page": None, "zone": None, "bbox": None}
    ]
    assert written["printed"]["parties"] == [
        {"entry": "bill_to", "label": "Rechnungsanschrift", "page": 1, "zone": "r1c2", "x": 1.0}
    ]
    assert written["missing"] == ["invoice_number", "iban"]
    assert written["unmapped"] == []


def test_a_placed_field_records_where_and_how_it_was_read() -> None:
    number = Term("de", "header_labels", "invoice_number", "Rechnungs-Nr.")
    read = evidence(
        "a.pdf",
        "de-DE",
        "de",
        (),
        settings(),
        [seen("Rechnungs-Nr.", Reading(Shape.IDENTIFIER), Mark.COLON, number)],
        DEFAULT_FIELDS,
    )
    assert read.placed[0].to_dict() == {
        "field": "invoice_number",
        "label": "Rechnungs-Nr.",
        "lexicon": ["de: header_labels.invoice_number"],
        "value": "v",
        "shape": "identifier",
        "how": "right",
        "page": 1,
        "zone": "r1c3",
        "bbox": [1.0, 2.0, 3.0, 4.0],
    }
