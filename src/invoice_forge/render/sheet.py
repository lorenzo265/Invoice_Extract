"""The drawing surface every block writes to: a page, a cursor, and a placement log.

`Sheet` is `Canvas` with the two things a block always needs — the page it is on and a
record of what it drew — so a block can say "put this here, and it is the subtotal"
in one call. Nothing here knows PyMuPDF; `Canvas` does.
"""

from __future__ import annotations

from pathlib import Path

from invoice_forge.layout.spec import Alignment, Column, PageGeometry, Weight
from invoice_forge.profiles.schema import FontFamily
from invoice_forge.render.pdf import Canvas
from invoice_forge.render.placement import Mark, Placement
from invoice_forge.render.text import wrap

BODY_SIZE = 9.0
RULE_WIDTH = 0.6
HEAVY_RULE_WIDTH = 0.8


class Sheet:
    """One document being drawn, page by page, recording every value it prints."""

    def __init__(self, geometry: PageGeometry, fonts: FontFamily) -> None:
        self.geometry = geometry
        self.canvas = Canvas(geometry, fonts)
        self.page = 0
        self.y = geometry.top
        self._placements: list[Placement] = []

    @property
    def placements(self) -> tuple[Placement, ...]:
        return tuple(self._placements)

    def new_page(self) -> None:
        self.canvas.new_page()
        self.page += 1
        self.y = self.geometry.top

    def width(self, text: str, size: float = BODY_SIZE, weight: Weight = Weight.REGULAR) -> float:
        return self.canvas.width(text, size, weight)

    def draw(
        self,
        x: float,
        y: float,
        text: str,
        size: float = BODY_SIZE,
        weight: Weight = Weight.REGULAR,
        mark: Mark | None = None,
        page: int | None = None,
    ) -> None:
        """Draw at a left edge and a baseline, recording it when the string carries a value."""
        self.canvas.text(x, y, text, size, weight, page)
        if mark is not None and text:
            self._placements.append(Placement(mark, text, page or self.page, x, y))

    def draw_right(
        self,
        x_right: float,
        y: float,
        text: str,
        size: float = BODY_SIZE,
        weight: Weight = Weight.REGULAR,
        mark: Mark | None = None,
        page: int | None = None,
    ) -> None:
        """Flush a string to a right edge. The placement records where it actually starts."""
        left = x_right - self.width(text, size, weight)
        self.draw(left, y, text, size, weight, mark, page)

    def draw_column(
        self,
        column: Column,
        y: float,
        text: str,
        size: float = BODY_SIZE,
        weight: Weight = Weight.REGULAR,
        mark: Mark | None = None,
    ) -> None:
        """Draw in a table column, on whichever edge the column is anchored to."""
        if column.align is Alignment.RIGHT:
            self.draw_right(column.anchor, y, text, size, weight, mark)
        else:
            self.draw(column.anchor, y, text, size, weight, mark)

    def rule(
        self,
        y: float,
        x0: float | None = None,
        x1: float | None = None,
        heavy: bool = False,
    ) -> None:
        """A horizontal rule across the text column, or between the two x values given."""
        width = HEAVY_RULE_WIDTH if heavy else RULE_WIDTH
        left = self.geometry.left if x0 is None else x0
        right = self.geometry.right if x1 is None else x1
        self.canvas.rule(y, left, right, width)

    def vrule(self, x: float, y0: float, y1: float) -> None:
        """A vertical rule, which only a bordered block has any use for."""
        self.canvas.line(x, y0, x, y1, RULE_WIDTH)

    def record(self, mark: Mark, text: str, x: float, y: float) -> None:
        """Note that a string already drawn is also evidence for something else.

        The point must be the one it was drawn at, exactly: that is what tells the truth
        builder this is a second reading of one printed string rather than a second
        printing. Nothing is drawn, so nothing can be recorded that is not on the page.
        """
        self._placements.append(Placement(mark, text, self.page, x, y))

    def box(self, x: float, y: float, width: float, height: float) -> None:
        self.canvas.box(x, y, width, height)

    def save(self, path: Path, title: str) -> None:
        """Write the PDF. Nothing may be drawn afterwards; the document is closed."""
        self.canvas.save(path, title)

    def wrapped(
        self,
        text: str,
        width: float,
        size: float = BODY_SIZE,
        weight: Weight = Weight.REGULAR,
    ) -> tuple[str, ...]:
        """Break a string to fit a column, measured in the face it will be drawn in.

        A bold line is wider than the same words set regular, so a party name that is set
        bold is measured bold: wrapping it as if it were body text is how a company name
        ends up half a centimetre inside the block beside it.
        """
        return wrap(text, width, lambda line: self.width(line, size, weight))
