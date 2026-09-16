"""A table's columns, found from the header row the vendor printed.

A column is not a coordinate a profile declares — it is where this document drew it. The
header words say so: a left-aligned column's cells start where its heading starts, a
right-aligned column's cells end where its heading ends, and in both cases a cell's box
overlaps its heading's box. So a column is its heading's box, and a cell belongs to the
heading it overlaps most.

Two headings the reader could not keep apart are put back:

- `Remaining` over `Term` is one heading set on two lines, joined by the gap below it.
- `KDV % Satır Toplamı` is two headings a reader ran together because the columns touch,
  cut back apart where the vendor's own words for two columns meet.

Headings the catalog has no name for are kept as columns without one. They are what keeps
a cell under `Period` out of `Details`: a table has more columns than the catalog names,
and forgetting the nameless ones would hand their cells to a neighbour.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from invoice_extractor.document.model import BBox, TextPart
from invoice_extractor.document.rows import CellRow
from invoice_extractor.profile.schema import TableProfile

# How far under the header row a second line of heading may sit and still belong to it.
HEADING_LEADING = 4.0
# How much of a heading's own width a cell must overlap before it counts as that column's.
MIN_OVERLAP = 0.01

Labels = Mapping[str, tuple[str, ...]]


@dataclass(frozen=True, slots=True)
class Column:
    """One column of this document's table: what it is called, and where it was drawn."""

    name: str | None
    heading: str
    bbox: BBox


@dataclass(frozen=True, slots=True)
class Header:
    """The header row of one table on one page, with every column it printed."""

    columns: tuple[Column, ...]
    top: float
    bottom: float

    @property
    def named(self) -> tuple[str, ...]:
        return tuple(column.name for column in self.columns if column.name is not None)

    def column(self, name: str) -> Column | None:
        return next((column for column in self.columns if column.name == name), None)


def find_header(
    rows: Sequence[CellRow], table: TableProfile, avoid: TableProfile | None = None
) -> Header | None:
    """The first row that names enough of the table's columns, with its second line joined.

    `avoid` is another table of the same document whose header this one must not be
    mistaken for. The two vocabularies overlap — a line-item header says `Rate` and `Net`,
    and a document redraws it on every page it runs over — so a row that names more of
    that table's columns than of this one's is that table's header and not this one's.
    """
    for index, row in enumerate(rows):
        below = _continuation(row, rows[index + 1] if index + 1 < len(rows) else None)
        header = _header(row, below, table.columns)
        if len(set(header.named)) < table.min_header_matches:
            continue
        if avoid is not None and _is_header_of(row, avoid, len(set(header.named))):
            continue
        return header
    return None


def _is_header_of(row: CellRow, table: TableProfile, mine: int) -> bool:
    """Whether this row is more that table's header than the one being looked for."""
    named = len(set(_header(row, (), table.columns).named))
    return named >= table.min_header_matches and named > mine


def place(row: CellRow, header: Header) -> dict[str, TextPart]:
    """This row's cells by column name, keeping the first cell drawn in each column.

    A cell under a heading the catalog has no name for is dropped here: it was read, it
    was placed, and there is nowhere to publish it.
    """
    placed: dict[str, TextPart] = {}
    for cell in row.cells:
        column = column_of(cell, header)
        if column is not None and column.name is not None and column.name not in placed:
            placed[column.name] = cell
    return placed


def column_of(part: TextPart, header: Header) -> Column | None:
    """The column this cell was drawn in: the heading its box overlaps most.

    Overlap is what makes a heading a candidate; the edge they share is what chooses
    between candidates. A column sets its cells from one side — left-aligned text starts
    where its heading starts, an amount ends where its heading ends — so the heading whose
    edge this cell lines up with is the column it was drawn in, even where a longer
    heading beside it overlaps the cell more. `Steuerschlüssel` is wider than its own
    column and runs over `Satz`; the rate under `Satz` still lines up with `Satz`.
    """
    overlapping = [
        (column, _overlap(part.bbox, column.bbox))
        for column in header.columns
        if _overlap(part.bbox, column.bbox) > MIN_OVERLAP
    ]
    if not overlapping:
        return None
    ranked = min(overlapping, key=lambda pair: (_edge_apart(part.bbox, pair[0].bbox), -pair[1]))
    return ranked[0]


def _edge_apart(cell: BBox, heading: BBox) -> float:
    """How far this cell sits from the heading's nearer edge, left or right."""
    return min(abs(cell.x0 - heading.x0), abs(cell.x1 - heading.x1))


def _header(row: CellRow, below: Sequence[TextPart], columns: Labels) -> Header:
    found = tuple(column for cell in row.cells for column in _columns_of(cell, below, columns))
    return Header(columns=found, top=row.top, bottom=_band(found, row))


def _band(columns: Sequence[Column], row: CellRow) -> float:
    """Where the heading ends, measured on the columns it names.

    A row is everything drawn at that height, and at that height a page may be drawing
    something else too — a totals block beside a VAT summary. Measuring the band on the
    headings themselves keeps a neighbour's line from swallowing the table's first row.
    """
    named = [column.bbox.y1 for column in columns if column.name is not None]
    return max(named) if named else row.bottom


def _columns_of(cell: TextPart, below: Sequence[TextPart], columns: Labels) -> list[Column]:
    """What this drawn heading says: one column, two that ran together, or none named."""
    text, box = _joined(cell, below)
    named = _split(text, box, columns)
    if named is not None:
        return named
    return [Column(name=_name_of(cell.text, columns), heading=text, bbox=box)]


def _split(text: str, box: BBox, columns: Labels) -> list[Column] | None:
    """This heading as the columns it names, or nothing where it names none."""
    name = _name_of(text, columns)
    if name is not None:
        return [Column(name=name, heading=text.strip(), bbox=box)]
    return _cut(text, box, columns)


def _cut(text: str, box: BBox, columns: Labels) -> list[Column] | None:
    """Two headings a reader ran together, cut where the first one's wording ends.

    Where each heading begins is measured in characters, which is the only measure a
    span leaves — and the second heading begins after whatever space stands between
    them, so the gap between two columns is a gap here too.

    The longest first heading wins: `MomskodeSats` is a code column and a rate column,
    and cutting it at the shortest word that names something would make it a tax column,
    a code column and a rate column that the vendor never printed.
    """
    for at in reversed(range(1, len(text))):
        head = _name_of(text[:at], columns)
        if head is None:
            continue
        rest = _split(text[at:], _from(box, text, _begins(text, at)), columns)
        if rest is not None:
            return [Column(head, text[:at].strip(), _upto(box, text, at)), *rest]
    return None


def _begins(text: str, at: int) -> int:
    """Where the wording after a cut starts, the space between the two skipped."""
    tail = text[at:]
    return at + len(tail) - len(tail.lstrip())


def _upto(box: BBox, text: str, at: int) -> BBox:
    return BBox(x0=box.x0, y0=box.y0, x1=_at(box, at / len(text)), y1=box.y1)


def _from(box: BBox, text: str, at: int) -> BBox:
    return BBox(x0=_at(box, at / len(text)), y0=box.y0, x1=box.x1, y1=box.y1)


def _at(box: BBox, share: float) -> float:
    return box.x0 + (box.x1 - box.x0) * share


def _name_of(text: str, columns: Labels) -> str | None:
    wanted = _folded(text)
    for name, labels in columns.items():
        if any(wanted == _folded(label) for label in labels):
            return name
    return None


def _folded(text: str) -> str:
    return text.strip().strip(":").casefold()


def _continuation(row: CellRow, below: CellRow | None) -> tuple[TextPart, ...]:
    """A heading of two words set over two lines: `Remaining` above, `Term` under it.

    The second line belongs to the header when it sits within a line's leading of it, has
    fewer cells than the header, and stands under headings rather than beside them. The
    first row of the table sits further down and fills more columns, which is what keeps
    it from being read as the rest of the heading.
    """
    if below is None or below.top - row.bottom > HEADING_LEADING:
        return ()
    if len(below.cells) >= len(row.cells):
        return ()
    under = [cell for cell in below.cells if _stands_under(cell, row.cells)]
    return tuple(under) if len(under) == len(below.cells) else ()


def _stands_under(cell: TextPart, headings: Sequence[TextPart]) -> bool:
    return any(_overlap(cell.bbox, heading.bbox) > MIN_OVERLAP for heading in headings)


def _joined(cell: TextPart, below: Sequence[TextPart]) -> tuple[str, BBox]:
    """A heading and whatever was set under it, read as one wording and one box."""
    under = [part for part in below if _overlap(part.bbox, cell.bbox) > MIN_OVERLAP]
    if not under:
        return cell.text.strip(), cell.bbox
    text = " ".join([cell.text.strip(), *(part.text.strip() for part in under)])
    return text, _union(cell.bbox, *(part.bbox for part in under))


def _union(first: BBox, *rest: BBox) -> BBox:
    boxes = (first, *rest)
    return BBox(
        x0=min(box.x0 for box in boxes),
        y0=min(box.y0 for box in boxes),
        x1=max(box.x1 for box in boxes),
        y1=max(box.y1 for box in boxes),
    )


def _overlap(cell: BBox, heading: BBox) -> float:
    return max(0.0, min(cell.x1, heading.x1) - max(cell.x0, heading.x0))
