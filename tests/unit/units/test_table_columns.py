"""Where a table's columns are, read off the header the vendor printed."""

from __future__ import annotations

from conftest import PAGE_HEIGHT, PAGE_WIDTH, make_table_profile
from invoice_extractor.document.model import BBox, TextLine, TextPart
from invoice_extractor.document.rows import CellRow, cell_rows_of
from invoice_extractor.document.zones import classify
from invoice_extractor.extraction.units.columns import column_of, find_header, place

HEIGHT = 10.0
# The columns the rows below print: a table names the ones its vendor set, not all nine.
PRINTED = ("part_number", "description", "quantity", "unit_price", "net_amount")


def cell(text: str, x0: float, x1: float, y: float) -> TextPart:
    return TextPart(text, BBox(x0, y, x1, y + HEIGHT))


def row(y: float, *cells: TextPart, page: int = 1) -> CellRow:
    return CellRow(page=page, cells=cells)


def drawn(y: float, *cells: TextPart, page: int = 1) -> TextLine:
    """One line whose runs are those cells, the way a reader hands a joined line over."""
    box = BBox(
        min(part.bbox.x0 for part in cells),
        y,
        max(part.bbox.x1 for part in cells),
        y + HEIGHT,
    )
    text = " ".join(part.text for part in cells)
    return TextLine(page, text, box, classify(box, PAGE_WIDTH, PAGE_HEIGHT), parts=cells)


def make_items_profile() -> object:
    """A line-item table that names the five columns these rows are drawn with."""
    return make_table_profile(columns={column: (column,) for column in PRINTED})


def header_row(y: float = 100.0) -> CellRow:
    return row(
        y,
        cell("part_number", 50, 100, y),
        cell("description", 150, 250, y),
        cell("quantity", 380, 420, y),
        cell("unit_price", 440, 480, y),
        cell("net_amount", 500, 545, y),
    )


def test_the_first_row_that_names_enough_columns_is_the_header() -> None:
    above = row(50.0, cell("Invoice", 50, 100, 50.0))
    found = find_header([above, header_row()], make_items_profile())
    assert found is not None
    assert set(found.named) == {
        "part_number",
        "description",
        "quantity",
        "unit_price",
        "net_amount",
    }


def test_a_page_that_names_too_few_columns_has_no_header() -> None:
    profile = make_table_profile(min_header_matches=3)
    thin = row(100.0, cell("description", 150, 250, 100.0))
    assert find_header([thin], profile) is None


def test_a_heading_set_over_two_lines_is_one_heading() -> None:
    """`Remaining` over `Term` is one column, joined by the gap under the header row."""
    profile = make_table_profile(
        columns={"description": ("description",), "net_amount": ("Remaining Term",)},
        min_header_matches=2,
    )
    first = row(100.0, cell("description", 150, 250, 100.0), cell("Remaining", 500, 545, 100.0))
    second = row(112.0, cell("Term", 510, 545, 112.0))
    found = find_header([first, second], profile)
    assert found is not None
    assert set(found.named) == {"description", "net_amount"}


def test_the_row_under_the_header_is_not_read_as_the_rest_of_it() -> None:
    """A data row sits further down and fills more columns than a second heading line."""
    body = row(
        120.0,
        cell("ACM-1", 50, 100, 120.0),
        cell("A bolt", 150, 250, 120.0),
        cell("2", 380, 420, 120.0),
        cell("3.50", 440, 480, 120.0),
        cell("7.00", 500, 545, 120.0),
    )
    found = find_header([header_row(), body], make_items_profile())
    assert found is not None
    assert found.bottom < body.top


def test_two_headings_a_reader_ran_together_are_cut_back_apart() -> None:
    """`KDV % Satır Toplamı` is two columns whose words touch, not one column."""
    profile = make_table_profile(
        columns={"vat_rate": ("KDV %",), "net_amount": ("Satır Toplamı",), "quantity": ("Miktar",)},
        min_header_matches=3,
    )
    header = row(
        100.0,
        cell("Miktar", 380, 420, 100.0),
        cell("KDV % Satır Toplamı", 466, 545, 100.0),
    )
    found = find_header([header], profile)
    assert found is not None
    assert set(found.named) == {"quantity", "vat_rate", "net_amount"}


def test_the_longest_first_heading_wins_where_two_cuts_are_possible() -> None:
    """`MomskodeSats` is a code column and a rate column, not a tax column and two more."""
    profile = make_table_profile(
        columns={"code": ("Momskode",), "rate": ("Sats",), "vat": ("Moms",), "base": ("Netto",)},
        min_header_matches=2,
    )
    header = row(100.0, cell("MomskodeSats", 50, 107, 100.0), cell("Netto", 200, 240, 100.0))
    found = find_header([header], profile)
    assert found is not None
    assert set(found.named) == {"code", "rate", "base"}


def test_a_cell_belongs_to_the_heading_whose_edge_it_lines_up_with() -> None:
    """A wide heading may cover its neighbour; the cells still line up with their own."""
    profile = make_table_profile(
        columns={"code": ("Steuerschlüssel",), "rate": ("Steuersatz",)}, min_header_matches=2
    )
    header = row(100.0, cell("Steuerschlüssel", 50, 111, 100.0), cell("Steuersatz", 90, 130, 100.0))
    found = find_header([header], profile)
    assert found is not None
    rate = cell("19 %", 90, 110, 120.0)
    column = column_of(rate, found)
    assert column is not None
    assert column.name == "rate"


def test_a_cell_under_no_heading_at_all_is_placed_nowhere() -> None:
    found = find_header([header_row()], make_items_profile())
    assert found is not None
    assert column_of(cell("note", 300, 340, 120.0), found) is None


def test_place_keeps_the_first_cell_drawn_in_each_column() -> None:
    found = find_header([header_row()], make_items_profile())
    assert found is not None
    body = row(120.0, cell("first", 150, 200, 120.0), cell("second", 205, 250, 120.0))
    placed = place(body, found)
    assert placed["description"].text == "first"


def test_a_header_is_not_read_out_of_another_tables_header() -> None:
    """A line-item header says `Rate` and `Net` too, and a document redraws it per page."""
    items = make_table_profile(columns={c: (c,) for c in PRINTED}, min_header_matches=3)
    summary = make_table_profile(
        columns={"rate": ("quantity",), "base": ("description",), "vat": ("Tax Amount",)},
        min_header_matches=2,
    )
    real = row(200.0, cell("quantity", 50, 100, 200.0), cell("Tax Amount", 150, 250, 200.0))
    found = find_header([header_row(), real], summary, avoid=items)
    assert found is not None
    assert found.top == real.top


def test_a_reader_that_gave_no_runs_leaves_the_whole_line_as_one_cell() -> None:
    box = BBox(380, 100, 420, 110)
    line = TextLine(1, "quantity", box, classify(box, PAGE_WIDTH, PAGE_HEIGHT))
    assert [part.text for part in line.cells] == ["quantity"]
    assert cell_rows_of([line])[0].cells[0].text == "quantity"


def test_a_line_drawn_in_several_runs_is_several_cells() -> None:
    joined = drawn(100.0, cell("Kód DPH", 50, 85, 100.0), cell("Sazba", 90, 113, 100.0))
    assert [part.text for part in cell_rows_of([joined])[0].cells] == ["Kód DPH", "Sazba"]
