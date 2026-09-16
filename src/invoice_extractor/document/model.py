"""The vocabulary every other package reads a document in: boxes, zones, lines, pages.

Nothing here knows a PDF library exists. `pymupdf_reader.py` builds a `Document` out of a
real file; a test builds one out of tuples, and no stage downstream can tell them apart.
A `Document` is read once and never re-read: every line already carries the zone it sits
in, and every page the anchors computed from it (`docs/ENGINE_SPEC.md` §2, stage 0).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Zone:
    """Where on the page a line sits, on the reader's grid. Rows and columns are 1-based."""

    row: int
    col: int

    @property
    def name(self) -> str:
        """`r2c3`: the spelling a profile writes, and the one a report prints."""
        return f"r{self.row}c{self.col}"


@dataclass(frozen=True, slots=True)
class BBox:
    """A rectangle on a page, in PDF points, with `y` growing downward."""

    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def center(self) -> tuple[float, float]:
        return (self.x0 + self.x1) / 2, (self.y0 + self.y1) / 2


@dataclass(frozen=True, slots=True)
class TextPart:
    """One run of text inside a line, with the box it alone occupies.

    A reader joins runs drawn close together into one line — `Kód DPH` and `Sazba`, two
    column headings a few points apart, arrive as one line of text. A table needs the two
    boxes back, because its columns are exactly what those boxes say.

    `bold` is how the run was set. A page uses weight to say what a thing is: a party's
    name is bold and its address is not, so a name set over two lines can be read back as
    one name rather than as a name and a street.
    """

    text: str
    bbox: BBox
    bold: bool = False


@dataclass(frozen=True, slots=True)
class TextLine:
    """One line of text on one page, already classified into a zone. `page` is 1-indexed.

    `parts` are the runs the line was joined from, in the order they were drawn. A line
    drawn in one run is one part; a label and its value read as a single line are two.
    """

    page: int
    text: str
    bbox: BBox
    zone: Zone
    parts: tuple[TextPart, ...] = ()

    @property
    def cells(self) -> tuple[TextPart, ...]:
        """The parts, or the whole line where a reader gave no parts for it."""
        return self.parts or (TextPart(self.text, self.bbox),)


@dataclass(frozen=True, slots=True)
class Anchors:
    """The four places on a page every later stage measures from.

    They are computed from the page alone, before any profile is known, because stage 1
    needs a document to score profiles against. Any of them may be absent: a page with no
    table has no header band, and a page that is all table has no totals.
    """

    logo_bottom: float | None
    table_header_band: tuple[float, float] | None
    totals_top: float | None
    vat_summary_top: float | None


@dataclass(frozen=True, slots=True)
class Page:
    """One page: its size, its lines in reading order, and the anchors found on it."""

    number: int
    width: float
    height: float
    lines: tuple[TextLine, ...]
    anchors: Anchors


@dataclass(frozen=True, slots=True)
class Document:
    """Every page of one file, and the path it was read from."""

    pages: tuple[Page, ...]
    source_path: str

    @property
    def page_count(self) -> int:
        return len(self.pages)

    @property
    def lines(self) -> tuple[TextLine, ...]:
        """Every line of every page, in page order — a label may sit on any page."""
        return tuple(line for page in self.pages for line in page.lines)

    def page(self, number: int) -> Page:
        return self.pages[number - 1]

    def text(self) -> Iterator[str]:
        """Every line's text, for the stages that ask what a document says rather than where."""
        return (line.text for line in self.lines)
