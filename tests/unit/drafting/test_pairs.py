"""Label and value pairs, found from a colon and from where things sit — never from words."""

from __future__ import annotations

from conftest import line, make_page
from invoice_extractor.document.model import Document, TextLine
from invoice_extractor.drafting.pairs import How, Mark, could_be_a_label, harvest


def document(*lines: TextLine) -> Document:
    return Document(pages=(make_page(1, lines),), source_path="fake.pdf")


def test_a_label_and_its_value_in_one_run_of_text_are_one_pair() -> None:
    (pair,) = harvest(document(line("Rechnungs-Nr.: RG-2024-1", 360.0, 80.0)))
    assert (pair.label, pair.value) == ("Rechnungs-Nr.", "RG-2024-1")
    assert pair.how is How.RIGHT
    assert pair.mark is Mark.COLON


def test_a_label_alone_takes_the_nearest_thing_beside_it_on_the_same_line() -> None:
    (pair,) = harvest(document(line("Datum:", 360.0, 80.0), line("14.06.2024", 480.0, 80.0)))
    assert (pair.label, pair.value, pair.how) == ("Datum", "14.06.2024", How.BESIDE)


def test_a_label_alone_with_nothing_beside_it_takes_the_line_under_it() -> None:
    (pair,) = harvest(document(line("Datum:", 360.0, 80.0), line("14.06.2024", 360.0, 92.0)))
    assert (pair.value, pair.how) == ("14.06.2024", How.BELOW)


def test_the_pair_carries_the_value_zone_not_the_label_zone() -> None:
    """The engine's candidate is the value line, so its zone is what a profile declares."""
    (pair,) = harvest(document(line("Datum:", 300.0, 80.0), line("14.06.2024", 500.0, 80.0)))
    assert pair.label_zone.name == "r1c2"
    assert pair.zone.name == "r1c3"


def test_a_short_line_without_a_colon_is_a_label_only_by_position_and_says_so() -> None:
    (pair,) = harvest(document(line("Datum", 360.0, 80.0), line("14.06.2024", 480.0, 80.0)))
    assert pair.mark is Mark.NONE


def test_a_timestamp_is_not_read_as_a_label_before_its_colon() -> None:
    assert harvest(document(line("2024-12-13T12:30", 360.0, 80.0))) == ()


def test_a_sentence_with_a_colon_in_it_is_not_a_label() -> None:
    sentence = "Es gelten unsere Allgemeinen Geschäftsbedingungen, siehe: Anhang"
    assert harvest(document(line(sentence, 50.0, 700.0))) == ()


def test_a_line_alone_on_the_page_pairs_with_nothing() -> None:
    assert harvest(document(line("Hardware", 50.0, 300.0))) == ()


def test_could_be_a_label_holds_to_short_mostly_lettered_text() -> None:
    assert could_be_a_label("USt-IdNr. des Kunden")
    assert not could_be_a_label("1851-055 Konto")
    assert not could_be_a_label("one two three four five six")
    assert not could_be_a_label("")
