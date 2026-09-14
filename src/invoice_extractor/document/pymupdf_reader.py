"""The one module that imports `pymupdf`.

Everything PyMuPDF hands back is converted into this project's own typed values before it
leaves the function that received it — no `pymupdf` object, and no untyped value, ever
escapes `read`. Swapping the PDF library is a change to this module alone.

`read` returns a whole `Document`: every page, every line already zoned, and the anchors
each page carries. The file is opened once and closed before the function returns,
because nothing downstream may reach back into it (`docs/ENGINE_SPEC.md` §2, stage 0).
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pymupdf

from invoice_extractor.document.anchors import anchors_of
from invoice_extractor.document.model import BBox, Document, Page, TextLine
from invoice_extractor.document.zones import DEFAULT_GRID, classify

BBOX_PRECISION = 2

# What one drawn line is, once PyMuPDF's own objects have been left behind: the box it
# occupies, and its spans joined — a span is a run of one font, not a word.
Drawn = tuple[Sequence[float], str]


def read(pdf_path: Path, grid: tuple[int, int] = DEFAULT_GRID) -> Document:
    """Read one PDF into a `Document`. Raises `FileNotFoundError` for a path that is not one."""
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    source = pymupdf.open(str(pdf_path))
    pages: list[Page] = []
    try:
        for number in range(1, int(source.page_count) + 1):
            drawn = source[number - 1]
            width, height = float(drawn.rect.width), float(drawn.rect.height)
            lines = [
                (raw["bbox"], "".join(str(span["text"]) for span in raw["spans"]))
                for block in drawn.get_text("dict")["blocks"]
                for raw in block.get("lines", ())
            ]
            pages.append(_page(lines, number, width, height, grid))
    finally:
        source.close()
    return Document(pages=tuple(pages), source_path=pdf_path.as_posix())


def _page(
    drawn: Sequence[Drawn], number: int, width: float, height: float, grid: tuple[int, int]
) -> Page:
    lines = _lines(drawn, number, width, height, grid)
    return Page(
        number=number,
        width=width,
        height=height,
        lines=lines,
        anchors=anchors_of(lines, height),
    )


def _lines(
    drawn: Sequence[Drawn], number: int, width: float, height: float, grid: tuple[int, int]
) -> tuple[TextLine, ...]:
    """Every text line on the page, in reading order.

    PyMuPDF returns lines grouped by block, and blocks are not in visual order; label
    matching reads a page top to bottom, left to right.
    """
    found = [_line(box, text, number, width, height, grid) for box, text in drawn]
    return tuple(sorted(found, key=_reading_order))


def _line(
    box: Sequence[float],
    text: str,
    number: int,
    width: float,
    height: float,
    grid: tuple[int, int],
) -> TextLine:
    bbox = _rounded_bbox(box)
    return TextLine(page=number, text=text, bbox=bbox, zone=classify(bbox, width, height, grid))


def _rounded_bbox(values: Sequence[float]) -> BBox:
    """Two decimals: PyMuPDF's float32 precision past that is noise, not information."""
    return BBox(
        x0=_rounded(values[0]),
        y0=_rounded(values[1]),
        x1=_rounded(values[2]),
        y1=_rounded(values[3]),
    )


def _rounded(value: float) -> float:
    return round(float(value), BBOX_PRECISION)


def _reading_order(line: TextLine) -> tuple[float, float]:
    return line.bbox.y0, line.bbox.x0
