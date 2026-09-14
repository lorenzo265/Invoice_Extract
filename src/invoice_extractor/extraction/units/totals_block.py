"""Where the totals block is on the page, and which of its rows names what.

This is the geometry half of `extraction/block.py`: it finds the short column of rows a
document adds up in and says which component each of them names. What those rows come to
— the amounts, the charges, the echo in another currency — is the other half's business.

Two rules do the finding. The block is the run of rows that names the most components in
one column, so a table heading that happens to say `VAT %` loses to a block that names
four. And the longest label wins, so `Total VAT` names the tax rather than the total.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from invoice_extractor.document.model import Document, TextPart
from invoice_extractor.document.rows import CellRow, cell_rows_of
from invoice_extractor.profile.schema import ComponentProfile, Profile

# How far from the block's own left edge a row still belongs to it, in points.
COLUMN_TOLERANCE = 2.0
# A4 at 72 dpi, which is what a profile's `cluster_gap` is a fraction of.
PAGE_HEIGHT = 842.0


@dataclass(frozen=True, slots=True)
class Named:
    """A row of the block and the component it names, with the label that named it."""

    name: str
    component: ComponentProfile
    label: TextPart
    matched: str


@dataclass(frozen=True, slots=True)
class Block:
    """The rows of the totals block, and the left edge of the column they are set in."""

    rows: tuple[CellRow, ...]
    edge: float


def find_block(document: Document, profile: Profile) -> Block:
    """The totals block: the column of component rows the last page adds up in.

    A component's word turns up elsewhere — a table heading that says `VAT %` begins with
    the vendor's word for VAT — so the block is not the first row that names one. It is
    the run of rows naming the most of them, in one column, close together; a stray match
    in a table names one component and loses to a block that names four.
    """
    page = document.page(document.page_count)
    rows = cell_rows_of(page.lines)
    found = [(row, component_of(row, profile.totals.components)) for row in rows]
    clusters = _clusters([(row, named) for row, named in found if named is not None], profile)
    if not clusters:
        return Block((), 0.0)
    best = max(clusters, key=_names_most)
    return Block(tuple(_column_from(rows, best, profile)), best[0][1].label.bbox.x0)


def component_of(
    row: CellRow, components: Mapping[str, ComponentProfile], edge: float | None = None
) -> Named | None:
    """Which component this row names, by the longest of its labels the row begins with.

    `edge` is the block's own column, once it is known. A row of a page is everything
    drawn at that height, and the VAT summary beside the block says `Rate` at the same
    height as the block says `Net`: only the cell in the block's column names its rows.
    """
    best: Named | None = None
    for cell in row.cells:
        if edge is not None and not at(cell, edge):
            continue
        text = cell.text.strip().casefold()
        for name, component in components.items():
            for label in component.labels:
                folded = label.strip().casefold()
                if folded and text.startswith(folded) and _longer(best, folded):
                    best = Named(name, component, cell, folded)
    return best


def at(cell: TextPart, edge: float) -> bool:
    """An amount set under its label starts where the label starts, and nothing else does."""
    return abs(cell.bbox.x0 - edge) <= COLUMN_TOLERANCE


def amounts(row: CellRow, found: Named) -> list[TextPart]:
    """Every value printed beside the label, left to right — one per column of the block."""
    return [
        cell for cell in row.cells if cell is not found.label and cell.bbox.x0 > found.label.bbox.x0
    ]


def _names_most(cluster: Sequence[tuple[CellRow, Named]]) -> tuple[int, float]:
    """How good a candidate block is: the components it names, then how low it sits."""
    return len({named.name for _, named in cluster}), cluster[0][0].top


def _clusters(
    named: Sequence[tuple[CellRow, Named]], profile: Profile
) -> list[list[tuple[CellRow, Named]]]:
    """Component rows grouped into blocks: one column, one run, nothing far between.

    A page draws more than one column at a time — the VAT summary's own heading sits
    between two rows of the totals block — so a row joins the open block in its own
    column, not whichever block was open last.
    """
    gap = profile.totals.cluster_gap * PAGE_HEIGHT
    grouped: list[list[tuple[CellRow, Named]]] = []
    for row, found in named:
        open_block = next(
            (block for block in reversed(grouped) if _joins(block[-1], (row, found), gap)), None
        )
        if open_block is None:
            grouped.append([(row, found)])
        else:
            open_block.append((row, found))
    return grouped


def _joins(last: tuple[CellRow, Named], current: tuple[CellRow, Named], gap: float) -> bool:
    same_column = abs(current[1].label.bbox.x0 - last[1].label.bbox.x0) <= COLUMN_TOLERANCE
    return same_column and current[0].top - last[0].bottom <= gap


def _column_from(
    rows: Sequence[CellRow], cluster: Sequence[tuple[CellRow, Named]], profile: Profile
) -> list[CellRow]:
    """Every row of the block's own column, from its first component row downward.

    The rows between the components belong to it too: a vendor that sets an amount under
    its label prints a row of its own for the amount, and the currency it echoes the
    total in is a row under all of them.
    """
    edge = cluster[0][1].label.bbox.x0
    gap = profile.totals.cluster_gap * PAGE_HEIGHT
    kept: list[CellRow] = []
    for row in rows:
        if row.top < cluster[0][0].top or not _starts_at(row, edge):
            continue
        if kept and row.top - kept[-1].bottom > gap:
            break
        kept.append(row)
    return kept


def _starts_at(row: CellRow, edge: float) -> bool:
    return any(at(cell, edge) for cell in row.cells)


def _longer(best: Named | None, label: str) -> bool:
    return best is None or len(label) > len(best.matched)
