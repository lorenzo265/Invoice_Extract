"""The document vocabulary: immutable lines, and a fake that satisfies the protocol."""

from __future__ import annotations

import dataclasses

import pytest

from conftest import FakeDocument, line
from invoice_extractor.document.reader import BBox, DocumentReader, TextLine, Zone


def test_textline_is_immutable() -> None:
    text_line = line("Invoice Number: INV-2024-0042", 400, 76)
    with pytest.raises(dataclasses.FrozenInstanceError):
        text_line.text = "tampered"  # type: ignore[misc]  # the point of the test is that this fails


def test_bbox_center_is_the_midpoint_of_both_axes() -> None:
    assert BBox(10.0, 20.0, 30.0, 60.0).center == (20.0, 40.0)


def test_fake_document_satisfies_protocol() -> None:
    document: DocumentReader = FakeDocument([(1, "Acme Components Ltd", 56.0, 49.25, 150.0, 62.99)])
    assert document.page_count == 1
    assert [text_line.text for text_line in document.lines(1)] == ["Acme Components Ltd"]


def test_fake_document_zones_its_lines() -> None:
    document = FakeDocument([(1, "Total Due: 588.00", 400.0, 663.25, 479.49, 676.99)])
    (only,) = document.lines(1)
    assert isinstance(only, TextLine)
    assert only.zone is Zone.BOTTOM_RIGHT
