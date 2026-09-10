"""What is under the table: the VAT summary on the left, the totals block on the right.

The pagination has to know how tall all of this is before a single row is placed, so the
height is computed from counts — how many VAT rates, how many total rows — and the
drawing follows exactly that arithmetic. `after_table_height` and `draw_totals` are two
readings of one layout, and a test holds them to each other.
"""

from __future__ import annotations

from decimal import Decimal

from invoice_forge.layout.spec import VatSummarySpec, VatSummaryStyle, Weight
from invoice_forge.model import Charge, Totals
from invoice_forge.render import text as fmt
from invoice_forge.render.blocks import draw_payment, payment_height
from invoice_forge.render.context import RenderContext
from invoice_forge.render.placement import Mark, charge, field, secondary, vat_cell
from invoice_forge.render.sheet import Sheet
from invoice_forge.render.wording import Wording

SUMMARY_HEADING_GAP = 14.0
TOTAL_RULE_ABOVE = 10.0
SECONDARY_GAP = 4.0
TABLE_CLOSING_RULE = 9.0


def after_table_height(context: RenderContext) -> float:
    """Every point between the last row and the footer, counted before anything is drawn.

    The VAT summary and the totals are drawn side by side, so the taller of the two is
    what the table has to leave room for; the payment block goes under both.
    """
    beside = max(_summary_height(context), _totals_height(context))
    return TABLE_CLOSING_RULE + beside + payment_height(context)


def draw_totals(sheet: Sheet, context: RenderContext, y: float) -> float:
    """The closing rule, the VAT summary, the totals, the echo and the payment block."""
    spec = context.family.items
    if spec.ruled:
        sheet.rule(y - TABLE_CLOSING_RULE, heavy=True)
    summary_bottom = _draw_vat_summary(sheet, context, y)
    totals_bottom = _draw_amounts(sheet, context, y)
    return draw_payment(sheet, context, max(summary_bottom, totals_bottom))


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


def _charge_rows(context: RenderContext) -> list[tuple[str, str, Decimal]]:
    """Declared charges only. An undeclared one is in the total and nowhere on the page."""
    labels = context.wording.charges
    return [
        (f"charge:{index}", labels[item.type.value], item.amount)
        for index, item in enumerate(context.document.charges)
        if item.declared
    ]


def _draw_vat_summary(sheet: Sheet, context: RenderContext, y: float) -> float:
    spec = context.family.vat_summary
    totals = context.document.totals
    if spec is None or spec.style is VatSummaryStyle.NONE or not totals.vat_lines:
        return y
    top = y + SUMMARY_HEADING_GAP
    headline = headline_rate(totals)
    _draw_summary_headings(sheet, context, spec, top)
    for index, line in enumerate(totals.vat_lines):
        baseline = top + spec.leading * (index + 1)
        printed = f"{fmt.rate(line.rate)} %"
        sheet.draw(spec.x, baseline, printed, spec.size, Weight.REGULAR, vat_cell(index, "rate"))
        if line.rate == headline and len(totals.vat_lines) > 1:
            # The document states no single rate, so the summary row is the rate's evidence
            # and the column it sits under is its label.
            rate_mark = field("vat_rate", context.wording.vat_summary["rate"])
            sheet.record(rate_mark, printed, spec.x, baseline)
        _draw_summary_amounts(sheet, context, spec, index, baseline)
    return top + spec.leading * (len(totals.vat_lines) + 1)


def _draw_summary_headings(
    sheet: Sheet, context: RenderContext, spec: VatSummarySpec, y: float
) -> None:
    headers = context.wording.vat_summary
    sheet.draw(spec.x, y, headers["rate"], spec.size - 1, Weight.BOLD)
    sheet.draw_right(spec.base_x, y, headers["base"], spec.size - 1, Weight.BOLD)
    sheet.draw_right(spec.vat_x, y, headers["vat"], spec.size - 1, Weight.BOLD)


def _draw_summary_amounts(
    sheet: Sheet, context: RenderContext, spec: VatSummarySpec, index: int, y: float
) -> None:
    line = context.document.totals.vat_lines[index]
    number_format = context.wording.number_format
    base = fmt.money(line.base, number_format)
    vat = fmt.money(line.vat, number_format)
    sheet.draw_right(spec.base_x, y, base, spec.size, Weight.REGULAR, vat_cell(index, "base"))
    sheet.draw_right(spec.vat_x, y, vat, spec.size, Weight.REGULAR, vat_cell(index, "vat"))


def _draw_amounts(sheet: Sheet, context: RenderContext, y: float) -> float:
    """Label and amount per row, the last one ruled off and set bold."""
    spec = context.family.totals
    rows = total_rows(context)
    top = y + spec.gap_above
    for index, (name, label, amount) in enumerate(rows):
        baseline = top + spec.leading * index
        last = index == len(rows) - 1
        if last:
            sheet.rule(baseline - TOTAL_RULE_ABOVE, spec.label_x, spec.value_x)
        weight = Weight.BOLD if last else Weight.REGULAR
        sheet.draw(spec.label_x, baseline, f"{label}:", spec.size, weight)
        printed, mark = _amount_text(context, name, amount)
        sheet.draw_right(spec.value_x, baseline, printed, spec.size, weight, mark)
    return _draw_secondary(sheet, context, top + spec.leading * len(rows))


def _amount_text(context: RenderContext, name: str, amount: Decimal) -> tuple[str, Mark]:
    wording = context.wording
    if name == "vat_rate":
        return f"{fmt.rate(amount)} %", field("vat_rate", wording.labels["vat_rate"])
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


def _summary_height(context: RenderContext) -> float:
    spec = context.family.vat_summary
    lines = len(context.document.totals.vat_lines)
    if spec is None or spec.style is VatSummaryStyle.NONE or not lines:
        return 0.0
    return SUMMARY_HEADING_GAP + spec.leading * (lines + 1)


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
