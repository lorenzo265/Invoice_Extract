"""`TableSpec`: a table read off every page it runs over, cell by cell with evidence.

The engine's collect step for a table is a header and a state machine (`units/columns.py`
and `units/rowkind.py`): the header says where the columns are on this page, the state
machine says what each printed row under it is. What comes out is raw text per column —
the shape of a line item or of a VAT-summary line is the reader's business, not this
module's, which is why nothing here parses a number or names a field.

A table that runs over a page break is one table: every page is read with its own header,
because a vendor redraws the header and may move a column while doing it.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from invoice_extractor.document.model import Document, Page, TextPart
from invoice_extractor.document.rows import CellRow, cell_rows_of
from invoice_extractor.domain.models import Evidence, Strategy
from invoice_extractor.extraction.units.columns import Header, find_header, place
from invoice_extractor.extraction.units.rowkind import Bounds, Previous, RowKind, classify
from invoice_extractor.profile.schema import TableEdge, TableProfile

# What a cell says and where it was drawn. The text is raw: a reader turns it into a value.
Cells = Mapping[str, "Cell"]


@dataclass(frozen=True, slots=True)
class Cell:
    """One column of one row, as printed, with the evidence for it (ADR-0002)."""

    text: str
    evidence: Evidence


@dataclass(frozen=True, slots=True)
class RawRow:
    """One row of a table: its cells by column, and whatever was indented under it."""

    cells: Cells
    sub_items: tuple[Cells, ...] = ()


@dataclass(frozen=True, slots=True)
class Reading:
    """Every row of one table, the pages it was found on, and what a page break carried."""

    rows: tuple[RawRow, ...] = ()
    pages: int = 0
    carried: tuple[Cell, ...] = ()


def read_table(
    document: Document,
    table: TableProfile,
    required: Sequence[str],
    avoid: TableProfile | None = None,
) -> Reading:
    """Read one table off the whole document, first page's rows first.

    `avoid` is another table of the same document, whose header this one is not. A
    line-item header uses a VAT summary's words — `Rate`, `Net`, `VAT Code` — and a
    document redraws it on every page it runs over, so the summary is read from the rows
    that header is not.
    """
    rows: list[RawRow] = []
    carried: list[Cell] = []
    pages = 0
    bounds = Bounds(
        stop_labels=table.stop_labels,
        carry_forward_labels=table.carry_forward_labels,
        sub_item_indent=table.sub_item_indent,
        required_columns=tuple(required),
    )
    for page in document.pages:
        pages += _read_page(page, table, bounds, rows, carried, avoid)
    return Reading(tuple(rows), pages, tuple(carried))


def _read_page(
    page: Page,
    table: TableProfile,
    bounds: Bounds,
    rows: list[RawRow],
    carried: list[Cell],
    avoid: TableProfile | None,
) -> int:
    """Read this page's rows onto the ones already read, and say whether it carried any.

    The rows read so far are handed in because a table does not start over at a page
    break: a component indented under the last row of one page belongs to that row, not to
    nothing. What does start over is what a loose description continues — the first line
    under a redrawn header continues nothing.
    """
    printed = cell_rows_of(page.lines)
    header = find_header(printed, table, avoid)
    if header is None:
        return 0
    previous = Previous()
    for row in _under(printed, header, page, table):
        placed = place(row, header)
        kind = classify(row, placed, header, bounds, previous)
        if kind is RowKind.STOP:
            break
        previous = _act(kind, row, placed, page, rows, carried, previous)
    return 1


def _act(
    kind: RowKind,
    row: CellRow,
    placed: Mapping[str, TextPart],
    page: Page,
    rows: list[RawRow],
    carried: list[Cell],
    previous: Previous,
) -> Previous:
    """Do what this row's kind says, and report what the next row is read against."""
    cells = _cells(placed, page.number)
    if kind is RowKind.ROW:
        rows.append(RawRow(cells))
        return Previous(row.bottom, read=True)
    if kind is RowKind.CONTINUATION and rows and "description" in rows[-1].cells:
        rows[-1] = _continued(rows[-1], cells)
        return Previous(row.bottom, read=True)
    if kind is RowKind.SUB_ITEM and rows:
        rows[-1] = _with_sub_item(rows[-1], cells)
        return Previous(row.bottom, read=False)
    if kind is RowKind.CARRY:
        carried.extend(cells.values())
    return Previous(row.bottom, read=False)


def _under(
    printed: Sequence[CellRow], header: Header, page: Page, table: TableProfile
) -> list[CellRow]:
    """Every row between the header and whatever the profile says closes the table."""
    floor = _floor(page, header, table)
    return [row for row in printed if row.top > header.bottom and row.top < floor]


def _floor(page: Page, header: Header, table: TableProfile) -> float:
    """Where the table stops on this page: the totals block, or the foot of the page.

    The totals anchor is found before any vendor is known, so it may name a block above
    the table — a metadata column reads like a run of rows. An anchor above this table's
    own header is not this table's end, and the stop labels are left to close it.
    """
    anchor = page.anchors.totals_top
    if table.page_bounds.end is TableEdge.TOTALS_ANCHOR and anchor is not None:
        return anchor if anchor > header.bottom else page.height
    return page.height


def _cells(placed: Mapping[str, TextPart], number: int) -> dict[str, Cell]:
    return {name: Cell(part.text.strip(), _evidence(part, number)) for name, part in placed.items()}


def _evidence(part: TextPart, page: int) -> Evidence:
    return Evidence(
        page=page,
        bbox=part.bbox,
        matched_label=None,
        strategy=Strategy.TABLE_CELL,
        raw_text=part.text.strip(),
    )


def _continued(row: RawRow, cells: Cells) -> RawRow:
    """The rest of a description, joined to the row it belongs to.

    A row is only continued by a line the state machine placed in the description column,
    so both sides of the join are descriptions.
    """
    described, rest = row.cells["description"], cells["description"]
    joined = Cell(f"{described.text} {rest.text}".strip(), described.evidence)
    return RawRow({**row.cells, "description": joined}, row.sub_items)


def _with_sub_item(row: RawRow, cells: Cells) -> RawRow:
    """A line indented under a row: a new component, or the rest of the last one."""
    if _starts_a_component(row, cells):
        return RawRow(row.cells, (*row.sub_items, cells))
    return RawRow(row.cells, (*row.sub_items[:-1], _joined(row.sub_items[-1], cells)))


def _starts_a_component(row: RawRow, cells: Cells) -> bool:
    """A priced line is a component of its own; so is one that begins a new sentence."""
    if not row.sub_items:
        return True
    if any(name != "description" for name in cells):
        return True
    return _new_sentence(row.sub_items[-1]["description"], cells["description"])


CONTINUING = ",-/(&:;"


def _new_sentence(last: Cell, current: Cell) -> bool:
    """A component's wording runs on; a new one starts a word the last line did not lead to.

    Nothing on the page separates one component from the next: both are set in the same
    face, indented the same, a line apart. What is left is the wording — a line that ends
    mid-clause is continued, and a line that starts a capital after one that did not is a
    new component.
    """
    ended = last.text.rstrip()
    if ended and ended[-1] in CONTINUING:
        return False
    first = current.text.lstrip()[:1]
    return first.isupper() or first.isdigit()


def _joined(cells: Cells, rest: Cells) -> dict[str, Cell]:
    described, more = cells["description"], rest["description"]
    text = f"{described.text} {more.text}".strip()
    return {**cells, "description": Cell(text, described.evidence)}
