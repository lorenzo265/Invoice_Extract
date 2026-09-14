"""The document vocabulary: immutable lines, zones that name themselves, whole documents."""

from __future__ import annotations

import dataclasses

import pytest

from conftest import line, make_document
from invoice_extractor.document.model import BBox, TextLine, Zone


def test_textline_is_immutable() -> None:
    text_line = line("Invoice Number: INV-2024-0042", 400, 76)
    with pytest.raises(dataclasses.FrozenInstanceError):
        text_line.text = "tampered"  # type: ignore[misc]  # the point of the test is that this fails


def test_bbox_center_is_the_midpoint_of_both_axes() -> None:
    assert BBox(10.0, 20.0, 30.0, 60.0).center == (20.0, 40.0)


def test_a_zone_names_itself_the_way_a_profile_writes_it() -> None:
    assert Zone(2, 3).name == "r2c3"


def test_two_zones_at_the_same_place_are_the_same_zone() -> None:
    """A profile's zone list is compared against a line's zone, so equality has to hold."""
    assert Zone(1, 3) == Zone(1, 3)
    assert Zone(1, 3) in {Zone(1, 3), Zone(2, 2)}


def test_a_document_counts_its_pages() -> None:
    document = make_document(
        [
            (1, "Acme Components Ltd", 56.0, 49.25, 150.0, 62.99),
            (2, "Page 2", 56.0, 49.25, 90.0, 62.99),
        ]
    )
    assert document.page_count == 2
    assert document.page(2).number == 2


def test_a_document_hands_back_every_line_in_page_order() -> None:
    document = make_document(
        [(2, "second", 56.0, 49.25, 90.0, 62.99), (1, "first", 56.0, 49.25, 90.0, 62.99)]
    )
    assert [text_line.text for text_line in document.lines] == ["first", "second"]


def test_a_document_zones_its_lines() -> None:
    document = make_document([(1, "Total Due: 588.00", 400.0, 663.25, 479.49, 676.99)])
    (only,) = document.page(1).lines
    assert isinstance(only, TextLine)
    assert only.zone == Zone(3, 3)


def test_a_document_reads_back_as_the_words_on_it() -> None:
    document = make_document([(1, "Rechnungsnummer", 56.0, 49.25, 150.0, 62.99)])
    assert list(document.text()) == ["Rechnungsnummer"]
