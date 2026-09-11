"""The tax summary: what was taxed at each rate, and what that came to.

A family declares one of four forms, and `docs/VARIATION_CATALOG.md` names all four on
one axis: none at all, a line per rate, a table of rate against base and VAT, or that
table with a code column ahead of it. The renderer reads the declaration; the knob that
chooses between them is `layout/variants.py`'s business.

`summary_height` and `draw_summary` are two readings of one layout, because the
pagination has to know how tall the block is before a row is placed.
"""

from __future__ import annotations

from decimal import Decimal

from invoice_forge.layout.spec import VatSummarySpec, VatSummaryStyle, Weight
from invoice_forge.model import Totals
from invoice_forge.render import text as fmt
from invoice_forge.render.context import RenderContext
from invoice_forge.render.placement import field, vat_cell
from invoice_forge.render.sheet import Sheet

SUMMARY_HEADING_GAP = 14.0
# What a VAT code column says about a rate: the standard one, a reduced one, or exempt.
ZERO = Decimal(0)
CODE_STANDARD, CODE_REDUCED, CODE_ZERO = "S", "R", "Z"


def draw_summary(sheet: Sheet, context: RenderContext, y: float) -> float:
    """Rate, base and VAT per row — as a table, as a coded table, or as one line each."""
    spec = context.family.vat_summary
    totals = context.document.totals
    if spec is None or spec.style is VatSummaryStyle.NONE or not totals.vat_lines:
        return y
    # A list has no heading row, so its first line sits where a table's headings would.
    first = 0 if spec.style is VatSummaryStyle.LIST else 1
    top = y + SUMMARY_HEADING_GAP
    headline = headline_rate(totals)
    if first:
        _draw_headings(sheet, context, spec, top)
    for index, line in enumerate(totals.vat_lines):
        baseline = top + spec.leading * (index + first)
        printed = f"{fmt.rate(line.rate, context.wording.number_format)} %"
        _draw_rate(sheet, context, spec, index, (printed, baseline))
        if line.rate == headline and len(totals.vat_lines) > 1:
            # The document states no single rate, so the summary row is the rate's evidence
            # and the column it sits under is its label.
            rate_mark = field("vat_rate", context.wording.vat_summary["rate"])
            sheet.record(rate_mark, printed, spec.x, baseline)
        _draw_amounts(sheet, context, spec, index, baseline)
    return top + spec.leading * (len(totals.vat_lines) + 1)


def summary_height(context: RenderContext) -> float:
    """Room for the heading and a row per rate, or nothing where the family prints none."""
    spec = context.family.vat_summary
    lines = len(context.document.totals.vat_lines)
    if spec is None or spec.style is VatSummaryStyle.NONE or not lines:
        return 0.0
    return SUMMARY_HEADING_GAP + spec.leading * (lines + 1)


def headline_rate(totals: Totals) -> Decimal | None:
    """The rate this invoice is mostly at: the one with the largest base, ties to the higher.

    A single-rate invoice has an obvious answer and prints it as a totals row. A document
    at two rates does not, and the extractor's `vat_rate_consistent` invariant is meant to
    complain about it — so the truth still names the dominant rate rather than nothing,
    and the benchmark reports single-rate and multi-rate documents apart.
    """
    if not totals.vat_lines:
        return None
    return max(totals.vat_lines, key=lambda line: (line.base, line.rate)).rate


def vat_code(rate: Decimal, context: RenderContext) -> str:
    """The letter a coded summary prints for a rate: standard, reduced, or zero-rated."""
    rates = context.profile.vat_rates
    if rate == ZERO:
        return CODE_ZERO
    return CODE_STANDARD if rate == rates.standard else CODE_REDUCED


def _draw_rate(
    sheet: Sheet,
    context: RenderContext,
    spec: VatSummarySpec,
    index: int,
    placed: tuple[str, float],
) -> None:
    """The rate, and the code beside it on a summary that names codes."""
    printed, baseline = placed
    if spec.style is VatSummaryStyle.CODED:
        code = vat_code(context.document.totals.vat_lines[index].rate, context)
        sheet.draw(spec.code_x, baseline, code, spec.size, Weight.BOLD)
    sheet.draw(spec.x, baseline, printed, spec.size, Weight.REGULAR, vat_cell(index, "rate"))


def _draw_headings(sheet: Sheet, context: RenderContext, spec: VatSummarySpec, y: float) -> None:
    headers = context.wording.vat_summary
    if spec.style is VatSummaryStyle.CODED:
        sheet.draw(spec.code_x, y, headers["code"], spec.size - 1, Weight.BOLD)
    sheet.draw(spec.x, y, headers["rate"], spec.size - 1, Weight.BOLD)
    sheet.draw_right(spec.base_x, y, headers["base"], spec.size - 1, Weight.BOLD)
    sheet.draw_right(spec.vat_x, y, headers["vat"], spec.size - 1, Weight.BOLD)


def _draw_amounts(
    sheet: Sheet, context: RenderContext, spec: VatSummarySpec, index: int, y: float
) -> None:
    """A table flushes base and VAT to their columns; a list runs them on after the rate."""
    line = context.document.totals.vat_lines[index]
    number_format = context.wording.number_format
    base = fmt.money(line.base, number_format)
    vat = fmt.money(line.vat, number_format)
    if spec.style is VatSummaryStyle.LIST:
        headers = context.wording.vat_summary
        listed = f"{headers['base']} {base} · {headers['vat']} {vat}"
        sheet.draw(spec.base_x, y, listed, spec.size, Weight.REGULAR, vat_cell(index, "base"))
        return
    sheet.draw_right(spec.base_x, y, base, spec.size, Weight.REGULAR, vat_cell(index, "base"))
    sheet.draw_right(spec.vat_x, y, vat, spec.size, Weight.REGULAR, vat_cell(index, "vat"))
