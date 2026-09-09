"""The one module that imports `fitz`.

Everything PyMuPDF hands back is converted into this project's own typed values before
it leaves the function that received it — no `fitz` object, and no untyped value, ever
escapes this file. Swapping the PDF library is a change to this module alone.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from types import TracebackType
from typing import Self

import fitz

from invoice_extractor.document.reader import BBox, TextLine
from invoice_extractor.document.zones import classify

BBOX_PRECISION = 2


class PyMuPDFReader:
    """A `DocumentReader` over a real PDF, held open for the reader's lifetime."""

    def __init__(self, pdf_path: Path) -> None:
        if not pdf_path.is_file():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")
        self._document = fitz.open(str(pdf_path))

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._document.close()

    @property
    def page_count(self) -> int:
        return int(self._document.page_count)

    def lines(self, page: int) -> Sequence[TextLine]:
        """Every text line on `page` (1-indexed), in reading order."""
        source = self._document[page - 1]
        width, height = float(source.rect.width), float(source.rect.height)
        found: list[TextLine] = []
        for block in source.get_text("dict")["blocks"]:
            for raw in block.get("lines", ()):
                bbox = _rounded_bbox(raw["bbox"])
                text = _joined_text(raw["spans"])
                found.append(TextLine(page, text, bbox, classify(bbox, width, height)))
        # PyMuPDF returns lines grouped by block, and blocks are not in visual order;
        # label matching reads a page top to bottom, left to right.
        return sorted(found, key=_reading_order)


def _joined_text(spans: Iterable[Mapping[str, object]]) -> str:
    """A span is a run of one font, not a word — a line's text is its spans, joined."""
    return "".join(str(span["text"]) for span in spans)


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
