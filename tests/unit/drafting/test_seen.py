"""Pairs, shapes and terms met in one record, and the language they elect."""

from __future__ import annotations

import re

from conftest import line, make_page
from invoice_extractor.document.model import Document, TextLine
from invoice_extractor.drafting.seen import UNDETERMINED, language_of, observe, votes
from invoice_extractor.drafting.shapes import KnownId, Shape
from invoice_extractor.drafting.vocabulary import from_lexicons

LEXICONS = {
    "de": {
        "header_labels": {"invoice_date": ["Datum"], "invoice_number": ["Rechnungs-Nr."]},
        "totals_labels": {"total_amount": ["Gesamtbetrag"]},
        "document_titles": {"invoice": ["RECHNUNG"]},
    },
    "nl": {"header_labels": {"invoice_date": ["Datum"], "due_date": ["Vervaldatum"]}},
}
KNOWN = (KnownId("DE", "DE", re.compile(r"\d{9}")),)


def document(*lines: TextLine) -> Document:
    return Document(pages=(make_page(1, lines),), source_path="fake.pdf")


def german() -> Document:
    return document(
        line("RECHNUNG", 360.0, 50.0),
        line("Rechnungs-Nr.: RG-1", 360.0, 80.0),
        line("Datum: 14.06.2024", 360.0, 92.0),
        line("Gesamtbetrag: 1.234,56", 400.0, 700.0),
    )


def test_each_pair_is_observed_with_its_shape_and_its_terms() -> None:
    seen = observe(german(), from_lexicons(LEXICONS), KNOWN)
    by_label = {one.pair.label: one for one in seen}
    assert by_label["Datum"].reading.shape is Shape.DATE
    assert {term.language for term in by_label["Datum"].terms} == {"de", "nl"}
    assert by_label["Gesamtbetrag"].names("de") == ("totals_labels.total_amount",)


def test_a_label_two_languages_spell_names_the_entry_of_the_page_language() -> None:
    seen = observe(german(), from_lexicons(LEXICONS), KNOWN)
    datum = next(one for one in seen if one.pair.label == "Datum")
    assert datum.names("de") == ("header_labels.invoice_date",)
    assert datum.names("nl") == ("header_labels.invoice_date",)


def test_a_label_no_entry_of_the_page_language_spells_falls_back_to_any_language() -> None:
    seen = observe(
        document(line("Vervaldatum: 28.06.2024", 360.0, 80.0)), from_lexicons(LEXICONS), KNOWN
    )
    assert seen[0].names("de") == ("header_labels.due_date",)


def test_votes_count_the_title_standing_alone_at_the_top_of_the_page() -> None:
    vocabulary = from_lexicons(LEXICONS)
    page = german()
    counted = votes(page, observe(page, vocabulary, KNOWN), vocabulary)
    assert counted == (("de", 4), ("nl", 1))


def test_the_page_language_is_the_most_voted_lexicon_past_the_floor() -> None:
    assert language_of((("de", 3), ("nl", 1)), None, from_lexicons(LEXICONS)) == ("de", False)


def test_too_few_votes_leave_the_language_undetermined_and_a_lexicon_to_write() -> None:
    assert language_of((("de", 2),), None, from_lexicons(LEXICONS)) == (UNDETERMINED, True)
    assert language_of((), None, from_lexicons(LEXICONS)) == (UNDETERMINED, True)


def test_a_declared_language_wins_and_says_whether_a_lexicon_speaks_it() -> None:
    assert language_of((("de", 9),), "nl", from_lexicons(LEXICONS)) == ("nl", False)
    assert language_of((("de", 9),), "he", from_lexicons(LEXICONS)) == ("he", True)
