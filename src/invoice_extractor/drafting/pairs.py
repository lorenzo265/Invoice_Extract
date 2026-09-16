"""Every `label: value` a page prints, found from punctuation and geometry alone.

`profile draft` starts here. Nothing in this module knows a language: a label is a short
run of words followed by a colon, or set alone on its line with something beside or under
it, and a value is whatever that something says. Which field a label names is the next
stage's question (`drafting/vocabulary.py`), and what kind of thing the value is the one
after (`drafting/shapes.py`). Keeping the three apart is what lets the first of them run
on a page in a language no lexicon covers yet.

Geometry, never stream order — the rule `extraction/units/strategies.py` reads by, kept
here for the same reason: a PDF has no idea what a line is.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from invoice_extractor.document.model import BBox, Document, Page, TextLine, Zone
from invoice_extractor.document.zones import classify

SEPARATOR = ":"
# A label is short. Forty characters holds `USt-IdNr. des Leistungsempfängers` with room
# to spare; a longer run of text before a colon is a sentence that happens to contain one.
MAX_LABEL_LENGTH = 40
MAX_LABEL_WORDS = 5
# How much of the shorter box two lines must share vertically to be one line of the page
# — the same half `strategies.py` reads a tab-stopped value by.
SAME_LINE_SHARE = 0.5


class How(Enum):
    """Where the value was, relative to its label."""

    RIGHT = "right"
    BESIDE = "beside"
    BELOW = "below"


class Mark(Enum):
    """Whether the vendor ended the label with a colon, or the line merely stood alone."""

    COLON = "colon"
    NONE = "none"


@dataclass(frozen=True, slots=True)
class Pair:
    """One label and the value the page sets against it, with where both were drawn.

    `zone` is the value's zone, because that is the zone a candidate for the field will
    carry once a profile reads the page; `label_zone` is where the label itself sits.
    `mark` records whether the vendor ended the label with a colon — a label by the
    vendor's own punctuation — or the line merely stood alone and short.
    """

    label: str
    value: str
    page: int
    zone: Zone
    label_zone: Zone
    label_bbox: BBox
    value_bbox: BBox
    how: How
    mark: Mark


def harvest(document: Document) -> tuple[Pair, ...]:
    """Every pair on every page, in page order and reading order."""
    return tuple(pair for page in document.pages for pair in _on_page(page))


def could_be_a_label(text: str) -> bool:
    """A few words, mostly letters, not opening with a digit.

    `2024-12-13T12` before the colon of a timestamp is what the letter-to-digit rule
    rejects; `Tel` before a telephone number is a label and passes, as it should.
    """
    words = text.split()
    letters = sum(1 for character in text if character.isalpha())
    digits = sum(1 for character in text if character.isdigit())
    return (
        0 < len(text) <= MAX_LABEL_LENGTH
        and 0 < len(words) <= MAX_LABEL_WORDS
        and letters > digits
        and not text[0].isdigit()
    )


def _on_page(page: Page) -> list[Pair]:
    found: list[Pair] = []
    for line in page.lines:
        text = line.text.strip()
        inline = _split(text)
        if inline is not None:
            found.append(_pair(page, inline[0], line, line, How.RIGHT, Mark.COLON))
        elif could_be_a_label(text.removesuffix(SEPARATOR).strip()):
            found.extend(_partnered(page, line, _mark(text)))
    return found


def _split(text: str) -> tuple[str, str] | None:
    """`<label>: <value>` in one run of text, or nothing."""
    label, colon, value = text.partition(SEPARATOR)
    label, value = label.strip(), value.strip()
    if not colon or not value or not could_be_a_label(label):
        return None
    return label, value


def _mark(text: str) -> Mark:
    return Mark.COLON if text.endswith(SEPARATOR) else Mark.NONE


def _partnered(page: Page, anchor: TextLine, mark: Mark) -> list[Pair]:
    """The label alone on its line: its value is the nearest thing beside it, else under it."""
    label = anchor.text.strip().removesuffix(SEPARATOR).strip()
    beside = _nearest_beside(anchor, page.lines)
    if beside is not None:
        return [_pair(page, label, anchor, beside, How.BESIDE, mark)]
    below = _nearest_below(anchor, page.lines)
    if below is not None:
        return [_pair(page, label, anchor, below, How.BELOW, mark)]
    return []


def _pair(page: Page, label: str, anchor: TextLine, holder: TextLine, how: How, mark: Mark) -> Pair:
    value = holder.text.strip()
    if how is How.RIGHT:
        value = value.partition(SEPARATOR)[2].strip()
    return Pair(
        label=label,
        value=value,
        page=page.number,
        zone=classify(holder.bbox, page.width, page.height),
        label_zone=anchor.zone,
        label_bbox=anchor.bbox,
        value_bbox=holder.bbox,
        how=how,
        mark=mark,
    )


def _nearest_beside(anchor: TextLine, lines: Sequence[TextLine]) -> TextLine | None:
    """The first thing printed to the right of the label on the same line of the page."""
    beside = [
        line
        for line in lines
        if line is not anchor
        and line.bbox.x0 >= anchor.bbox.x1
        and _shares_a_line(line.bbox, anchor.bbox)
    ]
    return min(beside, key=lambda line: line.bbox.x0, default=None)


def _nearest_below(anchor: TextLine, lines: Sequence[TextLine]) -> TextLine | None:
    under = [
        line
        for line in lines
        if line.bbox.y0 > anchor.bbox.y0 and _overlaps_horizontally(line.bbox, anchor.bbox)
    ]
    return min(under, key=lambda line: line.bbox.y0, default=None)


def _shares_a_line(left: BBox, right: BBox) -> bool:
    overlap = min(left.y1, right.y1) - max(left.y0, right.y0)
    shorter = min(left.y1 - left.y0, right.y1 - right.y0)
    return overlap > shorter * SAME_LINE_SHARE


def _overlaps_horizontally(left: BBox, right: BBox) -> bool:
    return left.x0 < right.x1 and right.x0 < left.x1
