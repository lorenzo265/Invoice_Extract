"""The line-item table, read off a document built in memory.

Every case here is a page a vendor really prints: a row whose description wraps, a
section with a heading and a total of its own, components indented under their row, a
table that runs over a page break, and a totals block that ends it.
"""

from __future__ import annotations

import dataclasses
from decimal import Decimal

from conftest import make_document, make_profile, make_table_profile
from invoice_extractor.domain.evidence import Strategy
from invoice_extractor.extraction.line_items import extract_line_items
from invoice_extractor.extraction.specs import LINE_ITEMS
from invoice_extractor.profile.schema import TableEdge

# What the tables below print, and where each column is drawn.
COLUMNS = {
    "pos": 50.0,
    "part_number": 90.0,
    "description": 150.0,
    "quantity": 380.0,
    "unit_price": 440.0,
    "net_amount": 500.0,
}
WIDTH = 40.0
HEIGHT = 10.0
LEADING = 12.0
HEADER_Y = 100.0


# A line of a fake page: `(page, text, x0, y0, x1, y1)`, the way `make_document` reads one.
Entry = tuple[int, str, float, float, float, float]


def cell(column: str, text: str) -> tuple[str, float]:
    return text, COLUMNS[column]


def entries(y: float, *placed: tuple[str, float]) -> list[Entry]:
    return [(1, text, x, y, x + WIDTH, y + HEIGHT) for text, x in placed]


def document(*rows: list[Entry]) -> object:
    header = entries(HEADER_Y, *(cell(column, column) for column in COLUMNS))
    return make_document([*header, *(entry for row in rows for entry in row)])


def profile(**changed: object) -> object:
    table = make_table_profile(columns={column: (column,) for column in COLUMNS}, **changed)
    return make_profile(line_items=table)


def read(document_read: object, vendor: object | None = None) -> object:
    return extract_line_items(document_read, vendor or profile(), LINE_ITEMS)


def item_row(y: float, pos: str, part: str, described: str, amount: str) -> list[Entry]:
    return entries(
        y,
        cell("pos", pos),
        cell("part_number", part),
        cell("description", described),
        cell("quantity", "2"),
        cell("unit_price", "3.50"),
        cell("net_amount", amount),
    )


def test_a_row_is_published_cell_by_cell_with_the_box_each_was_read_from() -> None:
    found = read(document(item_row(120.0, "1", "ACM-1", "A bolt", "7.00")))
    item = found.items[0]
    assert (item.pos, item.part_number, item.description) == (1, "ACM-1", "A bolt")
    assert (item.quantity, item.unit_price, item.net_amount) == (
        Decimal(2),
        Decimal("3.50"),
        Decimal("7.00"),
    )
    assert item.cells["net_amount"].strategy is Strategy.TABLE_CELL
    assert item.cells["description"].bbox.x0 == COLUMNS["description"]


def test_a_description_that_wrapped_is_read_back_as_one_description() -> None:
    wrapped = entries(132.0, cell("description", "sealed both sides"))
    found = read(document(item_row(120.0, "1", "ACM-1", "Deep groove bearing,", "7.00"), wrapped))
    assert found.items[0].description == "Deep groove bearing, sealed both sides"


def test_a_section_heading_is_not_a_row_and_not_part_of_the_row_above_it() -> None:
    heading = entries(160.0, cell("description", "Software licences"))
    first = item_row(120.0, "1", "ACM-1", "A bolt", "7.00")
    second = item_row(180.0, "2", "ACM-2", "A bearing", "9.00")
    found = read(document(first, heading, second))
    assert [item.description for item in found.items] == ["A bolt", "A bearing"]


def test_a_section_subtotal_does_not_end_the_table() -> None:
    """It says `Subtotal` in the description column, and the rows go on under it."""
    vendor = profile(stop_labels=("Subtotal",))
    subtotal = entries(150.0, cell("description", "Subtotal Licences"), cell("net_amount", "7.00"))
    second = item_row(190.0, "2", "ACM-2", "A bearing", "9.00")
    first = item_row(120.0, "1", "ACM-1", "A bolt", "7.00")
    found = read(document(first, subtotal, second), vendor)
    assert len(found.items) == 2


def test_the_totals_block_ends_the_table() -> None:
    vendor = profile(stop_labels=("Subtotal",))
    totals = entries(150.0, ("Subtotal", 380.0), cell("net_amount", "7.00"))
    after = item_row(190.0, "2", "ACM-2", "A bearing", "9.00")
    found = read(document(item_row(120.0, "1", "ACM-1", "A bolt", "7.00"), totals, after), vendor)
    assert [item.part_number for item in found.items] == ["ACM-1"]


def test_a_component_indented_under_a_row_belongs_to_that_row() -> None:
    component = entries(132.0, ("On-site installation, per hour", COLUMNS["description"] + 12.0))
    found = read(document(item_row(120.0, "1", "ACM-1", "A service", "7.00"), component))
    parts = [sub.description for sub in found.items[0].sub_items]
    assert parts == ["On-site installation, per hour"]
    assert len(found.items) == 1


def test_two_components_are_told_apart_by_the_wording_that_starts_the_second() -> None:
    """Nothing separates them on the page but the sentence the next one begins."""
    indent = COLUMNS["description"] + 12.0
    first = entries(132.0, ("Foundation training,", indent))
    rest = entries(144.0, ("1 day, up to 8 attendees", indent))
    second = entries(156.0, ("On-site installation, per hour", indent))
    found = read(document(item_row(120.0, "1", "ACM-1", "A service", "7.00"), first, rest, second))
    assert [sub.description for sub in found.items[0].sub_items] == [
        "Foundation training, 1 day, up to 8 attendees",
        "On-site installation, per hour",
    ]


def test_a_component_that_is_priced_starts_a_component_of_its_own() -> None:
    indent = COLUMNS["description"] + 12.0
    priced = (("Gold support", indent), cell("quantity", "1"), cell("unit_price", "9.00"))
    first = entries(132.0, *priced)
    found = read(document(item_row(120.0, "1", "ACM-1", "A service", "7.00"), first))
    sub = found.items[0].sub_items[0]
    assert sub.description == "Gold support"
    assert (sub.quantity, sub.unit_price) == (Decimal(1), Decimal("9.00"))


def test_a_carry_forward_line_is_not_a_row() -> None:
    vendor = profile(carry_forward_labels=("Carried forward",))
    carried = entries(150.0, cell("description", "Carried forward"), cell("net_amount", "7.00"))
    found = read(document(item_row(120.0, "1", "ACM-1", "A bolt", "7.00"), carried), vendor)
    assert len(found.items) == 1


def test_a_cell_that_is_not_a_number_is_reported_and_the_rest_of_the_row_kept() -> None:
    broken = entries(
        120.0,
        cell("pos", "1"),
        cell("part_number", "ACM-1"),
        cell("description", "A bolt"),
        cell("quantity", "two"),
        cell("net_amount", "7.00"),
    )
    found = read(document(broken))
    assert found.items[0].description == "A bolt"
    assert found.items[0].quantity is None
    assert [finding.code for finding in found.findings] == ["line_item_cell_unreadable"]


def test_a_document_with_no_header_anywhere_reports_and_reads_nothing() -> None:
    bare = make_document([(1, "nothing here", 50.0, 100.0, 200.0, 110.0)])
    found = read(bare)
    assert found.items == ()
    assert [finding.code for finding in found.findings] == ["line_items_header_not_found"]


def test_a_table_that_runs_over_a_page_break_is_one_table() -> None:
    first = document(item_row(120.0, "1", "ACM-1", "A bolt", "7.00"))
    second = [
        (2, text, x, y, x + WIDTH, y + HEIGHT)
        for text, x, y in (
            *((column, COLUMNS[column], HEADER_Y) for column in COLUMNS),
            ("2", COLUMNS["pos"], 120.0),
            ("ACM-2", COLUMNS["part_number"], 120.0),
            ("A bearing", COLUMNS["description"], 120.0),
            ("9.00", COLUMNS["net_amount"], 120.0),
        )
    ]
    both = dataclasses.replace(
        make_document([*_entries_of(first), *second]), source_path="two-pages.pdf"
    )
    found = read(both)
    assert [item.part_number for item in found.items] == ["ACM-1", "ACM-2"]


def _entries_of(document_read: object) -> list[Entry]:
    return [
        (line.page, line.text, line.bbox.x0, line.bbox.y0, line.bbox.x1, line.bbox.y1)
        for line in document_read.lines
    ]


def test_a_table_the_profile_ends_at_the_totals_anchor_stops_there() -> None:
    """The anchor is found from the page's own drawing, before any vendor is known."""
    vendor = profile(end=TableEdge.TOTALS_ANCHOR)
    totals = entries(300.0, ("Subtotal", 380.0), cell("net_amount", "7.00"))
    after = item_row(340.0, "2", "ACM-2", "A bearing", "9.00")
    page = document(item_row(120.0, "1", "ACM-1", "A bolt", "7.00"), totals, after)
    assert page.page(1).anchors.totals_top is not None
    found = read(page, vendor)
    assert [item.part_number for item in found.items] == ["ACM-1"]
