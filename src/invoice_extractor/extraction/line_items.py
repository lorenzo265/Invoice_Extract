"""The line-item table: find the header row, then read every row under it.

A table is located, not ranked — the header row fixes where each column starts, and every
row below reuses those positions until a stop label ends the table. That is why a
`LineItem` carries no `Evidence`: there is no ranking decision to audit (ADR-0002). A row
this module cannot read becomes a `Finding`, never an exception (ADR-0005).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from invoice_extractor.document.reader import TextLine
from invoice_extractor.domain.findings import Finding, Severity
from invoice_extractor.domain.models import LineItem
from invoice_extractor.extraction.normalizers import parse_number
from invoice_extractor.layout.schema import LINE_ITEM_COLUMNS, Layout, LineItemsLayout

# How far apart two cells' tops may sit and still be the same printed row, in points.
ROW_TOLERANCE = 2.0

Anchors = Sequence[tuple[float, str]]


@dataclass(frozen=True, slots=True)
class TableExtraction:
    """Every row that could be read, and a finding for every row that could not."""

    items: tuple[LineItem, ...]
    findings: tuple[Finding, ...]


def extract_line_items(lines: Sequence[TextLine], layout: Layout) -> TableExtraction:
    """Read the line-item table off every page, first page's table first."""
    items: list[LineItem] = []
    findings: list[Finding] = []
    headers = 0
    for page in _pages(lines):
        header = _header_row(page, layout.line_items)
        if header is None:
            continue
        headers += 1
        _read_page(page, header, layout, items, findings)
    if headers == 0:
        return TableExtraction((), (_header_not_found(),))
    return TableExtraction(tuple(items), tuple(findings))


def _read_page(
    page: Sequence[TextLine],
    header: Mapping[str, TextLine],
    layout: Layout,
    items: list[LineItem],
    findings: list[Finding],
) -> None:
    anchors = sorted((line.bbox.x0, column) for column, line in header.items())
    for group in _row_groups(page, header, layout.line_items.stop_labels):
        item, finding = _read_row(group, anchors, layout)
        if item is not None:
            items.append(item)
        if finding is not None:
            findings.append(finding)


def _pages(lines: Sequence[TextLine]) -> list[list[TextLine]]:
    by_page: dict[int, list[TextLine]] = {}
    for line in lines:
        by_page.setdefault(line.page, []).append(line)
    return [by_page[page] for page in sorted(by_page)]


def _header_row(
    lines: Sequence[TextLine], line_items: LineItemsLayout
) -> dict[str, TextLine] | None:
    """Five header words, one per column, whose tops agree — or nothing on this page."""
    matches = [
        (column, line)
        for column in LINE_ITEM_COLUMNS
        for line in lines
        if _is_one_of(line.text, line_items.header_labels[column])
    ]
    for _, anchor in matches:
        row = _columns_at(matches, anchor.bbox.y0)
        if len(row) == len(LINE_ITEM_COLUMNS):
            return row
    return None


def _columns_at(matches: Sequence[tuple[str, TextLine]], y0: float) -> dict[str, TextLine]:
    row: dict[str, TextLine] = {}
    for column, line in matches:
        if column not in row and abs(line.bbox.y0 - y0) <= ROW_TOLERANCE:
            row[column] = line
    return row


def _row_groups(
    page: Sequence[TextLine], header: Mapping[str, TextLine], stop_labels: Sequence[str]
) -> list[list[TextLine]]:
    """Everything under the header, grouped into printed rows, up to the first stop label."""
    floor = max(line.bbox.y0 for line in header.values())
    below = sorted(
        (line for line in page if line.bbox.y0 > floor),
        key=lambda line: (line.bbox.y0, line.bbox.x0),
    )
    groups: list[list[TextLine]] = []
    for line in below:
        if groups and abs(line.bbox.y0 - groups[-1][0].bbox.y0) <= ROW_TOLERANCE:
            groups[-1].append(line)
        else:
            groups.append([line])
    return _until_stop(groups, stop_labels)


def _until_stop(
    groups: Sequence[list[TextLine]], stop_labels: Sequence[str]
) -> list[list[TextLine]]:
    kept: list[list[TextLine]] = []
    for group in groups:
        if any(_starts_with_one_of(line.text, stop_labels) for line in group):
            break
        kept.append(group)
    return kept


def _read_row(
    group: Sequence[TextLine], anchors: Anchors, layout: Layout
) -> tuple[LineItem | None, Finding | None]:
    cells = _cells(group, anchors)
    absent = next((column for column in LINE_ITEM_COLUMNS if column not in cells), None)
    if absent is not None:
        return None, _incomplete(group, f"no {absent} cell")
    quantity = parse_number(cells["quantity"], layout)
    unit_price = parse_number(cells["unit_price"], layout)
    net_amount = parse_number(cells["net_amount"], layout)
    if quantity is None:
        return None, _incomplete(group, "an unreadable quantity")
    if unit_price is None:
        return None, _incomplete(group, "an unreadable unit_price")
    if net_amount is None:
        return None, _incomplete(group, "an unreadable net_amount")
    item = LineItem(cells["sku"], cells["description"], quantity, unit_price, net_amount)
    return item, None


def _cells(group: Sequence[TextLine], anchors: Anchors) -> dict[str, str]:
    cells: dict[str, str] = {}
    for line in group:
        column = _column_of(line, anchors)
        if column is not None and column not in cells:
            cells[column] = line.text.strip()
    return cells


def _column_of(cell: TextLine, anchors: Anchors) -> str | None:
    """The rightmost column that starts at or before this cell — anchors sort ascending."""
    left_of_cell = [column for anchor, column in anchors if anchor <= cell.bbox.x0 + ROW_TOLERANCE]
    return left_of_cell[-1] if left_of_cell else None


def _is_one_of(text: str, words: Sequence[str]) -> bool:
    return text.strip().casefold() in {word.strip().casefold() for word in words}


def _starts_with_one_of(text: str, labels: Sequence[str]) -> bool:
    stripped = text.strip().casefold()
    return any(stripped.startswith(label.strip().casefold()) for label in labels)


def _incomplete(group: Sequence[TextLine], problem: str) -> Finding:
    return Finding(
        severity=Severity.WARNING,
        code="line_item_incomplete",
        message=f"row at y0={group[0].bbox.y0} has {problem}",
    )


def _header_not_found() -> Finding:
    return Finding(
        severity=Severity.WARNING,
        code="line_items_header_not_found",
        message="no line-item header row was found on any page",
    )
