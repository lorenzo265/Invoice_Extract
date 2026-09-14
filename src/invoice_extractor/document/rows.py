"""Printed rows: the lines of a page grouped by the baseline they were drawn on.

A PDF has no idea what a row is. What it has is boxes, and two boxes drawn at the same
height are one row of the page whatever block the library grouped them into. Every stage
that reads a table or a totals block starts here, so the grouping lives in one place.

A row comes in two grains. `rows_of` groups whole lines, which is what a page's shape is
measured from. `cell_rows_of` groups the runs those lines were drawn in, which is what a
table's cells are: two column headings a few points apart arrive as one line and are two
cells, and no table can read them as one.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TypeVar

from invoice_extractor.document.model import TextLine, TextPart

# How far apart two cells' tops may sit and still be the same printed row, in points.
ROW_TOLERANCE = 2.0

Boxed = TypeVar("Boxed", TextLine, TextPart)


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


@dataclass(frozen=True, slots=True)
class CellRow:
    """One printed row of one page, as the runs it was drawn in rather than as lines."""

    page: int
    cells: tuple[TextPart, ...]

    @property
    def top(self) -> float:
        return min(cell.bbox.y0 for cell in self.cells)

    @property
    def bottom(self) -> float:
        return max(cell.bbox.y1 for cell in self.cells)


def rows_of(lines: Sequence[TextLine]) -> tuple[Row, ...]:
    """Every printed row of one page, top to bottom, each cell left to right."""
    return tuple(Row(cells=tuple(group)) for group in _grouped(lines))


def cell_rows_of(lines: Sequence[TextLine]) -> tuple[CellRow, ...]:
    """The same rows, one page at a time, with every drawn run as a cell of its own."""
    pages = sorted({line.page for line in lines})
    return tuple(
        CellRow(page=page, cells=tuple(group))
        for page in pages
        for group in _grouped([part for line in lines if line.page == page for part in line.cells])
    )


def _grouped(items: Sequence[Boxed]) -> list[list[Boxed]]:
    """Boxes sorted into rows: same top within the tolerance, left to right inside a row."""
    return _by_top(sorted(items, key=lambda item: (item.bbox.y0, item.bbox.x0)))


def _by_top(ordered: Sequence[Boxed]) -> list[list[Boxed]]:
    grouped: list[list[Boxed]] = []
    for item in ordered:
        if grouped and abs(item.bbox.y0 - grouped[-1][0].bbox.y0) <= ROW_TOLERANCE:
            grouped[-1].append(item)
        else:
            grouped.append([item])
    return grouped
