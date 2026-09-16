"""The line-item table, shaped: raw cells in, `LineItem`s out.

`extraction/table.py` says where the rows are and what each cell says; this module says
what a row *is*. The two are apart because reading a table and knowing what its columns
mean are different jobs: the VAT summary is read by the same engine and shaped by
`vat_summary.py` into something else entirely.

A cell that will not parse is not a row thrown away — the row is published with that cell
empty and a `Finding` beside it, because a quantity nobody can read is not a reason to
lose the description and the amount (ADR-0005).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal

from invoice_extractor.document.model import Document
from invoice_extractor.domain.evidence import Evidence
from invoice_extractor.domain.findings import Finding, Severity
from invoice_extractor.domain.rows import LineItem, SubItem
from invoice_extractor.extraction.spec import TableSpec
from invoice_extractor.extraction.table import Cell, Cells, RawRow, read_table
from invoice_extractor.extraction.units.normalizers import parse_number
from invoice_extractor.profile.schema import Profile

# The columns whose text is a number in the vendor's own format.
NUMBERS: tuple[str, ...] = ("quantity", "unit_price", "discount_pct", "vat_rate", "net_amount")


@dataclass(frozen=True, slots=True)
class TableExtraction:
    """Every row that could be read, and a finding for every cell that could not."""

    items: tuple[LineItem, ...]
    findings: tuple[Finding, ...]


def extract_line_items(document: Document, profile: Profile, spec: TableSpec) -> TableExtraction:
    """Read the line-item table off every page it runs over, first page's rows first."""
    reading = read_table(document, profile.line_items, spec.required_columns)
    if reading.pages == 0:
        return TableExtraction((), (_header_not_found(),))
    items: list[LineItem] = []
    findings: list[Finding] = []
    for index, row in enumerate(reading.rows):
        items.append(_item(row, profile, index, findings, spec.columns))
    return TableExtraction(tuple(items), tuple(findings))


def _item(
    row: RawRow,
    profile: Profile,
    index: int,
    findings: list[Finding],
    columns: Sequence[str],
) -> LineItem:
    numbers = {column: _number(row.cells, column, profile, index, findings) for column in NUMBERS}
    return LineItem(
        pos=_position(row.cells, profile, index, findings),
        part_number=_text(row.cells, "part_number"),
        description=_text(row.cells, "description"),
        unit=_text(row.cells, "unit"),
        quantity=numbers["quantity"],
        unit_price=numbers["unit_price"],
        discount_pct=numbers["discount_pct"],
        vat_rate=numbers["vat_rate"],
        net_amount=numbers["net_amount"],
        sub_items=tuple(_sub_item(sub, profile) for sub in row.sub_items),
        cells=_evidence(row.cells, columns),
    )


def _sub_item(cells: Cells, profile: Profile) -> SubItem:
    return SubItem(
        description=_text(cells, "description") or "",
        quantity=_parsed(cells.get("quantity"), profile),
        unit_price=_parsed(cells.get("unit_price"), profile),
    )


def _text(cells: Cells, column: str) -> str | None:
    cell = cells.get(column)
    return None if cell is None else cell.text


def _number(
    cells: Cells, column: str, profile: Profile, index: int, findings: list[Finding]
) -> Decimal | None:
    cell = cells.get(column)
    if cell is None:
        return None
    value = _parsed(cell, profile)
    if value is None:
        findings.append(_unreadable(index, column, cell.text))
    return value


def _position(cells: Cells, profile: Profile, index: int, findings: list[Finding]) -> int | None:
    """The row number the vendor printed, which is a count and not an amount."""
    value = _number(cells, "pos", profile, index, findings)
    return None if value is None else int(value)


def _parsed(cell: Cell | None, profile: Profile) -> Decimal | None:
    return None if cell is None else parse_number(cell.text, profile)


def _evidence(cells: Cells, columns: Sequence[str]) -> Mapping[str, Evidence]:
    return {column: cells[column].evidence for column in columns if column in cells}


def _unreadable(index: int, column: str, printed: str) -> Finding:
    return Finding(
        severity=Severity.WARNING,
        code="line_item_cell_unreadable",
        message=f"line_items[{index}].{column} says {printed!r}, which is not a number",
        field=column,
    )


def _header_not_found() -> Finding:
    return Finding(
        severity=Severity.WARNING,
        code="line_items_header_not_found",
        message="no line-item header row was found on any page",
    )
