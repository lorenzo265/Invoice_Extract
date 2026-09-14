"""What one printed row under a table's header is: a row, or one of the things between rows.

A real table is not a list of rows. Between them a vendor prints section headings,
section subtotals, the line a page break carries forward, and the rest of a description
that did not fit — and every one of them has to be told apart from a row, because
counting one as a row is a row too many and dropping a real one is a row too few.

Each rule is geometry plus the vendor's own vocabulary, in that order:

| Kind | What says so |
|---|---|
| `CARRY` | a carry-forward label: what the page break carried, not a row |
| `STOP` | a stop label printed outside the description column: the totals block has begun |
| `SUBTOTAL` | a stop label printed *inside* it: a section's own total, which the table runs past |
| `SUB_ITEM` | a description indented past `sub_item_indent`: a component of the row above |
| `ROW` | a cell in every column the table cannot do without |
| `CONTINUATION` | a description alone, close under the row it belongs to |
| `OTHER` | anything else, a section heading among it — read, placed, and passed over |
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum, auto

from invoice_extractor.document.model import TextPart
from invoice_extractor.document.rows import CellRow
from invoice_extractor.extraction.units.columns import Column, Header

# How much of a line's own height may stand between it and the row above before it is a
# block of its own rather than the rest of that row.
CONTINUATION_GAP = 0.5


class RowKind(Enum):
    ROW = auto()
    CONTINUATION = auto()
    SUB_ITEM = auto()
    CARRY = auto()
    SUBTOTAL = auto()
    STOP = auto()
    OTHER = auto()


@dataclass(frozen=True, slots=True)
class Bounds:
    """The vocabulary and the measures one table reads its rows by."""

    stop_labels: tuple[str, ...]
    carry_forward_labels: tuple[str, ...]
    sub_item_indent: float
    required_columns: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Previous:
    """The row last read, which is what a loose line of description belongs to."""

    bottom: float | None = None
    read: bool = False

    def continues(self, row: CellRow) -> bool:
        """A description is the rest of the row above when it sits right under it."""
        if not self.read or self.bottom is None:
            return False
        return row.top - self.bottom <= (row.bottom - row.top) * CONTINUATION_GAP


def classify(
    row: CellRow,
    placed: Mapping[str, TextPart],
    header: Header,
    table: Bounds,
    previous: Previous,
) -> RowKind:
    """Which of the seven this printed row is. Order matters: the first rule that fits wins."""
    if _labelled(row, table.carry_forward_labels) is not None:
        return RowKind.CARRY
    stopped = _labelled(row, table.stop_labels)
    if stopped is not None:
        return RowKind.SUBTOTAL if _in_description(stopped, header) else RowKind.STOP
    if _indented(placed.get("description"), header, table.sub_item_indent):
        return RowKind.SUB_ITEM
    if all(name in placed for name in table.required_columns):
        return RowKind.ROW
    if _only_description(placed) and previous.continues(row):
        return RowKind.CONTINUATION
    return RowKind.OTHER


def _labelled(row: CellRow, labels: Sequence[str]) -> TextPart | None:
    """The cell one of these labels introduced, where the row carries one."""
    folded = [label.strip().casefold() for label in labels if label.strip()]
    for cell in row.cells:
        text = cell.text.strip().casefold()
        if any(text.startswith(label) for label in folded):
            return cell
    return None


def _in_description(cell: TextPart, header: Header) -> bool:
    return _same_column(cell, header.column("description"))


def _same_column(cell: TextPart, column: Column | None) -> bool:
    return column is not None and abs(cell.bbox.x0 - column.bbox.x0) <= 1.0


def _indented(description: TextPart | None, header: Header, indent: float) -> bool:
    column = header.column("description")
    if description is None or column is None:
        return False
    return description.bbox.x0 - column.bbox.x0 >= indent


def _only_description(placed: Mapping[str, TextPart]) -> bool:
    return set(placed) == {"description"}
