"""The line-item table: measuring a row, drawing a row, and the rules around them.

A row's height is not a constant — a description that wraps to three lines is three lines
tall — so the table measures every row before the pagination decides where the page
breaks. Measuring and drawing share the wrapped lines, so what was measured is what is
drawn.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from invoice_forge.layout.spec import Column, ItemsSpec, Weight
from invoice_forge.model import Document, LineItem
from invoice_forge.render import text as fmt
from invoice_forge.render.placement import cell
from invoice_forge.render.sheet import Sheet
from invoice_forge.render.wording import Wording

HEADER_RULE_ABOVE = 10.0
HEADER_RULE_BELOW = 4.0
HEADER_TO_FIRST_ROW = 18.0
HEADER_HEIGHT = HEADER_RULE_ABOVE + HEADER_TO_FIRST_ROW
CARRY_RULE_ABOVE = 9.0
CARRY_HEIGHT = 18.0
# The five columns the extractor reads. The others are printed but not recorded as cells.
TRUTH_CELLS = frozenset({"sku", "description", "quantity", "unit_price", "net_amount"})


@dataclass(frozen=True, slots=True)
class MeasuredRow:
    """One item, with its description already broken to the column it will be drawn in."""

    item: LineItem
    lines: tuple[str, ...]
    height: float


def measure_rows(sheet: Sheet, document: Document, spec: ItemsSpec) -> tuple[MeasuredRow, ...]:
    """Every row of the document, measured in the face it will be drawn in."""
    return tuple(_measure(sheet, item, spec) for item in document.items)


def rows_total(rows: tuple[MeasuredRow, ...]) -> Decimal:
    """What a page's rows add up to, for the line a page break carries forward."""
    return sum((row.item.net_amount for row in rows), Decimal(0))


def draw_header(sheet: Sheet, spec: ItemsSpec, wording: Wording, y: float) -> float:
    """The column headings, between two rules. Returns the first row's baseline."""
    if spec.ruled:
        sheet.rule(y - HEADER_RULE_ABOVE, heavy=True)
    for column in spec.columns:
        sheet.draw_column(column, y, wording.columns[column.name], spec.header_size, Weight.BOLD)
    if spec.ruled:
        sheet.rule(y + HEADER_RULE_BELOW, heavy=True)
    return y + HEADER_TO_FIRST_ROW


def draw_row(sheet: Sheet, row: MeasuredRow, spec: ItemsSpec, wording: Wording, y: float) -> float:
    """One item across its columns. Returns the baseline the next row starts at."""
    for column in spec.columns:
        if column.name == "description":
            _draw_description(sheet, row, spec, column, y)
            continue
        mark = cell(row.item.pos, column.name) if column.name in TRUTH_CELLS else None
        printed = _cell_text(row.item, column.name, wording)
        sheet.draw_column(column, y, printed, spec.row_size, Weight.REGULAR, mark)
    return y + row.height


def draw_carry(sheet: Sheet, spec: ItemsSpec, label: str, amount: str, y: float) -> float:
    """The subtotal a break carries: out at the foot of a page, in at the head of the next."""
    description = _column(spec, "description")
    if spec.ruled:
        sheet.rule(y - CARRY_RULE_ABOVE)
    sheet.draw(description.anchor, y, label, spec.row_size, Weight.BOLD)
    sheet.draw_right(_column(spec, "net_amount").anchor, y, amount, spec.row_size, Weight.BOLD)
    return y + CARRY_HEIGHT


def _column(spec: ItemsSpec, name: str) -> Column:
    return next(column for column in spec.columns if column.name == name)


def _measure(sheet: Sheet, item: LineItem, spec: ItemsSpec) -> MeasuredRow:
    lines = sheet.wrapped(item.description, spec.description_width, spec.row_size)
    return MeasuredRow(item=item, lines=lines, height=spec.row_leading * len(lines) + spec.row_gap)


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
        "vat_rate": lambda: fmt.rate(item.vat_rate),
        "net_amount": lambda: fmt.money(item.net_amount, number_format),
    }.get(column)
    if printed is None:
        raise ValueError(f"no value for table column {column}")
    return printed()
