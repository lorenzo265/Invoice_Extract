"""`PyMuPDFReader` against the two real sample PDFs."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from invoice_extractor.document.pymupdf_reader import BBOX_PRECISION, PyMuPDFReader
from invoice_extractor.document.reader import TextLine, Zone

SAMPLES = Path("samples")
SUPPLIER_NAMES = {
    "acme_invoice.pdf": "Acme Components Ltd",
    "nordic_invoice.pdf": "Fjordvik Elektronik AB",
}
# Baseline y=478 for the first table row, less the font's ascent.
FIRST_ROW_Y0 = 467.25


def page_lines(pdf_name: str) -> list[TextLine]:
    with PyMuPDFReader(SAMPLES / pdf_name) as reader:
        assert reader.page_count == 1
        return list(reader.lines(1))


@pytest.mark.parametrize("pdf_name", sorted(SUPPLIER_NAMES))
def test_reader_returns_supplier_name_in_top_left(pdf_name: str) -> None:
    supplier = next(line for line in page_lines(pdf_name) if line.text == SUPPLIER_NAMES[pdf_name])
    assert supplier.zone is Zone.TOP_LEFT


def test_reader_rounds_bbox_to_two_decimals() -> None:
    for line in page_lines("acme_invoice.pdf"):
        box = line.bbox
        assert [box.x0, box.y0, box.x1, box.y1] == [
            round(value, BBOX_PRECISION) for value in (box.x0, box.y0, box.x1, box.y1)
        ]


def test_reader_returns_lines_in_reading_order() -> None:
    lines = page_lines("acme_invoice.pdf")
    keys = [(line.bbox.y0, line.bbox.x0) for line in lines]
    assert keys == sorted(keys)


def test_reader_raises_for_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "absent.pdf"
    with pytest.raises(FileNotFoundError, match=re.escape("absent.pdf")):
        PyMuPDFReader(missing)


def test_table_cells_arrive_as_separate_lines() -> None:
    row = [line for line in page_lines("acme_invoice.pdf") if line.bbox.y0 == FIRST_ROW_Y0]
    assert [line.text for line in row] == [
        "ACM-1001",
        "Hex bolt M8 x 40, zinc",
        "500",
        "0.12",
        "60.00",
    ]
