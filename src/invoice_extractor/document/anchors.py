"""The four places on a page every later stage measures from, found from the page alone.

Stage 1 has to score profiles against a document, so stage 0 cannot ask a profile where
anything is. What it can do is look at how the page is laid out: a letterhead is the
block above the first real gap, a table is a run of rows that share their column
positions, and a totals block is the narrow rows that follow one.

Every rule below is a statement about drawing, not about vocabulary — nothing here reads
a word. Any anchor may be absent, and absent is a value: a page that is all table has no
totals, and a continuation page has no letterhead.
"""

from __future__ import annotations

from collections.abc import Sequence
from itertools import pairwise

from invoice_extractor.document.model import Anchors, TextLine
from invoice_extractor.document.rows import Row, rows_of

# A gap this many times the previous row's height ends the letterhead block.
LETTERHEAD_GAP = 1.6
# How far down the page the letterhead may still be found.
LETTERHEAD_BAND = 0.35
# A row of a table has at least this many cells: something named, and something about it.
TABLE_CELLS = 3
# Two rows belong to the same table when this many of their cells start at the same x.
SHARED_COLUMNS = 2
# How far apart two cells' left edges may sit and still be the same column, in points.
COLUMN_TOLERANCE = 3.0
# A totals row is narrow: a label and an amount, or an amount alone.
TOTALS_CELLS = 2
DIGITS = "0123456789"


def anchors_of(lines: Sequence[TextLine], page_height: float) -> Anchors:
    """The four anchors of one page. Each is `None` when the page does not carry it."""
    rows = rows_of(lines)
    runs = table_runs(rows)
    return Anchors(
        logo_bottom=_logo_bottom(lines, page_height),
        table_header_band=_band(runs[0]) if runs else None,
        totals_top=_totals_top(rows, runs),
        vat_summary_top=_band(runs[1])[0] if len(runs) > 1 else None,
    )


def table_runs(rows: Sequence[Row]) -> tuple[tuple[Row, ...], ...]:
    """Maximal runs of consecutive rows that share their column positions."""
    runs: list[list[Row]] = []
    for row in rows:
        if len(row.cells) < TABLE_CELLS:
            runs.append([])
            continue
        if runs and runs[-1] and _shares_columns(runs[-1][-1], row):
            runs[-1].append(row)
        else:
            runs.append([row])
    return tuple(tuple(run) for run in runs if len(run) > 1)


def _band(run: Sequence[Row]) -> tuple[float, float]:
    """A table's header band is its first row: the one that names the columns."""
    return run[0].top, run[0].bottom


def _shares_columns(previous: Row, row: Row) -> bool:
    shared = sum(
        1
        for left in row.lefts
        if any(abs(left - other) <= COLUMN_TOLERANCE for other in previous.lefts)
    )
    return shared >= SHARED_COLUMNS


def _logo_bottom(lines: Sequence[TextLine], page_height: float) -> float | None:
    """The bottom of the vendor's own block at the left margin, where a gap closes it.

    A letterhead is not separated from the body by white space across the page — the
    metadata column beside it runs on down — but it is separated in its own column. So
    the gap is measured there: down the leftmost column, high enough up the page.
    """
    column = _leftmost_column(lines)
    ceiling = page_height * LETTERHEAD_BAND
    for previous, line in pairwise(column):
        if previous.bbox.y1 > ceiling:
            return None
        if line.bbox.y0 - previous.bbox.y1 > (previous.bbox.y1 - previous.bbox.y0) * LETTERHEAD_GAP:
            return previous.bbox.y1
    return None


def _leftmost_column(lines: Sequence[TextLine]) -> list[TextLine]:
    """Every line drawn at the page's left margin, top to bottom."""
    if not lines:
        return []
    margin = min(line.bbox.x0 for line in lines)
    at_margin = [line for line in lines if abs(line.bbox.x0 - margin) <= COLUMN_TOLERANCE]
    return sorted(at_margin, key=lambda line: line.bbox.y0)


def _totals_top(rows: Sequence[Row], runs: Sequence[Sequence[Row]]) -> float | None:
    """The first narrow row carrying a number, below the last table the page holds."""
    floor = runs[-1][-1].bottom if runs else 0.0
    for row in rows:
        if row.top > floor and len(row.cells) <= TOTALS_CELLS and _carries_a_number(row):
            return row.top
    return None


def _carries_a_number(row: Row) -> bool:
    return any(character in DIGITS for character in row.cells[-1].text)
