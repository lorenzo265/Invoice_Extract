"""Shared fixtures: a document made of text lines, with no PDF anywhere near it."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from invoice_extractor.document.reader import BBox, TextLine, Zone
from invoice_extractor.document.zones import classify
from invoice_extractor.layout.schema import (
    FIELD_NAMES,
    LINE_ITEM_COLUMNS,
    FieldLayout,
    Layout,
    LineItemsLayout,
)

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


def make_field_layout(
    labels: Sequence[str] = ("Label",),
    zones: Sequence[Zone] = (Zone.TOP_RIGHT,),
    regex: str | None = None,
) -> FieldLayout:
    """A `FieldLayout` for one field, with the pieces a test does not care about filled in."""
    return FieldLayout(tuple(labels), tuple(zones), None if regex is None else re.compile(regex))


def make_layout(
    fields: Mapping[str, FieldLayout] | None = None,
    decimal_separator: str = ".",
    thousands_separator: str = ",",
    date_formats: Sequence[str] = ("%d %b %Y",),
) -> Layout:
    """A `Layout` built in memory, so a unit test never reads `layouts/*.json`."""
    return Layout(
        id="test",
        language="en",
        decimal_separator=decimal_separator,
        thousands_separator=thousands_separator,
        date_formats=tuple(date_formats),
        currency_symbols={"GBP": "£"},
        fields=dict(fields or {name: make_field_layout() for name in FIELD_NAMES}),
        line_items=LineItemsLayout(
            header_labels={column: (column,) for column in LINE_ITEM_COLUMNS},
            stop_labels=(),
        ),
    )
