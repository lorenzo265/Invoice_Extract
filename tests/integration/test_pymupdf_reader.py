"""`PyMuPDFReader` against real PDFs: the corpus fixtures committed under `tests/`."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from invoice_extractor.document.pymupdf_reader import BBOX_PRECISION, PyMuPDFReader
from invoice_extractor.document.reader import TextLine, Zone
from invoice_extractor.profile.registry import ProfileRegistry

FIXTURES = Path("tests/forge/fixtures/corpus")
TRUTH_SUFFIX = ".truth.json"
ONE_PAGE = "0004_en-GB_stacked_s7.pdf"


def documents() -> list[tuple[str, str]]:
    """Every committed fixture document, with the profile its vendor was printed from."""
    found = []
    for truth_path in sorted(FIXTURES.glob(f"*{TRUTH_SUFFIX}")):
        truth = json.loads(truth_path.read_text(encoding="utf-8"))
        name = truth_path.name.removesuffix(TRUTH_SUFFIX) + ".pdf"
        found.append((name, str(truth["generator"]["profile"])))
    return found


def page_lines(pdf_name: str, page: int = 1) -> list[TextLine]:
    with PyMuPDFReader(FIXTURES / pdf_name) as reader:
        assert reader.page_count >= page
        return list(reader.lines(page))


@pytest.mark.parametrize(("pdf_name", "profile_id"), documents())
def test_reader_returns_the_supplier_name_in_the_top_left(pdf_name: str, profile_id: str) -> None:
    """Every vendor prints itself in its letterhead, which is where a profile says to look."""
    expected = ProfileRegistry().get(profile_id).supplier.name
    supplier = next(line for line in page_lines(pdf_name) if line.text == expected)
    assert supplier.zone is Zone.TOP_LEFT


def test_reader_rounds_bbox_to_two_decimals() -> None:
    for line in page_lines(ONE_PAGE):
        box = line.bbox
        assert [box.x0, box.y0, box.x1, box.y1] == [
            round(value, BBOX_PRECISION) for value in (box.x0, box.y0, box.x1, box.y1)
        ]


@pytest.mark.parametrize(("pdf_name", "profile_id"), documents())
def test_reader_returns_lines_in_reading_order(pdf_name: str, profile_id: str) -> None:
    keys = [(line.bbox.y0, line.bbox.x0) for line in page_lines(pdf_name)]
    assert keys == sorted(keys)


def test_reader_raises_for_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "absent.pdf"
    with pytest.raises(FileNotFoundError, match=re.escape("absent.pdf")):
        PyMuPDFReader(missing)


def test_table_cells_arrive_as_separate_lines() -> None:
    """A row of a table is drawn cell by cell, so the reader must hand back cell by cell."""
    lines = page_lines(ONE_PAGE)
    tops = [line.bbox.y0 for line in lines]
    shared = max(set(tops), key=tops.count)
    row = [line for line in lines if line.bbox.y0 == shared]
    assert len(row) > 1
    assert len({line.bbox.x0 for line in row}) == len(row)
