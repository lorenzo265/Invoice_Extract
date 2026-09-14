"""Printed rows: the lines of a page grouped by the baseline they were drawn on.

A PDF has no idea what a row is. What it has is boxes, and two boxes drawn at the same
height are one row of the page whatever block the library grouped them into. Every stage
that reads a table or a totals block starts here, so the grouping lives in one place.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from invoice_extractor.document.model import TextLine

# How far apart two cells' tops may sit and still be the same printed row, in points.
ROW_TOLERANCE = 2.0


@dataclass(frozen=True, slots=True)
class Row:
    """One printed row: its cells left to right, and the band it occupies."""

    cells: tuple[TextLine, ...]

    @property
    def top(self) -> float:
        return min(cell.bbox.y0 for cell in self.cells)

    @property
    def bottom(self) -> float:
        return max(cell.bbox.y1 for cell in self.cells)

    @property
    def lefts(self) -> tuple[float, ...]:
        return tuple(cell.bbox.x0 for cell in self.cells)

    @property
    def text(self) -> str:
        return " ".join(cell.text.strip() for cell in self.cells)


def rows_of(lines: Sequence[TextLine]) -> tuple[Row, ...]:
    """Every printed row of one page, top to bottom, each cell left to right."""
    ordered = sorted(lines, key=lambda line: (line.bbox.y0, line.bbox.x0))
    grouped: list[list[TextLine]] = []
    for line in ordered:
        if grouped and abs(line.bbox.y0 - grouped[-1][0].bbox.y0) <= ROW_TOLERANCE:
            grouped[-1].append(line)
        else:
            grouped.append([line])
    return tuple(Row(cells=tuple(cells)) for cells in grouped)
