"""`read` against real PDFs: the corpus fixtures committed under `tests/`."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from invoice_extractor.document.model import Document, Zone
from invoice_extractor.document.pymupdf_reader import BBOX_PRECISION, read
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


def document(pdf_name: str) -> Document:
    return read(FIXTURES / pdf_name)


@pytest.mark.parametrize(("pdf_name", "profile_id"), documents())
def test_the_supplier_name_is_read_in_the_top_left(pdf_name: str, profile_id: str) -> None:
    """Every vendor prints itself in its letterhead, which is where a profile says to look."""
    expected = ProfileRegistry().get(profile_id).supplier.name
    supplier = next(line for line in document(pdf_name).lines if line.text == expected)
    assert supplier.zone == Zone(1, 1)


def test_bbox_values_are_rounded_to_two_decimals() -> None:
    for line in document(ONE_PAGE).lines:
        box = line.bbox
        assert [box.x0, box.y0, box.x1, box.y1] == [
            round(value, BBOX_PRECISION) for value in (box.x0, box.y0, box.x1, box.y1)
        ]


@pytest.mark.parametrize(("pdf_name", "profile_id"), documents())
def test_lines_arrive_in_reading_order(pdf_name: str, profile_id: str) -> None:
    for page in document(pdf_name).pages:
        keys = [(line.bbox.y0, line.bbox.x0) for line in page.lines]
        assert keys == sorted(keys)


@pytest.mark.parametrize(("pdf_name", "profile_id"), documents())
def test_every_page_knows_its_own_size_and_number(pdf_name: str, profile_id: str) -> None:
    read_back = document(pdf_name)
    assert [page.number for page in read_back.pages] == list(range(1, read_back.page_count + 1))
    assert all(page.width > 0 and page.height > 0 for page in read_back.pages)


@pytest.mark.parametrize(("pdf_name", "profile_id"), documents())
def test_every_page_carries_the_anchors_found_on_it(pdf_name: str, profile_id: str) -> None:
    """A rendered invoice has a table, so its first page has a header band."""
    first = document(pdf_name).page(1)
    assert first.anchors.table_header_band is not None
    top, bottom = first.anchors.table_header_band
    assert 0 < top < bottom < first.height


def test_the_letterhead_is_found_above_everything_it_introduces() -> None:
    first = document(ONE_PAGE).page(1)
    assert first.anchors.logo_bottom is not None
    assert first.anchors.table_header_band is not None
    assert first.anchors.logo_bottom < first.anchors.table_header_band[0]


def test_reading_a_file_that_is_not_there_raises(tmp_path: Path) -> None:
    missing = tmp_path / "absent.pdf"
    with pytest.raises(FileNotFoundError, match=re.escape("absent.pdf")):
        read(missing)


def test_a_document_names_the_file_it_was_read_from() -> None:
    assert document(ONE_PAGE).source_path == (FIXTURES / ONE_PAGE).as_posix()


def test_table_cells_arrive_as_separate_lines() -> None:
    """A row of a table is drawn cell by cell, so the reader must hand back cell by cell."""
    lines = document(ONE_PAGE).page(1).lines
    tops = [line.bbox.y0 for line in lines]
    shared = max(set(tops), key=tops.count)
    row = [line for line in lines if line.bbox.y0 == shared]
    assert len(row) > 1
    assert len({line.bbox.x0 for line in row}) == len(row)
