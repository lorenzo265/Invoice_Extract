"""Every lexicon at once: exact lookups, language votes, and what a lexicon file may lack."""

from __future__ import annotations

import json
from pathlib import Path

from invoice_extractor.drafting.vocabulary import Term, elect, fold, from_lexicons, read_vocabulary

GERMAN = {
    "header_labels": {"invoice_number": ["Rechnungs-Nr.", "Rechnungsnummer"], "iban": ["IBAN"]},
    "document_titles": {"invoice": ["RECHNUNG"]},
    "section_headings": ["Hardware"],
    "months": ["Januar", "Juni"],
    "month_abbreviations": ["Jan", "Jun"],
    "amount_in_words": {"units": ["null"]},
}
DUTCH = {
    "header_labels": {"invoice_date": ["Datum"], "invoice_number": ["Factuurnummer"]},
    "months": ["juni"],
}


def vocabulary() -> object:
    return from_lexicons({"de": GERMAN, "nl": DUTCH})


def test_a_label_is_found_whatever_its_case_and_punctuation() -> None:
    found = from_lexicons({"de": GERMAN}).lookup("rechnungs nr")
    assert found == (Term("de", "header_labels", "invoice_number", "Rechnungs-Nr."),)


def test_a_label_is_never_found_inside_a_longer_word() -> None:
    """`IBAN` inside `Citibank` is the detector's known false positive; a draft has none."""
    assert from_lexicons({"de": GERMAN}).lookup("Citibank") == ()


def test_a_plain_list_entry_is_a_term_with_no_key() -> None:
    (term,) = from_lexicons({"de": GERMAN}).lookup("Hardware")
    assert term.name == "section_headings"


def test_months_of_every_language_are_folded_together() -> None:
    read = from_lexicons({"de": GERMAN, "nl": DUTCH})
    assert {"juni", "jan"} <= read.months
    assert read.languages == ("de", "nl")
    assert read.knows("nl") and not read.knows("fr")


def test_the_election_counts_distinct_entries_per_language_and_breaks_ties_by_name() -> None:
    matched = [
        Term("nl", "header_labels", "invoice_date", "Datum"),
        Term("nl", "header_labels", "invoice_date", "Datum"),
        Term("de", "header_labels", "invoice_number", "Rechnungs-Nr."),
        Term("de", "header_labels", "invoice_number", "Rechnungsnummer"),
        Term("de", "document_titles", "invoice", "RECHNUNG"),
        Term("cs", "document_titles", "invoice", "FAKTURA"),
    ]
    assert elect(matched) == (("de", 2), ("cs", 1), ("nl", 1))


def test_folding_keeps_accented_letters_and_digits_and_drops_the_rest() -> None:
    assert fold("Číslo faktury: 12") == "číslofaktury12"


def test_a_directory_of_lexicons_is_read_by_file_stem(tmp_path: Path) -> None:
    (tmp_path / "de.json").write_text(json.dumps(GERMAN), encoding="utf-8")
    (tmp_path / "broken.json").write_text("[]", encoding="utf-8")
    read = read_vocabulary(tmp_path)
    assert read.languages == ("broken", "de")
    assert read.lookup("RECHNUNG")[0].language == "de"


def test_an_entry_that_is_not_a_list_of_strings_is_ignored() -> None:
    read = from_lexicons({"xx": {"header_labels": {"iban": "IBAN"}, "months": "Juni"}})
    assert read.lookup("IBAN") == ()
    assert read.months == frozenset()
