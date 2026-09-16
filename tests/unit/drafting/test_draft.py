"""One document, read against the bundled vendors, as a draft profile — built in memory."""

from __future__ import annotations

from conftest import line, make_page
from invoice_extractor.document.model import Document, TextLine
from invoice_extractor.drafting.draft import FALLBACK_ID, draft, known_ids
from invoice_extractor.profile.registry import ProfileRegistry


def document(*lines: TextLine) -> Document:
    return Document(pages=(make_page(1, lines),), source_path="fake.pdf")


def german() -> Document:
    return document(
        line("Nordlicht GmbH", 50.0, 50.0),
        line("Am Hafen 60", 50.0, 62.0),
        line("USt-IdNr.: DE879668745", 50.0, 74.0),
        line("RECHNUNG", 400.0, 50.0),
        line("Rechnungsnummer: RG-2024-1", 400.0, 80.0),
        line("Rechnungsdatum: 14.06.2024", 400.0, 92.0),
        line("Währung: EUR", 400.0, 104.0),
        line("Rechnungsanschrift", 50.0, 200.0),
        line("Rheinwerk Elektronik GmbH", 50.0, 212.0),
        line("Nettosumme: 1.234,56", 400.0, 700.0),
        line("USt-Satz: 19 %", 400.0, 712.0),
        line("Gesamtbetrag: 1.469,13", 400.0, 724.0),
    )


def test_a_german_page_is_drafted_as_a_german_profile_named_after_its_country() -> None:
    drafted = draft(german(), ProfileRegistry())
    assert drafted.id == "de-DE"
    assert drafted.profile["language"] == "de"
    assert drafted.profile["number_format"] == {
        "decimal_separator": ",",
        "thousands_separators": ["."],
    }
    assert drafted.profile["date_formats"] == ["dd.mm.yyyy"]
    assert drafted.profile["currencies"] == ["EUR"]
    assert drafted.profile["vat"] == {
        "rates": {"standard": "19"},
        "id_prefix": "DE",
        "id_pattern": r"\d{9}",
    }
    assert drafted.profile["fields"] == {
        "supplier_vat_id": {"zones": ["r1c1"]},
        "invoice_number": {"zones": ["r1c3"]},
        "invoice_date": {"zones": ["r1c3"]},
        "currency": {"zones": ["r1c3"]},
        "subtotal": {"zones": ["r3c3"]},
        "vat_rate": {"zones": ["r3c3"]},
        "total_amount": {"zones": ["r3c3"]},
    }
    assert drafted.profile["parties"] == {"bill_to": {"zones": ["r1c1"]}}


def test_the_evidence_names_the_language_vote_and_what_the_page_did_not_print() -> None:
    drafted = draft(german(), ProfileRegistry())
    assert drafted.evidence.votes[0][0] == "de"
    assert "iban" in drafted.evidence.missing
    assert drafted.evidence.placeholders == ()


def test_a_name_and_a_language_given_by_the_person_are_taken_as_given() -> None:
    drafted = draft(german(), ProfileRegistry(), profile_id="dell-DE", language="xx")
    assert drafted.id == "dell-DE"
    assert drafted.profile["lexicon"] == "xx"
    assert drafted.profile["fields"]["invoice_number"] == {
        "zones": ["r1c3"],
        "labels": ["Rechnungsnummer"],
    }


def test_a_page_that_says_too_little_is_named_draft_and_left_undetermined() -> None:
    drafted = draft(document(line("Something: else", 50.0, 50.0)), ProfileRegistry())
    assert drafted.id == FALLBACK_ID
    assert drafted.profile["language"] == "und"
    assert "country" in drafted.evidence.placeholders


def test_every_country_the_registry_knows_has_one_id_shape() -> None:
    shapes = known_ids(ProfileRegistry())
    assert len({shape.country for shape in shapes}) == len(shapes)
    assert next(shape for shape in shapes if shape.country == "AT").prefix == "ATU"
