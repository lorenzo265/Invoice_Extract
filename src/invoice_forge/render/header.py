"""Everything above the table: letterhead, title, the reference block, and the traps.

Each function draws one block from the family's declaration and returns the y its next
neighbour starts at, so the page is stacked rather than laid out at fixed offsets. That
is what lets a profile with three extra reference lines push the table down instead of
printing over it.

The reference block is the one an extractor has most trouble with, so it is drawn three
ways: as a list with the value flushed right of its label, as a bordered table, and
stacked with the value on the line below. The family says which.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from invoice_forge.layout.spec import CustomerVat, MetadataSpec, MetadataStyle, PageLine, Weight
from invoice_forge.render import text as fmt
from invoice_forge.render.context import RenderContext
from invoice_forge.render.placement import field, noise, party_part
from invoice_forge.render.sheet import Sheet
from invoice_forge.render.wording import page_line

RULE_BELOW_HEADER = 20.0
FOOTER_PAGE_LINE_GAP = 4.0
# Trap dates sit a few days off the invoice date, never on it.
TRAP_ORDER_DAYS = 11
TRAP_DELIVERY_DAYS = 4
TRAP_PRINT_DAYS = 2
# The page count is the last row of the reference block; the rule goes under it.
PAGE_LINE_GAP = 4.0
NAME_TO_LINES_GAP = 4.0
VAT_LINE_GAP = 2.0
# Where the rule between labels and values falls in a bordered reference block.
METADATA_DIVIDER = 8.0

# Every reference the header block can print, in the order a European invoice prints them.
METADATA_ORDER: tuple[str, ...] = (
    "invoice_number",
    "credit_reference",
    "invoice_date",
    "supply_date",
    "due_date",
    "customer_number",
    "order_number",
    "contract_number",
    "our_reference",
    "your_reference",
    "currency",
)

Row = tuple[str, str, str]


@dataclass(frozen=True, slots=True)
class HeaderExtent:
    """Where the header block ended, and where its last line — the page count — goes."""

    bottom: float
    page_line_y: float


def draw_header(sheet: Sheet, context: RenderContext, first: bool = True) -> HeaderExtent:
    """Letterhead on the left, title and reference list on the right, one rule under both.

    A family that does not repeat its letterhead prints the supplier's name alone on the
    pages after the first — enough to know whose invoice this is, and nothing an extractor
    can read the VAT id off twice.
    """
    repeats = first or context.family.pagination.repeat_letterhead
    left = _draw_letterhead(sheet, context) if repeats else _draw_continuation(sheet, context)
    _draw_title(sheet, context)
    page_line_y = _draw_traps(sheet, context, _draw_metadata(sheet, context))
    bottom = max(left, page_line_y)
    sheet.rule(bottom + PAGE_LINE_GAP)
    return HeaderExtent(bottom=bottom + PAGE_LINE_GAP + RULE_BELOW_HEADER, page_line_y=page_line_y)


def draw_page_line(sheet: Sheet, context: RenderContext, page: int, pages: int, y: float) -> None:
    """Drawn last, on a page long since left: the count is not known until the end."""
    spec = context.family.metadata
    if context.family.page_line is PageLine.NONE:
        return
    printed = page_line(context.wording, page, pages)
    if context.family.page_line is PageLine.FOOTER:
        baseline = context.family.page.bottom - FOOTER_PAGE_LINE_GAP
        sheet.draw_right(spec.value_x, baseline, printed, spec.size, Weight.REGULAR, page=page)
        return
    sheet.draw_right(spec.value_x, y, printed, spec.size, Weight.REGULAR, page=page)


def _draw_continuation(sheet: Sheet, context: RenderContext) -> float:
    spec = context.family.letterhead
    sheet.draw(spec.x, spec.top, context.document.supplier.name, spec.name_size, Weight.BOLD)
    return spec.top


def _draw_letterhead(sheet: Sheet, context: RenderContext) -> float:
    spec = context.family.letterhead
    supplier = context.document.supplier
    name_mark = party_part("supplier", "name")
    sheet.draw(spec.x, spec.top, supplier.name, spec.name_size, Weight.BOLD, name_mark)
    top = spec.top + spec.leading + NAME_TO_LINES_GAP
    for index, line in enumerate(supplier.lines):
        baseline = top + spec.leading * index
        sheet.draw(
            spec.x, baseline, line, spec.line_size, Weight.REGULAR, party_part("supplier", "line")
        )
    y = top + spec.leading * len(supplier.lines) + VAT_LINE_GAP
    if supplier.vat_id is None:
        return y
    label = context.wording.labels["supplier_vat_id"]
    printed = f"{label}: {supplier.vat_id}"
    sheet.draw(spec.x, y, printed, spec.line_size, Weight.REGULAR, field("supplier_vat_id", label))
    return y


def _draw_title(sheet: Sheet, context: RenderContext) -> None:
    """The document type, and under it the stamp that says this copy is not the original."""
    spec = context.family.title
    title = context.wording.title
    printed = title.upper() if spec.upper_case else title
    sheet.draw(spec.x, spec.top, printed, spec.size, Weight.BOLD)
    if not context.family.copy_stamp:
        return
    stamp = context.wording.copy_stamp
    baseline = spec.top + spec.stamp_gap
    sheet.draw(spec.x, baseline, stamp, spec.stamp_size, Weight.BOLD, noise("copy_stamp", stamp))


def _draw_traps(sheet: Sheet, context: RenderContext, y: float) -> float:
    """Dates beside the real ones. They are noise, and the truth says which trap is where."""
    spec = context.family.traps
    if spec is None:
        return y
    for index, kind in enumerate(spec.kinds):
        baseline = y + spec.leading * index
        label = context.wording.traps[kind]
        sheet.draw(spec.label_x, baseline, f"{label}:", spec.size)
        printed = _trap_date(context, kind)
        sheet.draw_right(
            spec.value_x, baseline, printed, spec.size, Weight.REGULAR, noise("trap_label", label)
        )
    return y + spec.leading * len(spec.kinds)


def _trap_date(context: RenderContext, kind: str) -> str:
    """Dates near the invoice date but never equal to it, so a wrong read is a wrong value."""
    dates = context.document.dates
    offsets = {"order_date": -TRAP_ORDER_DAYS, "delivery_date": -TRAP_DELIVERY_DAYS}
    shifted = dates.invoice_date + timedelta(days=offsets.get(kind, TRAP_PRINT_DAYS))
    return fmt.date_text(shifted, context.wording.date_format, context.lexicon)


def _draw_metadata(sheet: Sheet, context: RenderContext) -> float:
    """The reference block, in whichever of the three forms the family declares."""
    spec = context.family.metadata
    rows = _metadata_rows(context)
    if spec.style is MetadataStyle.STACKED:
        return _draw_stacked_metadata(sheet, spec, rows)
    bottom = _draw_listed_metadata(sheet, spec, rows)
    if spec.style is MetadataStyle.TABLE:
        _rule_metadata(sheet, spec, len(rows))
    return bottom


def _draw_listed_metadata(sheet: Sheet, spec: MetadataSpec, rows: tuple[Row, ...]) -> float:
    """Label on the left of the block, value flushed to the right margin, one row each."""
    for index, (name, label, printed) in enumerate(rows):
        y = spec.top + spec.leading * index
        sheet.draw(spec.label_x, y, f"{label}:", spec.size)
        sheet.draw_right(spec.value_x, y, printed, spec.size, Weight.REGULAR, field(name, label))
    return spec.top + spec.leading * len(rows)


def _draw_stacked_metadata(sheet: Sheet, spec: MetadataSpec, rows: tuple[Row, ...]) -> float:
    """The value on the line under its label — no value is to the right of anything here."""
    for index, (name, label, printed) in enumerate(rows):
        y = spec.top + spec.leading * index
        sheet.draw(spec.label_x, y, label, spec.size - 1)
        mark = field(name, label)
        sheet.draw(spec.label_x, y + spec.value_leading, printed, spec.size, Weight.BOLD, mark)
    return spec.top + spec.leading * len(rows)


def _rule_metadata(sheet: Sheet, spec: MetadataSpec, rows: int) -> None:
    """The box around a bordered block: one rule per row, and three down the sides."""
    top = spec.top - spec.leading + spec.pad
    bottom = spec.top + spec.leading * (rows - 1) + spec.pad
    for index in range(rows + 1):
        sheet.rule(top + spec.leading * index, spec.left, spec.value_x + spec.pad)
    for x in (spec.left, spec.label_x + METADATA_DIVIDER, spec.value_x + spec.pad):
        sheet.vrule(x, top, bottom)


def _metadata_rows(context: RenderContext) -> tuple[Row, ...]:
    """`(field name, label, printed value)` for every reference this document prints."""
    labels = context.wording.labels
    printed = _metadata_values(context)
    order = METADATA_ORDER
    if context.family.customer_vat is CustomerVat.METADATA:
        printed["customer_vat_id"] = context.document.bill_to.vat_id or ""
        order = (*order, "customer_vat_id")
    return tuple((name, labels[name], printed[name]) for name in order if printed[name])


def _metadata_values(context: RenderContext) -> dict[str, str]:
    document = context.document
    dates = document.dates
    identifiers = document.identifiers

    def written(value: date | None) -> str:
        if value is None:
            return ""
        return fmt.date_text(value, context.wording.date_format, context.lexicon)

    return {
        "invoice_number": identifiers.invoice_number,
        "credit_reference": identifiers.credit_reference or "",
        "invoice_date": written(dates.invoice_date),
        "supply_date": written(dates.supply_date),
        "due_date": written(dates.due_date),
        "customer_number": identifiers.customer_number,
        "order_number": identifiers.order_number,
        "contract_number": identifiers.contract_number or "",
        "our_reference": identifiers.our_reference or "",
        "your_reference": identifiers.your_reference or "",
        "currency": document.currency,
    }
