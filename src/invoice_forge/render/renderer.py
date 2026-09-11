"""One document to one PDF: measure, plan, draw, save.

The order matters. Rows are measured before anything is placed, because the page breaks
depend on how tall a wrapped description turns out to be. The plan is made before the
first row is drawn, because a carry-forward line has to know it is one. And "page 1 of 3"
is drawn last of all, on a page left long before, because the count is not known until
the last row has found its page.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from random import Random

from invoice_forge.families import Family
from invoice_forge.knobs import Knob
from invoice_forge.layout.classic import family_spec
from invoice_forge.layout.variants import with_knobs
from invoice_forge.lexicon.schema import Lexicon
from invoice_forge.model import Document
from invoice_forge.profiles.schema import VendorProfile
from invoice_forge.render import blocks, header, table, totals
from invoice_forge.render.context import RenderContext
from invoice_forge.render.pagination import PageBudget, PlannedPage, plan_pages
from invoice_forge.render.placement import Placement
from invoice_forge.render.sheet import Sheet
from invoice_forge.render.text import money
from invoice_forge.render.wording import choose_wording


@dataclass(frozen=True, slots=True)
class RenderRequest:
    """A document and everything that decides how it is printed."""

    document: Document
    profile: VendorProfile
    lexicon: Lexicon
    family: Family
    seed: int
    knobs: tuple[Knob, ...] = ()


@dataclass(frozen=True, slots=True)
class RenderResult:
    """What was drawn, and where: the placement log the truth builder reads."""

    pages: int
    placements: tuple[Placement, ...]
    context: RenderContext


def render(request: RenderRequest, path: Path) -> RenderResult:
    """Draw one document to `path` and return the log of every value it printed."""
    context = _context(request)
    sheet = Sheet(context.family.page, request.profile.fonts)
    rows = table.measure_rows(sheet, context.document, context.family.items)
    plan, extents = _draw_pages(sheet, context, rows)
    for page in plan:
        header.draw_page_line(sheet, context, page.number, len(plan), extents[page.number - 1])
    sheet.save(path, context.document.identifiers.invoice_number)
    return RenderResult(pages=len(plan), placements=sheet.placements, context=context)


def _context(request: RenderRequest) -> RenderContext:
    profile = request.profile
    family = with_knobs(family_spec(request.family), request.knobs)
    wording = choose_wording(
        request.document, profile, request.lexicon, Random(request.seed), request.knobs
    )
    return RenderContext(
        document=request.document,
        profile=profile,
        lexicon=request.lexicon,
        family=family,
        wording=wording,
        knobs=request.knobs,
    )


def _draw_pages(
    sheet: Sheet, context: RenderContext, rows: tuple[table.MeasuredRow, ...]
) -> tuple[tuple[PlannedPage, ...], list[float]]:
    """Draw page one, plan the rest from what page one showed, then draw the rest."""
    sheet.new_page()
    first = header.draw_header(sheet, context)
    extents = [first.page_line_y]
    first_top = blocks.draw_parties(sheet, context, first.bottom)
    plan = plan_pages(rows, _budget(sheet, context, first_top, first.bottom))
    _draw_page(sheet, context, plan[0], first_top)
    for page in plan[1:]:
        sheet.new_page()
        later = header.draw_header(sheet, context, first=False)
        extents.append(later.page_line_y)
        _draw_page(sheet, context, page, later.bottom)
    return plan, extents


def _budget(sheet: Sheet, context: RenderContext, first_top: float, later_top: float) -> PageBudget:
    return PageBudget(
        first_top=first_top,
        later_top=later_top,
        bottom=blocks.footer_top(context),
        header_height=table.header_height(sheet, context.family.items, context.wording),
        totals_height=totals.after_table_height(sheet, context),
        carry_forward=context.family.pagination.carry_forward,
    )


def _draw_page(sheet: Sheet, context: RenderContext, page: PlannedPage, top: float) -> None:
    """The table's share of one page: header row, carried-in line, rows, closing line.

    A page that holds only the totals gets no column headings: an empty table header is
    the kind of thing a real invoice never prints.
    """
    spec = context.family.items
    wording = context.wording
    tabled = bool(page.rows) or page.carried_in is not None
    y = top + table.HEADER_RULE_ABOVE
    if tabled:
        y = table.draw_header(sheet, spec, wording, y)
    if page.carried_in is not None:
        printed = money(page.carried_in, wording.number_format)
        y = table.draw_carry(sheet, spec, wording.carry["incoming"], printed, y)
    for row in page.rows:
        y = table.draw_row(sheet, row, spec, wording, y)
    if page.carried_out is not None:
        printed = money(page.carried_out, wording.number_format)
        table.draw_carry(sheet, spec, wording.carry["outgoing"], printed, y)
    if page.last:
        totals.draw_totals(sheet, context, y, closed=tabled)
    blocks.draw_footer(sheet, context)
