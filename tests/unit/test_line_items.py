"""The table extractor, on pages built in memory."""

from __future__ import annotations

from decimal import Decimal

import pytest

from conftest import line, make_profile, make_table_profile
from invoice_extractor.document.reader import TextLine
from invoice_extractor.domain.findings import Severity
from invoice_extractor.domain.models import LINE_ITEM_COLUMNS
from invoice_extractor.extraction.line_items import extract_line_items
from invoice_extractor.profile.schema import Profile

COLUMN_X = (56, 140, 320, 370, 450)
HEADER_Y = 460
FIRST_ROW_Y = 478
ROW_STEP = 18

ACME_HEADER = ("SKU", "Description", "Qty", "Unit Price", "Net Amount")
ACME_ROWS = (
    ("ACM-1001", "Hex bolt M8 x 40, zinc", "500", "0.12", "60.00"),
    ("ACM-2210", "Bearing 6204-2RS", "40", "3.85", "154.00"),
)


def table_profile(
    header_labels: dict[str, tuple[str, ...]] | None = None,
    stop_labels: tuple[str, ...] = ("Subtotal",),
    decimal_separator: str = ".",
    thousands_separators: tuple[str, ...] = (",",),
) -> Profile:
    labels = header_labels or {
        "part_number": ("SKU",),
        "description": ("Description",),
        "quantity": ("Qty",),
        "unit_price": ("Unit Price",),
        "net_amount": ("Net Amount",),
    }
    return make_profile(
        decimal_separator=decimal_separator,
        thousands_separators=thousands_separators,
        line_items=make_table_profile(columns=labels, stop_labels=stop_labels),
    )


def row_lines(cells: tuple[str, ...], y: float) -> list[TextLine]:
    return [line(text, x, y) for x, text in zip(COLUMN_X, cells, strict=True)]


def page(
    header: tuple[str, ...] = ACME_HEADER,
    rows: tuple[tuple[str, ...], ...] = ACME_ROWS,
    trailing: tuple[str, ...] = ("Subtotal: 214.00",),
) -> list[TextLine]:
    lines = row_lines(header, HEADER_Y)
    for index, cells in enumerate(rows):
        lines += row_lines(cells, FIRST_ROW_Y + index * ROW_STEP)
    for index, text in enumerate(trailing):
        lines.append(line(text, 400, 620 + index * ROW_STEP))
    return lines


def test_extracts_all_rows_until_stop_label() -> None:
    table = extract_line_items(page(), table_profile())
    assert table.findings == ()
    assert [item.part_number for item in table.items] == ["ACM-1001", "ACM-2210"]
    assert table.items[0].quantity == Decimal("500")
    assert table.items[0].unit_price == Decimal("0.12")
    assert table.items[0].net_amount == Decimal("60.00")


def test_stop_label_line_is_not_a_row() -> None:
    table = extract_line_items(page(), table_profile())
    assert all("Subtotal" not in item.part_number for item in table.items)
    assert len(table.items) == len(ACME_ROWS)


def test_description_with_digits_and_commas_stays_whole() -> None:
    rows = (("FJ-771", "Kabelkanal 40x60, 2 m", "30", "89.00", "2670.00"),)
    table = extract_line_items(page(rows=rows), table_profile())
    assert table.items[0].description == "Kabelkanal 40x60, 2 m"


def test_header_synonyms_are_accepted() -> None:
    labels = {
        "part_number": ("SKU", "Item"),
        "description": ("Description", "Item Description"),
        "quantity": ("Qty", "Quantity"),
        "unit_price": ("Unit Price", "Price"),
        "net_amount": ("Net Amount", "Amount"),
    }
    header = ("Item", "Item Description", "Quantity", "Price", "Amount")
    table = extract_line_items(page(header=header), table_profile(header_labels=labels))
    assert len(table.items) == len(ACME_ROWS)


def test_no_header_yields_warning_and_empty_table() -> None:
    table = extract_line_items(page(header=("A", "B", "C", "D", "E")), table_profile())
    assert table.items == ()
    (finding,) = table.findings
    assert finding.code == "line_items_header_not_found"
    assert finding.severity is Severity.WARNING


def test_missing_cell_yields_warning_finding_and_skips_row() -> None:
    lines = row_lines(ACME_HEADER, HEADER_Y)
    lines += [line("ACM-1001", 56, FIRST_ROW_Y), line("Hex bolt", 140, FIRST_ROW_Y)]
    table = extract_line_items(lines, table_profile())
    assert table.items == ()
    (finding,) = table.findings
    assert finding.code == "line_item_incomplete"
    assert "quantity" in finding.message
    assert str(line("ACM-1001", 56, FIRST_ROW_Y).bbox.y0) in finding.message


@pytest.mark.parametrize(
    ("cells", "column"),
    [
        (("ACM-1001", "Hex bolt", "many", "0.12", "60.00"), "quantity"),
        (("ACM-1001", "Hex bolt", "500", "free", "60.00"), "unit_price"),
        (("ACM-1001", "Hex bolt", "500", "0.12", "n/a"), "net_amount"),
    ],
)
def test_unreadable_number_yields_warning_finding_and_skips_row(
    cells: tuple[str, ...], column: str
) -> None:
    table = extract_line_items(page(rows=(cells,)), table_profile())
    assert table.items == ()
    (finding,) = table.findings
    assert finding.code == "line_item_incomplete"
    assert column in finding.message


def test_a_partial_header_row_is_not_a_header() -> None:
    partial = ("SKU", "Description", "Qty", "unnamed", "unnamed")
    table = extract_line_items(page(header=partial), table_profile())
    assert table.items == ()
    assert table.findings[0].code == "line_items_header_not_found"


def test_a_stray_header_word_elsewhere_is_not_part_of_the_header_row() -> None:
    lines = page()
    lines.append(line("Qty", 320, 300))
    table = extract_line_items(lines, table_profile())
    assert [item.part_number for item in table.items] == ["ACM-1001", "ACM-2210"]


def test_a_cell_left_of_every_column_is_ignored() -> None:
    lines = page(rows=(("ACM-1001", "Hex bolt", "500", "0.12", "60.00"),))
    lines.append(line("*", 10, FIRST_ROW_Y))
    table = extract_line_items(lines, table_profile())
    assert table.items[0].part_number == "ACM-1001"


def test_a_second_cell_in_one_column_does_not_displace_the_first() -> None:
    lines = page(rows=(("ACM-1001", "Hex bolt", "500", "0.12", "60.00"),))
    lines.append(line("ACM-9999", 60, FIRST_ROW_Y))
    table = extract_line_items(lines, table_profile())
    assert table.items[0].part_number == "ACM-1001"


def test_numbers_use_layout_separators() -> None:
    rows = (("FJ-771", "Kabelkanal", "30", "89,00", "2 670,00"),)
    profile = table_profile(
        stop_labels=("Netto",), decimal_separator=",", thousands_separators=(" ",)
    )
    table = extract_line_items(page(rows=rows, trailing=("Netto: 2 670,00",)), profile)
    assert table.items[0].net_amount == Decimal("2670.00")
    assert table.items[0].unit_price == Decimal("89.00")


def test_rows_from_every_page_are_kept_in_page_order() -> None:
    first = page(rows=(("A-1", "first", "1", "1.00", "1.00"),), trailing=())
    second = [
        TextLine(2, text.text, text.bbox, text.zone)
        for text in page(rows=(("B-1", "second", "2", "2.00", "4.00"),), trailing=())
    ]
    table = extract_line_items([*second, *first], table_profile())
    assert [item.part_number for item in table.items] == ["A-1", "B-1"]


def test_table_columns_are_the_five_the_schema_names() -> None:
    table = extract_line_items(page(), table_profile())
    expected = ("part_number", "description", "quantity", "unit_price", "net_amount")
    assert expected == LINE_ITEM_COLUMNS
    assert table.items[0].part_number and table.items[0].description
