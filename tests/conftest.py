"""Shared fixtures: a document made of text lines, with no PDF anywhere near it."""

from __future__ import annotations

from collections.abc import Sequence

from invoice_extractor.document.reader import BBox, TextLine
from invoice_extractor.document.zones import classify

PAGE_WIDTH = 595.0
PAGE_HEIGHT = 842.0

# The sample PDFs' font metrics: helv at 10 pt, measured from the drawn baseline, so a
# fake page lays out in the same coordinates docs/SAMPLES_SPEC.md gives.
ASCENT = 10.75
DESCENT = 2.99
CHAR_WIDTH = 5.5

Entry = tuple[int, str, float, float, float, float]


def line(text: str, x: float, y: float, page: int = 1) -> TextLine:
    """A `TextLine` whose text is drawn at baseline `y`, starting at `x`."""
    bbox = BBox(x, y - ASCENT, x + CHAR_WIDTH * len(text), y + DESCENT)
    return TextLine(page, text, bbox, classify(bbox, PAGE_WIDTH, PAGE_HEIGHT))


class FakeDocument:
    """A `DocumentReader` built from `(page, text, x0, y0, x1, y1)` tuples."""

    def __init__(self, entries: Sequence[Entry]) -> None:
        self._lines = [_from_entry(entry) for entry in entries]

    @property
    def page_count(self) -> int:
        return max((text_line.page for text_line in self._lines), default=0)

    def lines(self, page: int) -> Sequence[TextLine]:
        return [text_line for text_line in self._lines if text_line.page == page]


def _from_entry(entry: Entry) -> TextLine:
    page, text, x0, y0, x1, y1 = entry
    bbox = BBox(x0, y0, x1, y1)
    return TextLine(page, text, bbox, classify(bbox, PAGE_WIDTH, PAGE_HEIGHT))
