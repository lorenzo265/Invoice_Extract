"""The line-item table: measuring a row, drawing a row, and the rules around them.

A row's height is not a constant — a description that wraps to three lines is three lines
tall, a row with two components is two lines taller, and the first row of a section wears
its heading — so the table measures every row before the pagination decides where the
page breaks. Measuring and drawing share the wrapped lines and the same arithmetic, so
what was measured is what is drawn.

Section subtotals and carry-forward lines are recorded as noise: both print a number that
looks like the invoice total and is not one, which is exactly the kind of trap the corpus
exists to measure.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from invoice_forge.layout.spec import Alignment, Column, ItemsSpec, Weight
from invoice_forge.model import Document, LineItem, SubItem
from invoice_forge.render import text as fmt
from invoice_forge.render.placement import cell, noise
from invoice_forge.render.sheet import Sheet
from invoice_forge.render.wording import Wording

HEADER_RULE_ABOVE = 10.0
HEADER_RULE_BELOW = 4.0
HEADER_TO_FIRST_ROW = 18.0
# A heading of several words wraps inside its column; one word cannot, which is why
# `layout/columns.py` anchors every column wide enough for the longest word in it. The
# same gutter separates two columns' values, which is what a description wraps short of.
HEADING_LEADING = 9.0
COLUMN_GUTTER = 4.0
CARRY_RULE_ABOVE = 9.0
CARRY_HEIGHT = 18.0
# The five columns the extractor reads. The others are printed but not recorded as cells.
TRUTH_CELLS = frozenset({"sku", "description", "quantity", "unit_price", "net_amount"})


@dataclass(frozen=True, slots=True)
class MeasuredRow:
    """One item, broken to its column, with whatever a section wraps around it."""

    item: LineItem
    lines: tuple[str, ...]
    parts: tuple[tuple[str, ...], ...]
    height: float
    heading: str | None = None
    subtotal: Decimal | None = None


def measure_rows(sheet: Sheet, document: Document, spec: ItemsSpec) -> tuple[MeasuredRow, ...]:
    """Every row of the document, measured in the face it will be drawn in."""
    items = document.items
    return tuple(
        _measure(sheet, item, spec, _heading(items, index), _subtotal(items, index))
        for index, item in enumerate(items)
    )


def rows_total(rows: tuple[MeasuredRow, ...]) -> Decimal:
    """What a page's rows add up to, for the line a page break carries forward."""
    return sum((row.item.net_amount for row in rows), Decimal(0))


def heading_lines(
    sheet: Sheet, spec: ItemsSpec, wording: Wording
) -> tuple[tuple[Column, tuple[str, ...]], ...]:
    """Each column's heading, broken to the room the column set leaves it.

    A table of nine columns cannot print `Faktureringsintervall` beside `Fördelning` on
    one line in any face that is still readable, and a real one does not try: it sets the
    heading over two lines. What room a column has is the distance to its neighbour on the
    side its text runs, which is what the anchors already say.
    """
    rooms = _rooms(spec)
    return tuple(
        (column, sheet.wrapped(wording.columns[column.name], room, spec.header_size))
        for column, room in zip(spec.columns, rooms, strict=True)
    )


def header_height(sheet: Sheet, spec: ItemsSpec, wording: Wording) -> float:
    """How tall the heading row is, counted before the pagination places a single row."""
    tallest = max(len(lines) for _, lines in heading_lines(sheet, spec, wording))
    return HEADER_RULE_ABOVE + HEADING_LEADING * (tallest - 1) + HEADER_TO_FIRST_ROW


def draw_header(sheet: Sheet, spec: ItemsSpec, wording: Wording, y: float) -> float:
    """The column headings, between two rules. Returns the first row's baseline."""
    broken = heading_lines(sheet, spec, wording)
    tallest = max(len(lines) for _, lines in broken)
    if spec.ruled:
        sheet.rule(y - HEADER_RULE_ABOVE, heavy=True)
    for column, lines in broken:
        for index, line in enumerate(lines):
            baseline = y + HEADING_LEADING * index
            sheet.draw_column(column, baseline, line, spec.header_size, Weight.BOLD)
    bottom = y + HEADING_LEADING * (tallest - 1)
    if spec.ruled:
        sheet.rule(bottom + HEADER_RULE_BELOW, heavy=True)
    return bottom + HEADER_TO_FIRST_ROW


def _rooms(spec: ItemsSpec) -> tuple[float, ...]:
    """The width each heading has: to the next anchor, or to the previous one if flushed.

    The description's room is the width the set declares for it, because that is what its
    rows wrap to and a heading may not claim more than its own column.
    """
    anchors = [column.anchor for column in spec.columns]
    rooms = []
    for index, column in enumerate(spec.columns):
        if column.name == "description":
            rooms.append(spec.description_width)
            continue
        if column.align is Alignment.LEFT:
            edge = anchors[index + 1] if index + 1 < len(anchors) else anchors[index]
        else:
            edge = anchors[index - 1] if index else anchors[index]
        rooms.append(abs(edge - column.anchor) - COLUMN_GUTTER)
    return tuple(rooms)


def draw_row(sheet: Sheet, row: MeasuredRow, spec: ItemsSpec, wording: Wording, y: float) -> float:
    """One item, its section heading, its components and its section subtotal."""
    top = _draw_heading(sheet, row, spec, y)
    for column in spec.columns:
        if column.name == "description":
            _draw_description(sheet, row, spec, column, top)
            continue
        mark = cell(row.item.pos, column.name) if column.name in TRUTH_CELLS else None
        printed = _cell_text(row.item, column.name, wording)
        sheet.draw_column(column, top, printed, spec.row_size, Weight.REGULAR, mark)
    after = _draw_sub_items(sheet, row, spec, wording, top)
    _draw_subtotal(sheet, row, spec, wording, after)
    return y + row.height


def draw_carry(sheet: Sheet, spec: ItemsSpec, label: str, amount: str, y: float) -> float:
    """The subtotal a break carries: out at the foot of a page, in at the head of the next."""
    description = _column(spec, "description")
    if spec.ruled:
        sheet.rule(y - CARRY_RULE_ABOVE)
    sheet.draw(description.anchor, y, label, spec.row_size, Weight.BOLD)
    mark = noise("carry_forward", label)
    sheet.draw_right(
        _column(spec, "net_amount").anchor, y, amount, spec.row_size, Weight.BOLD, mark
    )
    return y + CARRY_HEIGHT


def _heading(items: tuple[LineItem, ...], index: int) -> str | None:
    """A section's heading is drawn where the section starts, and nowhere else."""
    section = items[index].section
    if section is None:
        return None
    return section if index == 0 or items[index - 1].section != section else None


def _subtotal(items: tuple[LineItem, ...], index: int) -> Decimal | None:
    """A section's subtotal is drawn where it ends, and adds only that section's rows."""
    section = items[index].section
    last = index == len(items) - 1 or items[index + 1].section != section
    if section is None or not last:
        return None
    grouped = [item for item in items if item.section == section]
    return sum((item.net_amount for item in grouped), Decimal(0))


def _measure(
    sheet: Sheet, item: LineItem, spec: ItemsSpec, heading: str | None, subtotal: Decimal | None
) -> MeasuredRow:
    lines = sheet.wrapped(item.description, spec.description_width, spec.row_size)
    indented = spec.description_width - spec.sub_item_indent
    parts = tuple(
        sheet.wrapped(part.description, indented, spec.row_size) for part in item.sub_items
    )
    drawn = len(lines) + sum(len(part) for part in parts)
    height = spec.row_leading * drawn + spec.row_gap
    if heading is not None:
        height += spec.section_gap + spec.row_leading
    if subtotal is not None:
        height += spec.section_gap + spec.row_leading
    return MeasuredRow(item, lines, parts, height, heading, subtotal)


def _draw_heading(sheet: Sheet, row: MeasuredRow, spec: ItemsSpec, y: float) -> float:
    if row.heading is None:
        return y
    column = _column(spec, "description")
    sheet.draw(column.anchor, y + spec.section_gap, row.heading, spec.row_size, Weight.BOLD)
    return y + spec.section_gap + spec.row_leading


def _draw_sub_items(
    sheet: Sheet, row: MeasuredRow, spec: ItemsSpec, wording: Wording, y: float
) -> float:
    """Components under their parent, indented and wrapped, priced where the parent says so."""
    column = _column(spec, "description")
    at = y + spec.row_leading * len(row.lines)
    for part, lines in zip(row.item.sub_items, row.parts, strict=True):
        _draw_sub_item_amount(sheet, part, spec, wording, at)
        for line in lines:
            sheet.draw(column.anchor + spec.sub_item_indent, at, line, spec.row_size)
            at += spec.row_leading
    return at


def _draw_sub_item_amount(
    sheet: Sheet, part: SubItem, spec: ItemsSpec, wording: Wording, y: float
) -> None:
    if part.quantity is None or part.unit_price is None:
        return
    quantity = _column(spec, "quantity")
    price = _column(spec, "unit_price")
    sheet.draw_right(
        quantity.anchor, y, fmt.quantity(part.quantity, wording.number_format), spec.row_size
    )
    sheet.draw_right(
        price.anchor, y, fmt.price(part.unit_price, wording.number_format), spec.row_size
    )


def _draw_subtotal(
    sheet: Sheet, row: MeasuredRow, spec: ItemsSpec, wording: Wording, y: float
) -> None:
    """A number that looks like a total and is not one, so the truth records it as noise."""
    if row.subtotal is None:
        return
    baseline = y + spec.section_gap
    label = f"{wording.labels['subtotal']} {row.item.section}"
    sheet.draw(_column(spec, "description").anchor, baseline, label, spec.row_size, Weight.BOLD)
    printed = fmt.money(row.subtotal, wording.number_format)
    mark = noise("section_subtotal", label)
    sheet.draw_right(
        _column(spec, "net_amount").anchor, baseline, printed, spec.row_size, Weight.BOLD, mark
    )


def _column(spec: ItemsSpec, name: str) -> Column:
    return next(column for column in spec.columns if column.name == name)


def _draw_description(
    sheet: Sheet, row: MeasuredRow, spec: ItemsSpec, column: Column, y: float
) -> None:
    """Each wrapped line is its own placement, so the truth carries a box per line."""
    for index, line in enumerate(row.lines):
        baseline = y + spec.row_leading * index
        mark = cell(row.item.pos, "description")
        sheet.draw(column.anchor, baseline, line, spec.row_size, Weight.REGULAR, mark)


def _cell_text(item: LineItem, column: str, wording: Wording) -> str:
    number_format = wording.number_format
    printed = {
        "pos": lambda: str(item.pos),
        "sku": lambda: item.sku,
        "unit": lambda: item.unit,
        "quantity": lambda: fmt.quantity(item.quantity, number_format),
        "unit_price": lambda: fmt.price(item.unit_price, number_format),
        "discount": lambda: _discount(item, number_format),
        "vat_rate": lambda: fmt.rate(item.vat_rate, number_format),
        "net_amount": lambda: fmt.money(item.net_amount, number_format),
        "subscription_id": lambda: _subscribed(item, "subscription_id", number_format),
        "billing_cycle": lambda: _subscribed(item, "billing_cycle", number_format),
        "period": lambda: _subscribed(item, "period", number_format),
        "share": lambda: _subscribed(item, "share", number_format),
        "remaining_term": lambda: _subscribed(item, "remaining_term", number_format),
    }.get(column)
    if printed is None:
        raise ValueError(f"no value for table column {column}")
    return printed()


def _discount(item: LineItem, number_format: fmt.NumberFormat) -> str:
    """A row without a discount leaves the column empty, as a real table does."""
    if item.discount_percent is None:
        return ""
    return f"{fmt.rate(item.discount_percent, number_format)} %"


def _subscribed(item: LineItem, column: str, number_format: fmt.NumberFormat) -> str:
    """A subscription column on a row that bills no subscription is an empty cell."""
    subscription = item.subscription
    if subscription is None:
        return ""
    share = subscription.share_percent
    return {
        "subscription_id": subscription.subscription_id,
        "billing_cycle": subscription.billing_cycle,
        "period": f"{subscription.period_start}-{subscription.period_end}",
        "share": "" if share is None else f"{fmt.rate(share, number_format)} %",
        "remaining_term": subscription.remaining_term or "",
    }[column]
