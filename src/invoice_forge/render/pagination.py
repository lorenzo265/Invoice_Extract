"""Where the pages break.

Rows are filled onto a page until the next one would not fit, and the last page must
also hold the totals block — so the plan is made against measured heights before anything
is drawn, and the renderer then draws exactly the plan. That is what lets "page 1 of 3"
be printed on page 1.

When a break falls inside the table, the page it leaves carries a subtotal out and the
page it opens carries the same subtotal in. Both are recorded, because an extractor that
mistakes a carry-forward line for the invoice total is exactly what the corpus is for.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from invoice_forge.render.table import CARRY_HEIGHT, MeasuredRow, rows_total


@dataclass(frozen=True, slots=True)
class PageBudget:
    """The vertical room the table has, page by page, and what must still fit after it."""

    first_top: float
    later_top: float
    bottom: float
    header_height: float
    totals_height: float
    carry_forward: bool


@dataclass(frozen=True, slots=True)
class PlannedPage:
    """One page's share of the table, what the breaks around it carry, and whether it ends it.

    `last` is stated rather than inferred from `carried_out`: a family that carries nothing
    across a break has no carry line on any page, and the totals still belong on one page.
    """

    number: int
    rows: tuple[MeasuredRow, ...]
    carried_in: Decimal | None
    carried_out: Decimal | None
    last: bool


def plan_pages(rows: tuple[MeasuredRow, ...], budget: PageBudget) -> tuple[PlannedPage, ...]:
    """Fill pages with rows, keeping room on the last one for everything that follows it."""
    pages: list[PlannedPage] = []
    remaining = rows
    carried = Decimal(0)
    while True:
        carries_in = bool(pages) and budget.carry_forward
        top = (budget.later_top if pages else budget.first_top) + budget.header_height
        room = budget.bottom - top
        taken, rest, last = _take(remaining, room - _height(carries_in), budget)
        carried += rows_total(taken)
        pages.append(
            PlannedPage(
                number=len(pages) + 1,
                rows=taken,
                carried_in=carried - rows_total(taken) if carries_in else None,
                carried_out=None if last or not budget.carry_forward else carried,
                last=last,
            )
        )
        if last:
            return tuple(pages)
        remaining = rest


def _take(
    rows: tuple[MeasuredRow, ...], room: float, budget: PageBudget
) -> tuple[tuple[MeasuredRow, ...], tuple[MeasuredRow, ...], bool]:
    """As many rows as fit, and whether this is the last page: `(taken, rest, last)`."""
    if _height_of(rows) <= room - budget.totals_height:
        return rows, (), True
    count = _fitting_count(rows, room - _height(budget.carry_forward))
    # When they all fit but the totals block does not, the totals get a page to themselves.
    return rows[:count], rows[count:], False


def _fitting_count(rows: tuple[MeasuredRow, ...], room: float) -> int:
    """How many rows fit, always at least one so a page can never make no progress."""
    used = 0.0
    for count, row in enumerate(rows):
        if count and used + row.height > room:
            return count
        used += row.height
    return len(rows)


def _height_of(rows: tuple[MeasuredRow, ...]) -> float:
    return sum(row.height for row in rows)


def _height(present: bool) -> float:
    return CARRY_HEIGHT if present else 0.0
