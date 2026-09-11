"""What is under the table: the tax summary on the left, the totals block on the right.

The pagination has to know how tall all of this is before a single row is placed, so the
height is computed from counts — how many VAT rates, how many total rows — and the
drawing follows exactly that arithmetic. `after_table_height` and `draw_totals` are two
readings of one layout, and a test holds them to each other.

The summary itself is `render/summary.py`; this module places it and everything beside
and under it.
"""

from __future__ import annotations

from decimal import Decimal

from invoice_forge.layout.spec import Weight
from invoice_forge.lexicon.spelling import spell_amount
from invoice_forge.model import Charge
from invoice_forge.render import text as fmt
from invoice_forge.render.blocks import draw_payment, payment_height
from invoice_forge.render.context import RenderContext
from invoice_forge.render.placement import Mark, charge, field, noise, secondary
from invoice_forge.render.sheet import Sheet
from invoice_forge.render.summary import draw_summary, summary_height
from invoice_forge.render.wording import Wording

TOTAL_RULE_ABOVE = 10.0
SECONDARY_GAP = 4.0
TABLE_CLOSING_RULE = 9.0
# The lines under the totals that spell the amount out, and the one that says why a rate
# is zero. Both are printed, located and recorded as noise: neither is a field's value.
EXTRA_LINE_LEADING = 11.0
# How far under its label a stacked family sets the amount.
STACKED_VALUE_GAP = 10.0
ZERO = Decimal(0)


def after_table_height(sheet: Sheet, context: RenderContext) -> float:
    """Every point between the last row and the footer, counted before anything is drawn.

    The VAT summary and the totals are drawn side by side, so the taller of the two is
    what the table has to leave room for; the lines that run the width of the page go
    under both, and the payment block under those. The sheet is here because a spelled
    total is as long as the language makes it, so the only way to know how many lines it
    takes is to break it in the face it will be drawn in.
    """
    beside = max(summary_height(context), _totals_height(context))
    extra = EXTRA_LINE_LEADING * len(_extra_lines(sheet, context))
    return TABLE_CLOSING_RULE + beside + extra + payment_height(context)


def draw_totals(sheet: Sheet, context: RenderContext, y: float, closed: bool = True) -> float:
    """The closing rule, the VAT summary, the totals, the echo and the payment block.

    `closed` is false on a page that holds no table: there is nothing above to rule off.
    """
    spec = context.family.items
    if spec.ruled and closed:
        sheet.rule(y - TABLE_CLOSING_RULE, heavy=True)
    summary_bottom = draw_summary(sheet, context, y)
    totals_bottom = _draw_amounts(sheet, context, y)
    bottom = _draw_extra_lines(sheet, context, max(summary_bottom, totals_bottom))
    return draw_payment(sheet, context, bottom)


def _draw_extra_lines(sheet: Sheet, context: RenderContext, y: float) -> float:
    """The sentence that explains a zero rate, and the total spelled out in words.

    Both run from the left margin across the text column, which is where an invoice that
    prints them puts them — and the only place a German total spelled out has room.
    """
    spec = context.family.totals
    left = context.family.page.left
    at = y
    for line, mark in _extra_lines(sheet, context):
        at += EXTRA_LINE_LEADING
        sheet.draw(left, at, line, spec.size, Weight.REGULAR, mark)
    return at


def _extra_lines(sheet: Sheet, context: RenderContext) -> tuple[tuple[str, Mark], ...]:
    """Every line that goes under the totals, already broken to the width of the page."""
    spec = context.family.totals
    page = context.family.page
    width = page.right - page.left
    lines: list[tuple[str, Mark]] = []
    exemption = _exemption_sentence(context)
    if exemption is not None:
        broken = sheet.wrapped(exemption, width, spec.size)
        lines += [(line, noise("exemption")) for line in broken]
    if spec.amount_in_words:
        spelled = spell_amount(
            context.document.totals.total_amount, context.lexicon.amount_in_words
        )
        broken = sheet.wrapped(spelled, width, spec.size)
        lines += [(line, noise("amount_in_words")) for line in broken]
    return tuple(lines)


def _exemption_sentence(context: RenderContext) -> str | None:
    """Printed only where the family asks for it and a rate on the document is actually zero."""
    if not context.family.totals.exemption:
        return None
    if all(line.rate != ZERO for line in context.document.totals.vat_lines):
        return None
    return context.wording.exemption


def total_rows(context: RenderContext) -> tuple[tuple[str, str, Decimal], ...]:
    """`(field name or charge key, label, amount)` for the totals block, in printed order."""
    totals = context.document.totals
    labels = context.wording.labels
    rows: list[tuple[str, str, Decimal]] = [("subtotal", labels["subtotal"], totals.subtotal)]
    rows.extend(_charge_rows(context))
    rows.append(("vat_amount", labels["vat_amount"], totals.vat_amount))
    if len(totals.vat_lines) == 1:
        # One rate is a rate the document can state. Several are a summary table, and no
        # real invoice prints one of them as "the" VAT rate.
        rows.append(("vat_rate", labels["vat_rate"], totals.vat_lines[0].rate))
    rows.append(("total_amount", labels["total_amount"], totals.total_amount))
    return tuple(rows)


def _charge_rows(context: RenderContext) -> list[tuple[str, str, Decimal]]:
    """Declared charges only. An undeclared one is in the total and nowhere on the page."""
    labels = context.wording.charges
    return [
        (f"charge:{index}", labels[item.type.value], item.amount)
        for index, item in enumerate(context.document.charges)
        if item.declared
    ]


def _draw_amounts(sheet: Sheet, context: RenderContext, y: float) -> float:
    """Label and amount per row, the last one ruled off and set bold.

    A stacked family sets the amount on the line under its label instead of across from
    it, which is the layout an extractor that looks to the right of a label cannot read.
    """
    spec = context.family.totals
    rows = total_rows(context)
    top = y + spec.gap_above
    for index, (name, label, amount) in enumerate(rows):
        baseline = top + spec.leading * index
        last = index == len(rows) - 1
        if last:
            sheet.rule(baseline - TOTAL_RULE_ABOVE, spec.label_x, spec.value_x)
        weight = Weight.BOLD if last else Weight.REGULAR
        sheet.draw(spec.label_x, baseline, _label_text(context, label), spec.size, weight)
        printed, mark = _amount_text(context, name, amount)
        _place_amount(sheet, context, (printed, baseline), (weight, mark))
    return _draw_secondary(sheet, context, top + spec.leading * len(rows))


def _label_text(context: RenderContext, label: str) -> str:
    """A label above its value wears no colon; one across from a value does."""
    return label if context.family.totals.stacked else f"{label}:"


def _place_amount(
    sheet: Sheet,
    context: RenderContext,
    printed: tuple[str, float],
    style: tuple[Weight, Mark],
) -> None:
    spec = context.family.totals
    text, baseline = printed
    weight, mark = style
    if spec.stacked:
        sheet.draw(spec.label_x, baseline + STACKED_VALUE_GAP, text, spec.size, weight, mark)
        return
    sheet.draw_right(spec.value_x, baseline, text, spec.size, weight, mark)


def _amount_text(context: RenderContext, name: str, amount: Decimal) -> tuple[str, Mark]:
    wording = context.wording
    if name == "vat_rate":
        printed = f"{fmt.rate(amount, wording.number_format)} %"
        return printed, field("vat_rate", wording.labels["vat_rate"])
    printed = f"{fmt.money(amount, wording.number_format)} {context.document.currency}"
    if name.startswith("charge:"):
        index = int(name.split(":")[1])
        return printed, charge(index, _charge_label(context.document.charges, index, wording))
    return printed, field(name, wording.labels[name])


def _charge_label(charges: tuple[Charge, ...], index: int, wording: Wording) -> str:
    return wording.charges[charges[index].type.value]


def _draw_secondary(sheet: Sheet, context: RenderContext, y: float) -> float:
    spec = context.family.totals
    document = context.document
    rate = document.exchange_rate
    if not spec.secondary_echo or rate is None or document.secondary_currency is None:
        return y
    second = document.secondary_currency
    converted = fmt.money(document.totals.total_amount * rate, context.wording.number_format)
    written = fmt.quantity(rate, context.wording.number_format)
    printed = f"= {converted} {second} (1 {document.currency} = {written} {second})"
    baseline = y + SECONDARY_GAP
    mark = secondary("echo")
    sheet.draw(spec.label_x, baseline, printed, spec.size - 1, Weight.REGULAR, mark)
    return baseline + spec.leading


def _totals_height(context: RenderContext) -> float:
    spec = context.family.totals
    rows = len(total_rows(context))
    echo = SECONDARY_GAP + spec.leading if _has_secondary(context) else 0.0
    return spec.gap_above + spec.leading * rows + echo


def _has_secondary(context: RenderContext) -> bool:
    document = context.document
    return (
        context.family.totals.secondary_echo
        and document.exchange_rate is not None
        and document.secondary_currency is not None
    )
